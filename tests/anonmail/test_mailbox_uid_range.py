"""Configurable per-mailbox UID range (MAILBOX_UID_MIN / MAILBOX_UID_MAX).

A smaller range lets Mailu run where containers live in a user namespace
(rootless Docker or Podman, userns-remap), where only the IDs of the host's
subuid/subgid block (usually 0-65535) exist.
"""
import importlib.util
import pathlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from socrate import mailbox

from mailu import configuration, create_app_from_config, models


# --- socrate.mailbox.uid_range / valid_uid ---------------------------------

def test_default_range():
    assert mailbox.uid_range({}) == (100000, 2000000000)


def test_custom_range():
    assert mailbox.uid_range({'MAILBOX_UID_MIN': '10000', 'MAILBOX_UID_MAX': ' 60000 '}) == (10000, 60000)


def test_empty_values_mean_default():
    assert mailbox.uid_range({'MAILBOX_UID_MIN': '', 'MAILBOX_UID_MAX': None}) == (100000, 2000000000)


@pytest.mark.parametrize('env, message', [
    ({'MAILBOX_UID_MIN': 'abc'}, 'MAILBOX_UID_MIN must be an integer'),
    ({'MAILBOX_UID_MAX': '6e4'}, 'MAILBOX_UID_MAX must be an integer'),
    ({'MAILBOX_UID_MIN': '1000'}, 'at least 10000'),
    ({'MAILBOX_UID_MAX': str(2**31)}, 'at most'),
    ({'MAILBOX_UID_MIN': '60000', 'MAILBOX_UID_MAX': '60000'}, 'must be lower'),
    ({'MAILBOX_UID_MIN': '60000', 'MAILBOX_UID_MAX': '10000'}, 'must be lower'),
])
def test_invalid_range(env, message):
    with pytest.raises(ValueError, match=message):
        mailbox.uid_range(env)


def test_range_may_include_reserved_ids():
    # A whole 65536-ID subuid block may be used; 65534/65535 are skipped.
    assert mailbox.uid_range({'MAILBOX_UID_MIN': '10000', 'MAILBOX_UID_MAX': '65535'}) == (10000, 65535)


@pytest.mark.parametrize('uid, ok', [
    (9999, False), (10000, True), (65533, True), (65534, False), (65535, False), (65536, False),
])
def test_valid_uid(uid, ok):
    assert mailbox.valid_uid(uid, 10000, 65535) is ok


def test_provision_rejects_reserved_uid(tmp_path, monkeypatch):
    monkeypatch.setattr(mailbox, 'MIN_UID', 10000)
    monkeypatch.setattr(mailbox, 'MAX_UID', 65535)
    with pytest.raises(ValueError, match='Invalid mailbox identity'):
        mailbox.provision({'home': '/mail/./example.com/ab/alice', 'uid': 65534, 'gid': 65534}, str(tmp_path))


# --- admin configuration ----------------------------------------------------

def test_config_reads_range(env_setup, monkeypatch):
    monkeypatch.setenv('MAILBOX_UID_MIN', '10000')
    monkeypatch.setenv('MAILBOX_UID_MAX', '60000')
    app = create_app_from_config(configuration.ConfigManager())
    assert app.config['MAILBOX_UID_RANGE'] == (10000, 60000)
    assert app.config['MAILBOX_UID_MIN'] == 10000


def test_config_rejects_invalid_range(env_setup, monkeypatch):
    monkeypatch.setenv('MAILBOX_UID_MIN', '500')
    with pytest.raises(ValueError, match='at least 10000'):
        create_app_from_config(configuration.ConfigManager())


# --- UID assignment ---------------------------------------------------------

def _add_users(count, prefix='u'):
    if not models.db.session.get(models.Domain, 'example.com'):
        models.db.session.add(models.Domain(name='example.com'))
    users = []
    for i in range(count):
        user = models.User(localpart=f'{prefix}{i}', domain_name='example.com')
        user.set_password('password')
        models.db.session.add(user)
        models.db.session.commit()
        users.append(user)
    return users


def test_new_uid_in_default_range(app):
    with app.app_context():
        user, = _add_users(1)
        assert 100000 <= user.dovecot_uid <= 2000000000


def test_new_uids_fill_small_range_without_collision(app):
    app.config['MAILBOX_UID_RANGE'] = (10000, 10004)
    with app.app_context():
        uids = [user.dovecot_uid for user in _add_users(5)]
        assert sorted(uids) == [10000, 10001, 10002, 10003, 10004]


def test_new_uid_skips_reserved(app):
    app.config['MAILBOX_UID_RANGE'] = (65533, 65535)
    with app.app_context():
        user, = _add_users(1)
        assert user.dovecot_uid == 65533


