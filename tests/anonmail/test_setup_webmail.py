"""The setup wizard can generate deployments with or without webmail."""
from pathlib import Path

import jinja2
import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('enabled', [True, False])
@pytest.mark.parametrize('admin_enabled', [True, False])
def test_setup_webmail_is_consistent(enabled, admin_enabled):
    environment = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    environment.globals['secret'] = lambda length: 'x' * length
    context = {
        'webmail_enabled': enabled,
        'admin_enabled': admin_enabled,
        'root': '/mailu',
        'version': 'test',
        'flavor': 'compose',
        'subnet': '192.168.203.0/24',
        'auth_ratelimit_ip': '0',
        'auth_ratelimit_user': '0',
        'message_ratelimit_pd': '0',
    }
    compose_template = (ROOT / 'setup/flavors/compose/docker-compose.yml').read_text()
    env_template = (ROOT / 'setup/flavors/compose/mailu.env').read_text()
    compose = yaml.safe_load(environment.from_string(compose_template).render(context))
    settings = environment.from_string(env_template).render(context)
    if enabled:
        assert '/mailu/overrides/roundcube:/roundcube-overrides:ro' in compose['services']['webmail']['volumes']
        assert '/mailu/overrides/snappymail:/snappymail-overrides:ro' in compose['services']['webmail']['volumes']
    assert ('webmail' in compose['services']) is enabled
    assert ('webmail' in compose['networks']) is enabled
    assert ('webmail' in compose['services']['front']['networks']) is enabled
    assert ('WEBMAIL_AVAILABLE=roundcube,snappymail' if enabled else 'WEBMAIL_AVAILABLE=none') in settings
    redirect = '/webmail' if enabled else ('/admin' if admin_enabled else 'none')
    assert f'WEBROOT_REDIRECT={redirect}' in settings
