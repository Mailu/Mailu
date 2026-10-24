"""Configuration regressions for BURL through the front submission proxy."""

from pathlib import Path
import re

from mailu.internal.nginx import get_server


ROOT = Path(__file__).resolve().parents[2]


def test_authenticated_submission_is_proxied_to_storage_dovecot(app, monkeypatch):
    monkeypatch.setitem(app.config, 'IMAP_ADDRESS', '192.0.2.10')
    monkeypatch.setitem(app.config, 'SMTP_ADDRESS', '192.0.2.20')

    with app.app_context():
        assert get_server('submission', authenticated=True) == ('192.0.2.10', 2587)


def test_front_accepts_the_public_urlauth_host():
    config = (ROOT / 'core/nginx/dovecot/proxy.conf').read_text()

    assert 'imap_urlauth_host = {{ HOSTNAMES.split(",")[0] }}' in config
    assert re.search(r'imap_capability\s*\{\s*METADATA = yes\s*URLAUTH = yes', config)


def test_front_proxies_submission_auth_to_storage_dovecot():
    config = (ROOT / 'core/nginx/dovecot/login.lua').read_text()
    branch = re.search(
        r'elseif req\.protocol == "submission" then(.*?)(?:\n\s*else|\n\s*end)',
        config,
        re.DOTALL,
    ).group(1)

    assert 'reply.proxy_mech = "PLAIN"' in branch
    assert 'reply.proxy_noauth' not in branch


def test_snappymail_exposes_supported_imap_metadata_and_preview():
    config = (ROOT / 'webmails/snappymail/defaults/default.json').read_text()
    disabled = re.search(r'"disabled_capabilities": \[(.*?)\]', config, re.DOTALL).group(1)

    assert '"METADATA"' not in disabled
    assert '"PREVIEW"' not in disabled
    assert '"OBJECTID"' in disabled
    assert '"STATUS=SIZE"' in disabled
