"""Exercise actual Radicale storage, provisioning and DAV isolation."""
import importlib.util
from pathlib import Path

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

radicale = pytest.importorskip('radicale')
from radicale import config, storage
from radicale.app import Application

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('run_radicale', ROOT / 'optional/radicale/run_radicale.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture
def dav_config(tmp_path):
    configuration = config.load([(str(ROOT / 'optional/radicale/radicale.conf'), False)])
    configuration.update({'storage': {'filesystem_folder': str(tmp_path)}})
    return configuration


def test_provisioning_preserves_existing_books_and_contacts(dav_config):
    backend = storage.load(dav_config)
    with backend.acquire_lock('w'):
        backend.create_collection('/empty/')
        backend.create_collection('/existing/')
        backend.create_collection('/existing/personal/', props={
            'tag': 'VADDRESSBOOK', 'D:displayname': 'My contacts',
        })
        backend.create_collection('/calendar-only/')
        backend.create_collection('/calendar-only/calendar/', props={'tag': 'VCALENDAR'})
    for _ in range(2):
        runner.provision_addressbooks(dav_config)
    with backend.acquire_lock('r'):
        assert next(backend.discover('/empty/contacts/')).get_meta('tag') == 'VADDRESSBOOK'
        assert next(backend.discover('/calendar-only/contacts/')).get_meta('tag') == 'VADDRESSBOOK'
        assert next(backend.discover('/calendar-only/calendar/')).get_meta('tag') == 'VCALENDAR'
        assert next(backend.discover('/existing/personal/')).get_meta('D:displayname') == 'My contacts'
        assert not list(backend.discover('/existing/contacts/'))


def test_new_user_gets_contacts_and_dav_rights_remain_private(dav_config):
    client = Client(Application(dav_config), Response)
    alice = {'X-Remote-User': 'alice@example.org'}
    response = client.open('/alice@example.org/', method='PROPFIND', headers={**alice, 'Depth': '1'})
    assert response.status_code == 207
    assert '/alice%40example.org/contacts/' in response.text
    card = 'BEGIN:VCARD\r\nVERSION:3.0\r\nUID:test\r\nFN:Alice\r\nEMAIL:alice@example.org\r\nEND:VCARD\r\n'
    assert client.put('/alice@example.org/contacts/test.vcf', headers=alice, data=card,
                      content_type='text/vcard').status_code == 201
    runner.provision_addressbooks(dav_config)
    assert 'FN:Alice' in client.get('/alice@example.org/contacts/test.vcf', headers=alice).text
    assert client.get('/alice@example.org/contacts/test.vcf', headers={
        'X-Remote-User': 'bob@example.org',
    }).status_code == 403
    browser_config = client.get('/.web/js/config.js', headers=alice)
    assert browser_config.status_code == 200
    assert 'PREFER_BROWSER_LOGIN = true' in browser_config.text
