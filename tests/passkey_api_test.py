import importlib
from types import SimpleNamespace

import pytest
from webauthn.helpers import bytes_to_base64url

from mailu import models


@pytest.fixture
def user(app):
    domain = models.Domain(name='passkey-api.example')
    user = models.User(localpart='alice', domain=domain)
    user.set_password('test-password')
    models.db.session.add_all([domain, user])
    models.db.session.commit()
    return user


def test_api_can_register_list_and_delete_a_users_passkey(client, user, monkeypatch):
    api_module = importlib.import_module('mailu.api.v1.passkey')
    monkeypatch.setattr(api_module, 'verify_registration_response', lambda **kwargs: SimpleNamespace(
        credential_id=b'api-credential-id',
        credential_public_key=b'public-key',
        sign_count=1,
        aaguid='adce0002-35bc-c60a-648b-0b25f1f05503',
        fmt='none',
        user_verified=True,
        credential_device_type='single_device',
        credential_backed_up=False,
    ))
    headers = {'Authorization': 'Bearer not-empty'}
    user_url = f'/api/v1/passkey/user/{user.email}'

    options_response = client.post(user_url + '/registration-options', headers=headers)
    assert options_response.status_code == 200
    options = options_response.get_json()
    assert options['options']['challenge']

    create_response = client.post(user_url, headers=headers, json={
        'request_id': options['request_id'],
        'name': 'Admin-enrolled key',
        'credential': {'id': bytes_to_base64url(b'api-credential-id')},
    })
    assert create_response.status_code == 200
    assert create_response.get_json()['aaguid'] == 'adce0002-35bc-c60a-648b-0b25f1f05503'
    assert create_response.get_json()['email'] == user.email
    assert create_response.get_json()['device_bound'] is True

    list_response = client.get(user_url, headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.get_json()) == 1
    assert list_response.get_json()[0]['email'] == user.email
    credential_id = list_response.get_json()[0]['credential_id']

    delete_response = client.delete(user_url + '/' + credential_id, headers=headers)
    assert delete_response.status_code == 200
    assert client.get(user_url, headers=headers).get_json() == []
