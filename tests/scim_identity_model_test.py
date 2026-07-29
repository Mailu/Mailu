"""Focused model and migration tests for persistent SCIM identity.

These tests deliberately stay below the HTTP API.  They prove that identity,
graph, deletion, and authority invariants exist at the model/migration layer
instead of depending on one endpoint remembering a convention.
"""

import importlib.util
import pathlib
import re
import threading
import unicodedata

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from mailu import models, utils


MIGRATIONS = pathlib.Path(models.__file__).resolve().parent.parent / 'migrations' / 'versions'
IDENTITY_MIGRATION = MIGRATIONS / 'e7c9a4f2b631_.py'
ADDRESS_MIGRATION = MIGRATIONS / 'd4a6f2b8c901_.py'
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-'
    r'[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)


def _domain(name='example.com'):
    domain = models.db.session.get(models.Domain, name)
    if domain is None:
        domain = models.Domain(name=name)
        models.db.session.add(domain)
        models.db.session.commit()
    return domain


def _user(localpart, domain=None):
    user = models.User(localpart=localpart, domain=domain or _domain())
    user.set_password('not-a-real-password')
    models.db.session.add(user)
    models.db.session.commit()
    return user


def _alias(localpart, *, domain=None, destination=None, **values):
    alias = models.Alias(
        localpart=localpart,
        domain=domain or _domain(),
        destination=destination or ['outside@example.net'],
        **values,
    )
    models.db.session.add(alias)
    models.db.session.commit()
    return alias


def _managed_group(localpart, *, destination=None):
    alias = _alias(localpart, destination=destination)
    resource = models.ScimResource(
        id=models.new_scim_id(),
        resource_type='Group',
        alias_email=alias.email,
        subject_address=alias.email,
    )
    models.db.session.add(resource)
    models.db.session.commit()
    return resource


def test_sqlite_foreign_keys_are_enabled_without_fixture_pragma(app):
    engine = sa.create_engine('sqlite://')
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                'PRAGMA foreign_keys'
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_address_conflict_preserves_integrity_error_contract():
    assert issubclass(models.AddressConflict, IntegrityError)


def test_new_orm_user_gets_random_generation_and_uuid_mapping(app):
    user = _user('new-identity')
    mapping = models.ScimResource.query.filter_by(
        resource_type='User',
        user_email=user.email,
        deleted_at=None,
    ).one()

    assert user.auth_generation != utils.INITIAL_AUTH_GENERATION
    assert re.fullmatch(r'[0-9a-f]{32}', user.auth_generation)
    assert UUID_PATTERN.fullmatch(mapping.id)
    assert mapping.subject_address == user.email
    assert mapping.external_id is None
    assert models.db.session.get(models.ScimState, 1).revision == 0


def test_user_mapping_helper_reuses_automatic_mapping(app):
    user = _user('mapping-helper')
    automatic = user.scim_resource

    assert models.create_scim_user_mapping(
        user,
        external_id='upstream-42',
    ) is automatic
    assert automatic.external_id == 'upstream-42'
    assert models.create_scim_user_mapping(
        user,
        resource_id=automatic.id,
    ) is automatic
    with pytest.raises(models.ScimIdentityError, match='different'):
        models.create_scim_user_mapping(
            user,
            resource_id=models.new_scim_id(),
        )


def test_hard_delete_recreate_cannot_reuse_identity_or_session_generation(app):
    user = _user('recreated')
    old_generation = user.auth_generation
    old_mapping = user.scim_resource
    old_id = old_mapping.id

    models.db.session.delete(user)
    models.db.session.commit()

    tombstone = models.db.session.get(models.ScimResource, old_id)
    assert tombstone.deleted_at is not None
    assert tombstone.user_email is None
    assert tombstone.subject_address == 'recreated@example.com'

    replacement = _user('recreated')
    assert replacement.auth_generation != old_generation
    assert replacement.scim_resource.id != old_id
    assert models.db.session.get(models.ScimResource, old_id) is tombstone


def test_external_id_is_byte_exact_and_bounded(app):
    user = _user('external-id')
    mapping = user.scim_resource

    mapping.external_id = 'Case-Sensitive-é'
    models.db.session.commit()
    assert mapping.external_id == 'Case-Sensitive-é'
    assert mapping.external_id_bytes == 'Case-Sensitive-é'.encode()

    mapping.external_id = 'a' * 1024
    assert len(mapping.external_id_bytes) == 1024
    with pytest.raises(ValueError, match='1024'):
        mapping.external_id = 'é' * 513
    with pytest.raises(TypeError):
        mapping.external_id = b'not-a-string'