def test_new_uid_finds_last_free_one(app, monkeypatch):
    # Random draws that keep hitting taken IDs fall back to the lowest free one.
    app.config['MAILBOX_UID_RANGE'] = (10000, 10009)
    with app.app_context():
        _add_users(9)
        free = ({*range(10000, 10010)} - {u.dovecot_uid for u in models.User.query}).pop()
        taken = min({u.dovecot_uid for u in models.User.query})
        monkeypatch.setattr(models.secrets, 'randbelow', lambda n: taken - 10000)
        user, = _add_users(1, prefix='last')
        assert user.dovecot_uid == free


def test_new_uid_fails_when_range_is_full(app):
    app.config['MAILBOX_UID_RANGE'] = (10000, 10001)
    with app.app_context():
        _add_users(2)
        # SQLAlchemy wraps errors raised by column defaults.
        with pytest.raises(sa.exc.StatementError, match='No free mailbox UID'):
            _add_users(1, prefix='late')
        models.db.session.rollback()


# --- start-up check -----------------------------------------------------------

def test_check_mailbox_uids_passes(app):
    with app.app_context():
        _add_users(2)
    result = app.test_cli_runner().invoke(args=['mailu', 'check-mailbox-uids'])
    assert result.exit_code == 0, result.output
    assert 'within 100000-2000000000' in result.output


def test_check_mailbox_uids_fails_outside_range(app):
    with app.app_context():
        _add_users(1)
    app.config['MAILBOX_UID_RANGE'] = (10000, 60000)
    result = app.test_cli_runner().invoke(args=['mailu', 'check-mailbox-uids'])
    assert result.exit_code != 0
    assert 'u0@example.com' in result.output
    assert '1 mailbox(es) have a UID outside' in result.output


# --- migration b5e8d1a4c2f0 ---------------------------------------------------

MIGRATION = (
    pathlib.Path(models.__file__).resolve().parent.parent
    / 'migrations' / 'versions' / 'b5e8d1a4c2f0_dovecot_mailbox_identity.py'
)


def _run_migration(app, emails, uid_range, engine=None):
    """Run upgrade() on a minimal pre-migration schema; return {email: uid}."""
    spec = importlib.util.spec_from_file_location('mig_b5e8d1a4c2f0', MIGRATION)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    app.config['MAILBOX_UID_RANGE'] = uid_range
    engine = engine or sa.create_engine('sqlite://')
    with engine.connect() as conn, app.app_context():
        conn.exec_driver_sql('CREATE TABLE domain (name VARCHAR(80) PRIMARY KEY)')
        conn.exec_driver_sql(
            'CREATE TABLE "user" (email VARCHAR(255) PRIMARY KEY, domain_name VARCHAR(80))'
        )
        for email in emails:
            conn.exec_driver_sql(
                'INSERT INTO "user" (email, domain_name) VALUES (?, ?)', (email, 'example.com')
            )
        mig.op = Operations(MigrationContext.configure(conn))
        with conn.begin_nested() if conn.in_transaction() else conn.begin():
            mig.upgrade()
        return dict(conn.exec_driver_sql('SELECT email, dovecot_uid FROM "user"').fetchall())


def test_migration_numbers_from_configured_min(app):
    uids = _run_migration(app, ['b@example.com', 'a@example.com'], (10000, 60000))
    assert uids == {'a@example.com': 10000, 'b@example.com': 10001}


def test_migration_default_range_unchanged(app):
    uids = _run_migration(app, ['a@example.com'], (100000, 2000000000))
    assert uids == {'a@example.com': 100000}


def test_migration_skips_reserved(app):
    uids = _run_migration(app, ['a@example.com', 'b@example.com'], (65533, 65536))
    assert uids == {'a@example.com': 65533, 'b@example.com': 65536}


def test_migration_fails_when_range_too_small(app, tmp_path):
    # Fails before any schema change, so a retry with a wider range works
    # (SQLite DDL is not rolled back).
    engine = sa.create_engine(f'sqlite:///{tmp_path}/main.db')
    emails = ['a@example.com', 'b@example.com']
    with pytest.raises(RuntimeError, match='2 mailboxes do not fit .* 1 usable IDs'):
        _run_migration(app, emails, (65533, 65535), engine)
    with engine.connect() as conn:
        assert 'dovecot_uid' not in {c['name'] for c in sa.inspect(conn).get_columns('user')}
        assert 'max_domain_quota_bytes' not in {c['name'] for c in sa.inspect(conn).get_columns('domain')}
        conn.exec_driver_sql('DROP TABLE "user"')
        conn.exec_driver_sql('DROP TABLE domain')
        conn.commit()
    assert _run_migration(app, emails, (65533, 65536), engine) == {
        'a@example.com': 65533, 'b@example.com': 65536}
