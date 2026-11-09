"""Mailbox creation protects existing homes and rejects path traversal."""
import os

import pytest
from socrate import mailbox


@pytest.fixture
def fields(monkeypatch, tmp_path):
    tmp_path.chmod(0o711)
    monkeypatch.setattr(mailbox, 'MIN_UID', 0)
    return {'home': '/mail/./example.com/ab/alice', 'uid': os.getuid(), 'gid': os.getgid()}


def test_create_and_reuse_home(tmp_path, fields):
    mailbox.provision(fields, str(tmp_path))
    home = tmp_path / 'example.com/ab/alice'
    assert home.is_dir()
    assert all(path.stat().st_mode & 0o777 == 0o711 for path in (tmp_path, tmp_path / 'example.com', tmp_path / 'example.com/ab'))
    assert home.stat().st_mode & 0o777 == 0o700
    mailbox.provision(fields, str(tmp_path))


@pytest.mark.parametrize('home', ['/mail/./../ab/alice', '/mail/./example.com/ab/..',
                                  '/mail/./example.com/ab//extra', '/etc/passwd'])
def test_reject_invalid_home(tmp_path, fields, home):
    fields['home'] = home
    with pytest.raises(ValueError):
        mailbox.provision(fields, str(tmp_path))


def test_reject_symlink_parent(tmp_path, fields):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'example.com').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        mailbox.provision(fields, str(tmp_path))
    assert not list(outside.iterdir())


def test_reject_symlink_home(tmp_path, fields):
    parent = tmp_path / 'example.com/ab'
    parent.mkdir(parents=True)
    parent.parent.chmod(0o711)
    parent.chmod(0o711)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (parent / 'alice').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        mailbox.provision(fields, str(tmp_path))
    assert not list(outside.iterdir())


def test_reject_unsafe_existing_home(tmp_path, fields):
    mailbox.provision(fields, str(tmp_path))
    home = tmp_path / 'example.com/ab/alice'
    home.chmod(0o755)
    with pytest.raises(PermissionError):
        mailbox.provision(fields, str(tmp_path))
    assert home.stat().st_mode & 0o777 == 0o755


def test_reject_inaccessible_existing_parent(tmp_path, fields):
    parent = tmp_path / 'example.com'
    parent.mkdir(mode=0o700)
    with pytest.raises(PermissionError):
        mailbox.provision(fields, str(tmp_path))


def test_reject_invalid_identity(tmp_path, fields):
    fields['uid'] = -1
    with pytest.raises(ValueError):
        mailbox.provision(fields, str(tmp_path))
    assert not list(tmp_path.iterdir())


def test_reject_writable_mail_root(tmp_path, fields):
    tmp_path.chmod(0o777)
    with pytest.raises(PermissionError):
        mailbox.provision(fields, str(tmp_path))
    assert not list(tmp_path.iterdir())


def test_harden_existing_parents_without_touching_mailbox(tmp_path, fields):
    mailbox.provision(fields, str(tmp_path))
    domain = tmp_path / 'example.com'
    shard = domain / 'ab'
    home = shard / 'alice'
    tmp_path.chmod(0o755)
    domain.chmod(0o755)
    shard.chmod(0o755)
    mailbox.harden_parents([fields['home']], str(tmp_path))
    assert all(path.stat().st_mode & 0o777 == 0o711 for path in (tmp_path, domain, shard))
    assert home.stat().st_mode & 0o777 == 0o700


def test_reject_readable_mail_root(tmp_path, fields):
    tmp_path.chmod(0o755)
    with pytest.raises(PermissionError):
        mailbox.provision(fields, str(tmp_path))


def test_hardening_rejects_symlink_parent(tmp_path, fields):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'example.com').symlink_to(outside, target_is_directory=True)
    original_mode = outside.stat().st_mode
    with pytest.raises(OSError):
        mailbox.harden_parents([fields['home']], str(tmp_path))
    assert outside.stat().st_mode == original_mode


def test_nested_safe_components_are_traversal_only(tmp_path, fields):
    fields['home'] = '/mail/./example.com/ab/alice/sub'
    mailbox.provision(fields, str(tmp_path))
    parent = tmp_path / 'example.com/ab/alice'
    assert parent.stat().st_mode & 0o777 == 0o711
    assert (parent / 'sub').stat().st_mode & 0o777 == 0o700


def test_harden_parents_once_skips_future_user_scans(tmp_path, fields):
    mailbox.provision(fields, str(tmp_path))
    calls = []

    def fetch_homes():
        calls.append(True)
        return [fields['home']]

    mailbox.harden_parents_once(fetch_homes, str(tmp_path))
    mailbox.harden_parents_once(fetch_homes, str(tmp_path))
    assert len(calls) == 1
    assert (tmp_path / '.mail-parents-protected-v1').is_file()


def test_harden_parents_once_retries_after_failure(tmp_path, fields):
    def fail():
        raise RuntimeError('userdb unavailable')

    with pytest.raises(RuntimeError):
        mailbox.harden_parents_once(fail, str(tmp_path))
    assert not (tmp_path / '.mail-parents-protected-v1').exists()
    mailbox.harden_parents_once(lambda: [fields['home']], str(tmp_path))
    assert (tmp_path / '.mail-parents-protected-v1').is_file()