def test_exact_provider_id_lookup_rejects_case_variant(app):
    user = _user('exact-id')
    mapping = user.scim_resource

    assert models.ScimResource.get_exact(mapping.id) is mapping
    assert models.ScimResource.get_exact(mapping.id.upper()) is None


def test_scim_resource_hard_delete_is_rejected(app):
    user = _user('immutable-tombstone')
    resource_id = user.scim_resource.id

    models.db.session.delete(user.scim_resource)
    with pytest.raises(models.ScimIdentityError, match='tombstone'):
        models.db.session.commit()
    models.db.session.rollback()

    assert models.ScimResource.get_exact(resource_id) is not None


def test_scim_resource_principal_binding_is_immutable(app):
    alice = _user('binding-alice')
    bob = _user('binding-bob')
    mapping = alice.scim_resource

    mapping.user = bob
    with pytest.raises(models.ScimIdentityError, match='binding'):
        models.db.session.commit()
    models.db.session.rollback()

    assert mapping.user_email == alice.email


def test_scim_tombstone_cannot_be_resurrected_or_edited(app):
    user = _user('immutable-deleted-resource')
    mapping = user.scim_resource
    original_external_id = mapping.external_id
    models.tombstone_scim_resource(mapping, retain_subject=True)
    models.db.session.commit()
    deleted_at = mapping.deleted_at

    mapping.deleted_at = None
    mapping.user = user
    mapping.external_id = 'changed-after-delete'
    with pytest.raises(models.ScimIdentityError, match='tombstone'):
        models.db.session.commit()
    models.db.session.rollback()

    assert mapping.deleted_at == deleted_at
    assert mapping.user_email is None
    assert mapping.external_id == original_external_id


def test_scim_tombstone_scrubs_retained_user_authority(app):
    user = _user('authority')
    user_domain = user.domain
    user.global_admin = True
    user.allow_spoofing = True
    user.forward_enabled = True
    user.forward_destination = ['old-owner@example.net']
    user.reply_enabled = True
    managed_domain = _domain('managed.example')
    models.db.session.execute(
        models.managers.insert().values(
            domain_name=managed_domain.name,
            user_email=user.email,
        )
    )
    token = models.Token(user=user)
    token.set_password('a' * 32)
    access = models.DomainAccess(
        domain_name='managed.example',
        user=user,
    )
    owned_alias = models.Alias(
        localpart='old-owner-alias',
        domain=user_domain,
        owner=user,
        destination=[user.email],
    )
    fetch = models.Fetch(
        user=user,
        protocol='imap',
        host='mail.old-owner.example',
        port=993,
        tls=True,
        username='old-owner',
        password='remote-secret',
    )
    models.db.session.add_all([token, access, owned_alias, fetch])
    models.db.session.commit()
    mapping = user.scim_resource

    models.tombstone_scim_resource(
        mapping,
        retain_subject=True,
        scrub_user_authority=True,
    )
    models.db.session.commit()

    assert mapping.deleted_at is not None
    assert mapping.user_email is None
    assert user.enabled is False
    assert user.global_admin is False
    assert user.allow_spoofing is False
    assert user.forward_enabled is False
    assert user.forward_destination == []
    assert user.reply_enabled is False
    assert models.Token.query.filter_by(user_email=user.email).count() == 0
    assert models.Fetch.query.filter_by(user_email=user.email).count() == 0
    assert models.Alias.query.filter_by(owner_email=user.email).count() == 0
    assert models.DomainAccess.query.filter_by(user_email=user.email).count() == 0
    assert models.db.session.execute(
        sa.select(sa.func.count()).select_from(models.managers).where(
            models.managers.c.user_email == user.email
        )
    ).scalar_one() == 0


def test_deleted_user_address_cannot_receive_a_new_scim_identity(app):
    user = _user('reserved-authority')
    mapping = user.scim_resource

    models.tombstone_scim_resource(
        mapping,
        retain_subject=True,
        scrub_user_authority=True,
    )
    models.db.session.commit()

    with pytest.raises(
        models.ScimIdentityError,
        match='permanently reserved',
    ):
        models.create_scim_user_mapping(user)


