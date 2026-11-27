"""The admin start script must pass every sensitive setting to Gunicorn.

socrate.supervisor strips environment variables whose names look sensitive
(``*SECRET*``, ``*_KEY``, ``*_TOKEN`` ...) and hands each program only the
secrets start.py lists for it. A sensitive setting missing from that list is
silently unset inside the running admin app.
"""

import ast
import os

from socrate.supervisor import _is_sensitive

from mailu.configuration import DEFAULT_CONFIG


# The repository copy, or the copy in the admin image where CI runs the tests.
START_PY = next(path for path in (
    os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'admin', 'start.py'),
    '/start.py',
) if os.path.exists(path))


def _admin_secrets():
    tree = ast.parse(open(START_PY).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) == 'admin_secrets':
            return {
                child.value for child in ast.walk(node.value)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            }
    raise AssertionError('admin_secrets not found in start.py')


def test_every_sensitive_admin_setting_reaches_the_admin_process():
    allowed = _admin_secrets()
    sensitive = {key for key in DEFAULT_CONFIG if _is_sensitive(key)}
    assert 'KEYCLOAK_CLIENT_SECRET' in sensitive
    assert sensitive - allowed == set()
    # Settings read from files (KEY_FILE) are sensitive too.
    assert {f'{key}_FILE' for key in sensitive if key != 'QUARANTINE_KEY'} - allowed == set()
