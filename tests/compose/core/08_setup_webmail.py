"""Render setup templates in the admin image used by the Compose test."""
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
templates = {
    'compose': (ROOT / 'setup/flavors/compose/docker-compose.yml').read_text(),
    'env': (ROOT / 'setup/flavors/compose/mailu.env').read_text(),
}

# The host test runner installs only its own dependencies; Jinja and PyYAML
# are already installed in the running admin image.
script = r'''
import json
import sys
import jinja2
import yaml

templates = json.load(sys.stdin)
environment = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
environment.globals['secret'] = lambda length: 'x' * length
for enabled in (True, False):
    for admin_enabled in (True, False):
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
        compose = yaml.safe_load(environment.from_string(templates['compose']).render(context))
        settings = environment.from_string(templates['env']).render(context)
        if enabled:
            volumes = compose['services']['webmail']['volumes']
            assert '/mailu/overrides/roundcube:/roundcube-overrides:ro' in volumes
            assert '/mailu/overrides/snappymail:/snappymail-overrides:ro' in volumes
        assert ('webmail' in compose['services']) is enabled
        assert ('webmail' in compose['networks']) is enabled
        assert ('webmail' in compose['services']['front']['networks']) is enabled
        assert ('WEBMAIL_AVAILABLE=roundcube,snappymail' if enabled else 'WEBMAIL_AVAILABLE=none') in settings
        redirect = '/webmail' if enabled else ('/admin' if admin_enabled else 'none')
        assert f'WEBROOT_REDIRECT={redirect}' in settings
print('Setup webmail variants rendered successfully')
'''
subprocess.run(
    ['docker', 'exec', '-i', os.environ.get('MAILU_TEST_ADMIN_CONTAINER', 'core-admin-1'),
     '/app/venv/bin/python', '-c', script],
    input=json.dumps(templates), text=True, check=True,
)