@pytest.mark.parametrize(
    'values',
    [
        {'disabled': True},
        {'wildcard': True},
    ],
)
def test_group_adoption_rejects_ineligible_alias_state(app, values):
    alias = _alias('ineligible', **values)
    with pytest.raises(models.ScimGroupAdoptionError):
        models.validate_scim_group_adoption(alias)


def test_group_adoption_rejects_owned_alias(app):
    owner = _user('owner')
    alias = _alias('owned', owner=owner)
    with pytest.raises(models.ScimGroupAdoptionError):
        models.validate_scim_group_adoption(alias)


def test_managed_alias_ordinary_edit_is_blocked_but_one_shot_edit_is_allowed(app):
    group = _managed_group('managed-edit')
    alias = group.alias

    alias.comment = 'ordinary edit'
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()

    alias = models.db.session.get(models.Alias, 'managed-edit@example.com')
    models.permit_scim_managed_alias_edit(alias)
    alias.comment = 'SCIM edit'
    models.db.session.commit()
    assert alias.comment == 'SCIM edit'


def test_managed_alias_destination_edit_is_blocked(app):
    group = _managed_group('managed-destination')
    alias = group.alias

    alias.destination = ['other@example.net']
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()


def test_managed_alias_ordinary_delete_is_blocked(app):
    group = _managed_group('managed-delete')
    resource_id = group.id
    alias_email = group.alias.email

    models.db.session.delete(group.alias)
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()

    assert models.db.session.get(models.Alias, alias_email) is not None
    assert models.ScimResource.get_exact(resource_id) is not None


def test_managed_alias_edit_permit_does_not_survive_rollback(app):
    group = _managed_group('managed-rollback')
    alias = group.alias
    models.permit_scim_managed_alias_edit(alias)
    alias.comment = 'permitted but rolled back'
    models.db.session.rollback()

    alias = models.db.session.get(models.Alias, alias.email)
    alias.comment = 'ordinary edit after rollback'
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()


def test_graph_materialization_uses_ids_and_rejects_local_external_values(app):
    member = _user('member')
    group = _managed_group('graph')

    models.replace_scim_group_graph(
        group,
        member_ids=[member.scim_resource.id],
        external_destinations=['pager@outside.test'],
    )
    models.db.session.commit()

    assert group.alias.destination == [
        'member@example.com',
        'pager@outside.test',
    ]
    assert {(edge.group_id, edge.member_id) for edge in group.member_edges} == {
        (group.id, member.scim_resource.id)
    }

    with pytest.raises(models.ScimExternalDestinationError):
        models.replace_scim_group_graph(
            group,
            member_ids=[],
            external_destinations=['member@example.com'],
        )
    models.db.session.rollback()


@pytest.mark.parametrize(
    'destination',
    [
        'foo bar@example.com',
        'foo..bar@example.com',
        '.foo@example.com',
    ],
)
def test_external_destination_rejects_malformed_localpart(app, destination):
    with pytest.raises(models.ScimExternalDestinationError):
        models.canonicalize_scim_destination(destination)


def test_external_destination_reservation_blocks_later_local_address(app):
    group = _managed_group('external-reservation')
    models.replace_scim_group_graph(
        group,
        member_ids=[],
        external_destinations=['future@future.example'],
    )
    models.db.session.commit()

    domain = _domain('future.example')
    candidate = models.User(localpart='future', domain=domain)
    candidate.set_password('not-a-real-password')
    models.db.session.add(candidate)
    with pytest.raises(models.AddressConflict):
        models.db.session.commit()
    models.db.session.rollback()


def test_mysql_external_reservation_sees_local_commit_after_old_snapshot(app):
    if models.db.engine.dialect.name != 'mysql':
        pytest.skip('requires MySQL/MariaDB REPEATABLE READ')

    group = _managed_group('snapshot-external')
    group_id = group.id
    _domain('future.example')
    models.db.session.remove()

    snapshot_ready = threading.Event()
    local_committed = threading.Event()
    outcome = []

    def reserve_external():
        with app.app_context():
            stale_group = models.db.session.get(
                models.ScimResource,
                group_id,
            )
            models.db.session.execute(sa.select(models.Domain)).all()
            snapshot_ready.set()
            assert local_committed.wait(timeout=10)
            try:
                models.replace_scim_group_graph(
                    stale_group,
                    member_ids=[],
                    external_destinations=['future@future.example'],
                )
                models.db.session.commit()
            except models.ScimExternalDestinationError:
                models.db.session.rollback()
                outcome.append('conflict')
            else:
                outcome.append('reserved')
            finally:
                models.db.session.remove()

    worker = threading.Thread(target=reserve_external)
    worker.start()
    assert snapshot_ready.wait(timeout=10)

    domain = models.db.session.get(models.Domain, 'future.example')
    candidate = models.User(localpart='future', domain=domain)
    candidate.set_password('not-a-real-password')
    models.db.session.add(candidate)
    models.db.session.commit()
    local_committed.set()
    worker.join(timeout=15)

    assert not worker.is_alive()
    assert outcome == ['conflict']
    assert models.db.session.get(
        models.User,
        'future@future.example',
    ) is not None
    assert models.ScimGroupDestination.query.filter_by(
        destination='future@future.example',
    ).count() == 0


def test_mysql_local_claim_sees_external_commit_after_old_snapshot(app):
    if models.db.engine.dialect.name != 'mysql':
        pytest.skip('requires MySQL/MariaDB REPEATABLE READ')

    group = _managed_group('snapshot-local')
    group_id = group.id
    domain = _domain('future.example')
    models.db.session.execute(sa.select(models.Domain)).all()

    def reserve_external():
        with app.app_context():
            current_group = models.db.session.get(
                models.ScimResource,
                group_id,
            )
            models.replace_scim_group_graph(
                current_group,
                member_ids=[],
                external_destinations=['future@future.example'],
            )
            models.db.session.commit()
            models.db.session.remove()

    worker = threading.Thread(target=reserve_external)
    worker.start()
    worker.join(timeout=15)
    assert not worker.is_alive()

    candidate = models.User(localpart='future', domain=domain)
    candidate.set_password('not-a-real-password')
    models.db.session.add(candidate)
    with pytest.raises(models.AddressConflict):
        models.db.session.commit()
    models.db.session.rollback()

    assert models.db.session.get(
        models.User,
        'future@future.example',
    ) is None
    assert models.ScimGroupDestination.query.filter_by(
        destination='future@future.example',
    ).count() == 1


def test_group_cycle_is_rejected_before_materialization(app):
    first = _managed_group('cycle-a')
    second = _managed_group('cycle-b')
    original_projection = list(first.alias.destination)
    models.replace_scim_group_graph(
        second,
        member_ids=[first.id],
        external_destinations=[],
    )
    models.db.session.commit()

    with pytest.raises(models.ScimGraphError):
        models.replace_scim_group_graph(
            first,
            member_ids=[second.id],
            external_destinations=[],
        )
    models.db.session.rollback()
    assert first.alias.destination == original_projection


def test_hard_deleted_member_is_tombstoned_and_removed_from_group(app):
    member = _user('departing')
    member_id = member.scim_resource.id
    group = _managed_group('member-delete')
    models.replace_scim_group_graph(
        group,
        member_ids=[member_id],
        external_destinations=['outside@example.net'],
    )
    models.db.session.commit()

    models.db.session.delete(member)
    models.db.session.commit()

    tombstone = models.db.session.get(models.ScimResource, member_id)
    assert tombstone.deleted_at is not None
    assert models.ScimGroupMember.query.filter_by(member_id=member_id).count() == 0
    assert group.alias.destination == ['outside@example.net']


def _load_migration(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity_legacy_engine():
    engine = sa.create_engine('sqlite://')
    metadata = sa.MetaData()
    sa.Table(
        'user',
        metadata,
        sa.Column('email', sa.String(255), primary_key=True),
        sa.Column('created_at', sa.Date, nullable=False),
        sa.Column('updated_at', sa.Date),
    )
    sa.Table(
        'alias',
        metadata,
        sa.Column('email', sa.String(255), primary_key=True),
        sa.Column(
            'owner_email',
            sa.String(255),
            sa.ForeignKey('user.email'),
        ),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO user (email, created_at, updated_at) VALUES "
            "('alice@example.com', '2024-01-02', NULL),"
            "('idna@xn--bcher-kva.example', '2024-01-03', '2024-01-04')"
        )
        connection.exec_driver_sql(
            "INSERT INTO alias (email, owner_email) VALUES "
            "('ordinary@example.com', 'alice@example.com')"
        )
    return engine


def _run_migration(engine, operation, *, destructive=False):
    migration = _load_migration(
        IDENTITY_MIGRATION,
        f'scim_identity_migration_{operation}_{destructive}',
    )
    x_arguments = []
    if destructive:
        x_arguments = [
            'allow_destructive_scim_identity=true',
            'scim_identity_exported=true',
        ]
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={'x_argument': x_arguments},
        )
        migration.op = Operations(context)
        with connection.begin():
            getattr(migration, operation)()


def test_identity_migration_backfills_users_only_and_gates_downgrade():
    engine = _identity_legacy_engine()
    _run_migration(engine, 'upgrade')

    inspector = sa.inspect(engine)
    assert {
        'scim_state',
        'scim_resource',
        'scim_group_member',
        'scim_group_destination',
    } <= set(inspector.get_table_names())
    assert 'auth_generation' in {
        column['name'] for column in inspector.get_columns('user')
    }

    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            'SELECT id, resource_type, user_email, alias_email '
            'FROM scim_resource ORDER BY user_email'
        ).all() == [
            ('alice@example.com', 'User', 'alice@example.com', None),
            (
                'idna@bücher.example',
                'User',
                'idna@xn--bcher-kva.example',
                None,
            ),
        ]
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM scim_resource WHERE resource_type='Group'"
        ).scalar_one() == 0
        assert connection.exec_driver_sql(
            'SELECT id, revision FROM scim_state'
        ).all() == [(1, 0)]
        assert set(connection.exec_driver_sql(
            'SELECT auth_generation FROM user'
        ).scalars()) == {utils.INITIAL_AUTH_GENERATION}
        assert connection.exec_driver_sql(
            'PRAGMA foreign_key_check'
        ).all() == []

    with pytest.raises(RuntimeError, match='identity export'):
        _run_migration(engine, 'downgrade')
    assert 'scim_resource' in sa.inspect(engine).get_table_names()

    _run_migration(engine, 'downgrade', destructive=True)
    inspector = sa.inspect(engine)
    assert 'scim_resource' not in inspector.get_table_names()
    assert 'auth_generation' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            'SELECT email, owner_email FROM alias'
        ).all() == [('ordinary@example.com', 'alice@example.com')]
        assert connection.exec_driver_sql(
            'PRAGMA foreign_key_check'
        ).all() == []
    engine.dispose()


def test_address_preflight_uses_native_database_collation():
    engine = sa.create_engine('sqlite://')

    def accent_insensitive(left, right):
        def normalized(value):
            decomposed = unicodedata.normalize('NFKD', value)
            return ''.join(
                char for char in decomposed
                if not unicodedata.combining(char)
            ).casefold()

        return (normalized(left) > normalized(right)) - (
            normalized(left) < normalized(right)
        )

    @sa.event.listens_for(engine, 'connect')
    def install_collation(connection, _record):
        connection.create_collation('mailu_ai', accent_insensitive)

    metadata = sa.MetaData()
    sa.Table(
        'user',
        metadata,
        sa.Column(
            'email',
            sa.String(255, collation='mailu_ai'),
            primary_key=True,
        ),
    )
    sa.Table(
        'alias',
        metadata,
        sa.Column(
            'email',
            sa.String(255, collation='mailu_ai'),
            primary_key=True,
        ),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO user (email) VALUES ('cafe@example.com')"
        )
        connection.exec_driver_sql(
            "INSERT INTO alias (email) VALUES ('café@example.com')"
        )

    migration = _load_migration(
        ADDRESS_MIGRATION,
        'address_native_collation_preflight',
    )
    with engine.connect() as connection:
        collisions = migration._cross_table_collisions(connection)
    assert collisions == [
        ('cafe@example.com', 'cafe@example.com', 'café@example.com')
    ]
    engine.dispose()


def test_address_migration_rebuilds_inbound_user_fks_only_on_sqlite():
    migration = _load_migration(
        ADDRESS_MIGRATION,
        'mail_address_backend_branching',
    )

    class Connection:
        def __init__(self, dialect_name):
            self.dialect = type('Dialect', (), {'name': dialect_name})()

    assert migration._requires_sqlite_reference_rebuild(
        Connection('sqlite')
    ) is True
    assert migration._requires_sqlite_reference_rebuild(
        Connection('postgresql')
    ) is False
    assert migration._requires_sqlite_reference_rebuild(
        Connection('mariadb')
    ) is False
