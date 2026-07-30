import time
import urllib.parse

import pytest
from sqlalchemy.orm import Session

from mailu import models
from mailu.api import scim


USER_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:User'
GROUP_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Group'
GROUP_EXTENSION = 'https://mailu.io/schemas/scim/2.0/Group'
PATCH_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:PatchOp'
BULK_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:BulkRequest'


def auth_headers(app):
    return {
        'Authorization': f'Bearer {app.config["API_TOKEN"]}',
        'Content-Type': 'application/scim+json',
    }


def create_domain(name='example.com'):
    domain = models.Domain(name=name)
    models.db.session.add(domain)
    models.db.session.commit()
    return domain


def create_user(localpart='conditional-user', *, displayed_name='Original user'):
    domain = models.db.session.get(models.Domain, 'example.com') or create_domain()
    user = models.User(localpart=localpart, domain=domain, displayed_name=displayed_name)
    user.set_password('secret')
    models.db.session.add(user)
    models.db.session.commit()
    return user


def create_group(localpart='conditional-group', *, comment='Original group'):
    domain = models.db.session.get(models.Domain, 'example.com') or create_domain()
    group = models.Alias(
        localpart=localpart,
        domain=domain,
        comment=comment,
        destination=[],
    )
    models.db.session.add(group)
    models.db.session.flush()
    resource = models.create_scim_group_mapping(
        group,
        resource_id=models.new_scim_id(),
    )
    models.replace_scim_group_graph(
        resource,
        member_ids=[],
        external_destinations=['original@example.net'],
    )
    models.db.session.commit()
    return group


def scim_id(subject):
    if isinstance(subject, models.ScimResource):
        return subject.id
    return subject.scim_resource.id


def scim_resource(resource_id):
    return models.db.session.get(models.ScimResource, resource_id)


def scim_user(resource_id):
    resource = scim_resource(resource_id)
    if resource is not None:
        return (
            resource.user
            or models.db.session.get(models.User, resource.subject_address)
        )
    return models.db.session.get(models.User, resource_id)


def scim_group(resource_id):
    resource = scim_resource(resource_id)
    if resource is not None:
        return resource.alias
    return models.db.session.get(models.Alias, resource_id)


def group_payload(
    alias_address,
    *,
    display_name='Group',
    members=None,
    external_destinations=None,
    schemas=None,
):
    return {
        'schemas': schemas or [GROUP_SCHEMA, GROUP_EXTENSION],
        'displayName': display_name,
        'members': [
            {'value': member}
            for member in (members or [])
        ],
        GROUP_EXTENSION: {
            'aliasAddress': alias_address,
            'externalDestinations': external_destinations or [],
        },
    }


def assert_precondition_failed(response):
    assert response.status_code == 412
    assert response.content_type == 'application/scim+json'
    assert response.get_json() == {
        'schemas': ['urn:ietf:params:scim:api:messages:2.0:Error'],
        'status': '412',
        'detail': 'If-Match does not match the current resource version',
    }


def test_scim_service_provider_config(app, client):
    rv = client.get('/api/scim/v2/ServiceProviderConfig', headers=auth_headers(app))

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['patch']['supported'] is True
    assert data['bulk']['supported'] is True
    assert data['etag']['supported'] is True
    assert data['filter']['supported'] is False
    assert data['changePassword']['supported'] is False
    assert data['authenticationSchemes'][0]['type'] == 'oauthbearertoken'


def test_scim_groups_are_backed_by_aliases(app, client):
    with app.app_context():
        create_domain()
        domain = models.db.session.get(models.Domain, 'example.com')
        user = models.User(localpart='alice', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    payload = group_payload(
        'admins@example.com',
        display_name='Administrators',
        members=[user_id],
    )
    rv = client.post('/api/scim/v2/Groups', json=payload, headers=auth_headers(app))

    assert rv.status_code == 201
    data = rv.get_json()
    assert data['id'] != 'admins@example.com'
    assert data['displayName'] == 'Administrators'
    assert data['members'][0]['value'] == user_id
    assert data['members'][0]['type'] == 'User'
    assert data[GROUP_EXTENSION] == {
        'aliasAddress': 'admins@example.com',
        'externalDestinations': [],
    }
    assert data['meta']['resourceType'] == 'Group'
    assert data['meta']['version'].startswith('"')
    assert data['meta']['version'].endswith('"')
    assert rv.headers['ETag'] == data['meta']['version']
    assert rv.headers['Location'] == data['meta']['location']
    assert rv.headers['Content-Location'] == data['meta']['location']

    with app.app_context():
        alias = models.db.session.get(models.Alias, 'admins@example.com')
        assert alias is not None
        assert alias.destination == ['alice@example.com']

    rv = client.get(
        f'/api/scim/v2/Groups/{data["id"]}',
        headers=auth_headers(app),
    )
    assert rv.status_code == 200
    assert rv.get_json()['members'][0]['value'] == user_id


def test_scim_group_patch_updates_alias_members(app, client):
    with app.app_context():
        create_domain()
        alice = create_user(localpart='alice')
        bob = create_user(localpart='bob')
        alias = create_group(localpart='team')
        models.replace_scim_group_graph(
            alias.scim_resource,
            member_ids=[scim_id(alice)],
            external_destinations=[],
        )
        models.db.session.commit()
        group_id = scim_id(alias)
        alice_id = scim_id(alice)
        bob_id = scim_id(bob)

    payload = {
        'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
        'Operations': [
            {'op': 'add', 'path': 'members', 'value': [{'value': bob_id}]},
            {'op': 'remove', 'path': 'members', 'value': [{'value': alice_id}]},
        ],
    }
    rv = client.patch(
        f'/api/scim/v2/Groups/{group_id}',
        json=payload,
        headers=auth_headers(app),
    )

    assert rv.status_code == 200
    assert [member['value'] for member in rv.get_json()['members']] == [bob_id]
    with app.app_context():
        alias = models.db.session.get(models.Alias, 'team@example.com')
        assert alias.destination == ['bob@example.com']


def test_scim_group_patch_supports_filtered_and_remove_all_members(app, client):
    with app.app_context():
        create_domain()
        alice = create_user(localpart='alice')
        bob = create_user(localpart='bob')
        group = create_group(localpart='filtered')
        models.replace_scim_group_graph(
            group.scim_resource,
            member_ids=[scim_id(alice), scim_id(bob)],
            external_destinations=[],
        )
        models.db.session.commit()
        group_id = scim_id(group)
        alice_id = scim_id(alice)
        bob_id = scim_id(bob)

    filtered = client.patch(
        f'/api/scim/v2/Groups/{group_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'remove',
                'path': f'members[value eq "{alice_id}"]',
            }],
        },
        headers=auth_headers(app),
    )
    assert filtered.status_code == 200
    assert [member['value'] for member in filtered.get_json()['members']] == [bob_id]

    no_target = client.patch(
        f'/api/scim/v2/Groups/{group_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'remove',
                'path': 'members[value eq "00000000-0000-4000-8000-000000000000"]',
            }],
        },
        headers=auth_headers(app),
    )
    assert no_target.status_code == 200
    assert [member['value'] for member in no_target.get_json()['members']] == [bob_id]

    remove_all = client.patch(
        f'/api/scim/v2/Groups/{group_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{'op': 'remove', 'path': 'members'}],
        },
        headers=auth_headers(app),
    )
    assert remove_all.status_code == 200
    assert remove_all.get_json()['members'] == []

    required = client.patch(
        f'/api/scim/v2/Groups/{group_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{'op': 'remove', 'path': 'displayName'}],
        },
        headers=auth_headers(app),
    )
    assert required.status_code == 400
    assert required.get_json()['scimType'] == 'mutability'


def test_scim_group_pathless_patch_applies_all_attributes_atomically(app, client):
    with app.app_context():
        create_domain()
        member_id = scim_id(create_user(localpart='pathless-member'))
        group_id = scim_id(create_group(localpart='pathless'))

    response = client.patch(
        f'/api/scim/v2/Groups/{group_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'value': {
                    'displayName': 'Pathless group',
                    'members': [{'value': member_id}],
                    GROUP_EXTENSION: {
                        'externalDestinations': ['pager@example.net'],
                    },
                },
            }],
        },
        headers=auth_headers(app),
    )
    assert response.status_code == 200
    assert response.get_json()['displayName'] == 'Pathless group'
    assert [member['value'] for member in response.get_json()['members']] == [member_id]
    assert response.get_json()[GROUP_EXTENSION]['externalDestinations'] == [
        'pager@example.net',
    ]

    rejected = client.patch(
        f'/api/scim/v2/Groups/{group_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [
                {'op': 'replace', 'path': 'displayName', 'value': 'Leaked change'},
                {'op': 'replace', 'path': 'unsupported', 'value': 'reject'},
            ],
        },
        headers=auth_headers(app),
    )
    assert rejected.status_code == 400
    with app.app_context():
        group = scim_group(group_id)
        assert group.comment == 'Pathless group'
        assert group.destination == [
            'pager@example.net',
            'pathless-member@example.com',
        ]



def test_scim_user_resources_include_etag_metadata(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='etag', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.get(
        f'/api/scim/v2/Users/{user_id}',
        headers=auth_headers(app),
    )

    assert rv.status_code == 200
    meta = rv.get_json()['meta']
    assert meta['resourceType'] == 'User'
    assert meta['version'].startswith('"')
    assert meta['version'].endswith('"')
    assert 'created' not in meta
    assert 'lastModified' not in meta
    assert rv.headers['ETag'] == meta['version']
    assert rv.headers['Content-Location'] == meta['location']


def test_scim_resource_locations_percent_encode_reserved_id_characters(app, client):
    with app.test_request_context('/'):
        location = scim._resource_location(
            'Users',
            'hash#tag@example.com',
        )
    assert '#tag' not in location
    assert '%23tag' in location


@pytest.mark.parametrize('resource_type', ['Users', 'Groups'])
def test_scim_conditional_get_uses_http_entity_tag_rules(app, client, resource_type):
    with app.app_context():
        resource = create_user() if resource_type == 'Users' else create_group()
        resource_id = scim_id(resource)

    url = f'/api/scim/v2/{resource_type}/{resource_id}'
    current = client.get(url, headers=auth_headers(app))
    version = current.headers['ETag']

    not_modified = client.get(
        url,
        headers={**auth_headers(app), 'If-None-Match': f'"other", W/{version}'},
    )
    assert not_modified.status_code == 304
    assert not_modified.data == b''
    assert not_modified.headers['ETag'] == version

    matched = client.get(
        url,
        headers={**auth_headers(app), 'If-Match': f'"other", {version}'},
    )
    assert matched.status_code == 200

    stale = client.get(
        url,
        headers={**auth_headers(app), 'If-Match': '"stale"'},
    )
    assert_precondition_failed(stale)


@pytest.mark.parametrize('resource_type', ['Users', 'Groups'])
def test_scim_if_none_match_rejects_unsafe_change(app, client, resource_type):
    with app.app_context():
        resource = create_user() if resource_type == 'Users' else create_group()
        resource_id = scim_id(resource)

    url = f'/api/scim/v2/{resource_type}/{resource_id}'
    version = client.get(url, headers=auth_headers(app)).headers['ETag']
    if resource_type == 'Users':
        payload = {
            'schemas': [PATCH_SCHEMA],
            'Operations': [
                {'op': 'replace', 'path': 'displayName', 'value': 'Must not change'},
            ],
        }
    else:
        payload = {
            'schemas': [PATCH_SCHEMA],
            'Operations': [
                {
                    'op': 'replace',
                    'path': 'members',
                    'value': [{'value': 'must-not-change@example.net'}],
                },
            ],
        }

    response = client.patch(
        url,
        json=payload,
        headers={
            **auth_headers(app),
            'If-Match': version,
            'If-None-Match': f'W/{version}',
        },
    )

    assert response.status_code == 412
    assert response.get_json()['detail'] == 'If-None-Match matches the current resource version'
    with app.app_context():
        if resource_type == 'Users':
            user = scim_user(resource_id)
            assert user.displayed_name == 'Original user'
        else:
            group = scim_group(resource_id)
            assert group.destination == ['original@example.net']


def test_scim_if_match_supports_lists_and_wildcard_but_rejects_weak_tags(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='entity-tags'))
    url = f'/api/scim/v2/Users/{user_id}'
    version = client.get(url, headers=auth_headers(app)).headers['ETag']
    payload = {
        'schemas': [PATCH_SCHEMA],
        'Operations': [
            {'op': 'replace', 'path': 'displayName', 'value': 'List match'},
        ],
    }

    weak = client.patch(
        url,
        json=payload,
        headers={**auth_headers(app), 'If-Match': f'W/{version}'},
    )
    assert_precondition_failed(weak)

    listed = client.patch(
        url,
        json=payload,
        headers={**auth_headers(app), 'If-Match': f'"other", {version}'},
    )
    assert listed.status_code == 200
    assert listed.get_json()['displayName'] == 'List match'

    wildcard = client.patch(
        url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [
                {'op': 'replace', 'path': 'displayName', 'value': 'Wildcard match'},
            ],
        },
        headers={**auth_headers(app), 'If-Match': '*'},
    )
    assert wildcard.status_code == 200
    assert wildcard.get_json()['displayName'] == 'Wildcard match'


@pytest.mark.parametrize('method', ['PUT', 'PATCH', 'DELETE'])
def test_scim_user_if_match_rejects_stale_without_changes(app, client, method):
    with app.app_context():
        user = create_user()
        user_id = scim_id(user)
        user_name = user.email

    initial = client.get(f'/api/scim/v2/Users/{user_id}', headers=auth_headers(app))
    stale_version = initial.get_json()['meta']['version']

    with app.app_context():
        user = scim_user(user_id)
        user.displayed_name = 'Concurrent user update'
        models.db.session.commit()
        expected_password = user.password

    current = client.get(f'/api/scim/v2/Users/{user_id}', headers=auth_headers(app))
    current_version = current.get_json()['meta']['version']
    assert current_version != stale_version

    headers = {**auth_headers(app), 'If-Match': stale_version}
    if method == 'PUT':
        response = client.put(
            f'/api/scim/v2/Users/{user_id}',
            json={
                'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
                'id': user_id,
                'userName': user_name,
                'active': False,
                'displayName': 'Rejected stale replacement',
            },
            headers=headers,
        )
    elif method == 'PATCH':
        response = client.patch(
            f'/api/scim/v2/Users/{user_id}',
            json={
                'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
                'Operations': [
                    {'op': 'replace', 'path': 'active', 'value': False},
                    {'op': 'replace', 'path': 'displayName', 'value': 'Rejected stale patch'},
                ],
            },
            headers=headers,
        )
    else:
        response = client.delete(f'/api/scim/v2/Users/{user_id}', headers=headers)

    assert_precondition_failed(response)
    with app.app_context():
        user = scim_user(user_id)
        assert user.enabled is True
        assert user.displayed_name == 'Concurrent user update'
        assert user.password == expected_password

    current_headers = {**auth_headers(app), 'If-Match': current_version}
    if method == 'PUT':
        response = client.put(
            f'/api/scim/v2/Users/{user_id}',
            json={
                'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
                'id': user_id,
                'userName': user_name,
                'active': False,
                'displayName': 'Accepted replacement',
            },
            headers=current_headers,
        )
        assert response.status_code == 200
        assert response.get_json()['displayName'] == 'Accepted replacement'
    elif method == 'PATCH':
        response = client.patch(
            f'/api/scim/v2/Users/{user_id}',
            json={
                'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
                'Operations': [{'op': 'replace', 'path': 'displayName', 'value': 'Accepted patch'}],
            },
            headers=current_headers,
        )
        assert response.status_code == 200
        assert response.get_json()['displayName'] == 'Accepted patch'
    else:
        response = client.delete(f'/api/scim/v2/Users/{user_id}', headers=current_headers)
        assert response.status_code == 204


@pytest.mark.parametrize('method', ['PUT', 'PATCH', 'DELETE'])
def test_scim_group_if_match_rejects_stale_without_changes(app, client, method):
    with app.app_context():
        group = create_group()
        group_id = scim_id(group)
        alias_address = group.email

    initial = client.get(f'/api/scim/v2/Groups/{group_id}', headers=auth_headers(app))
    stale_version = initial.get_json()['meta']['version']

    with app.app_context():
        group = scim_group(group_id)
        models.permit_scim_managed_alias_edit(group)
        group.comment = 'Concurrent group update'
        models.db.session.commit()

    current = client.get(f'/api/scim/v2/Groups/{group_id}', headers=auth_headers(app))
    current_version = current.get_json()['meta']['version']
    assert current_version != stale_version

    headers = {**auth_headers(app), 'If-Match': stale_version}
    if method == 'PUT':
        response = client.put(
            f'/api/scim/v2/Groups/{group_id}',
            json=group_payload(
                alias_address,
                display_name='Rejected stale replacement',
                external_destinations=['rejected@example.net'],
            ),
            headers=headers,
        )
    elif method == 'PATCH':
        response = client.patch(
            f'/api/scim/v2/Groups/{group_id}',
            json={
                'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
                'Operations': [
                    {
                        'op': 'replace',
                        'path': (
                            f'{GROUP_EXTENSION}:externalDestinations'
                        ),
                        'value': ['rejected@example.net'],
                    }
                ],
            },
            headers=headers,
        )
    else:
        response = client.delete(f'/api/scim/v2/Groups/{group_id}', headers=headers)

    assert_precondition_failed(response)
    with app.app_context():
        group = scim_group(group_id)
        assert group.comment == 'Concurrent group update'
        assert group.destination == ['original@example.net']

    current_headers = {**auth_headers(app), 'If-Match': current_version}
    if method == 'PUT':
        response = client.put(
            f'/api/scim/v2/Groups/{group_id}',
            json=group_payload(
                alias_address,
                display_name='Accepted replacement',
                external_destinations=['accepted@example.net'],
            ),
            headers=current_headers,
        )
        assert response.status_code == 200
        assert response.get_json()['displayName'] == 'Accepted replacement'
    elif method == 'PATCH':
        response = client.patch(
            f'/api/scim/v2/Groups/{group_id}',
            json={
                'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
                'Operations': [
                    {
                        'op': 'replace',
                        'path': (
                            f'{GROUP_EXTENSION}:externalDestinations'
                        ),
                        'value': ['accepted@example.net'],
                    }
                ],
            },
            headers=current_headers,
        )
        assert response.status_code == 200
        assert response.get_json()[GROUP_EXTENSION][
            'externalDestinations'
        ] == ['accepted@example.net']
    else:
        response = client.delete(f'/api/scim/v2/Groups/{group_id}', headers=current_headers)
        assert response.status_code == 204


def test_scim_user_patch_rejects_password_change_without_side_effects(app, client, monkeypatch):
    with app.app_context():
        user = create_user(localpart='patch-password')
        user_id = scim_id(user)
        original_password = user.password

    pruned_users = []
    monkeypatch.setattr(
        models.utils.MailuSessionExtension,
        'prune_sessions',
        lambda uid=None, keep=None, app=None: pruned_users.append(uid),
    )
    response = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [
                {'op': 'replace', 'path': 'password', 'value': 'replacement-secret'},
                {'op': 'replace', 'path': 'unsupported', 'value': 'reject the request'},
            ],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'mutability'
    assert pruned_users == []
    with app.app_context():
        user = scim_user(user_id)
        assert user.password == original_password


@pytest.mark.parametrize('method', ['PUT', 'PATCH', 'DELETE'])
def test_scim_deprovisioning_prunes_existing_sessions_after_commit(
    app,
    client,
    monkeypatch,
    method,
):
    with app.app_context():
        user = create_user(localpart=f'deprovision-{method.lower()}')
        user_id = scim_id(user)
        user_email = user.email

    pruned_users = []
    monkeypatch.setattr(
        models.utils.MailuSessionExtension,
        'prune_sessions',
        lambda uid=None, keep=None, app=None: pruned_users.append(uid),
    )
    url = f'/api/scim/v2/Users/{user_id}'
    if method == 'PUT':
        response = client.put(
            url,
            json={
                'schemas': [USER_SCHEMA],
                'userName': user_email,
                'active': False,
            },
            headers=auth_headers(app),
        )
    elif method == 'PATCH':
        response = client.patch(
            url,
            json={
                'schemas': [PATCH_SCHEMA],
                'Operations': [{
                    'op': 'replace',
                    'path': 'active',
                    'value': False,
                }],
            },
            headers=auth_headers(app),
        )
    else:
        response = client.delete(url, headers=auth_headers(app))

    assert response.status_code == (204 if method == 'DELETE' else 200)
    assert pruned_users == [user_email]
    with app.app_context():
        assert scim_user(user_id).enabled is False


def test_scim_stale_deprovision_precondition_does_not_prune_sessions(
    app,
    client,
    monkeypatch,
):
    with app.app_context():
        user_id = scim_id(create_user(localpart='stale-deprovision'))
    url = f'/api/scim/v2/Users/{user_id}'
    stale_version = client.get(url, headers=auth_headers(app)).headers['ETag']
    with app.app_context():
        user = scim_user(user_id)
        user.displayed_name = 'Concurrent change'
        models.db.session.commit()

    pruned_users = []
    monkeypatch.setattr(
        models.utils.MailuSessionExtension,
        'prune_sessions',
        lambda uid=None, keep=None, app=None: pruned_users.append(uid),
    )
    response = client.patch(
        url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'active',
                'value': False,
            }],
        },
        headers={**auth_headers(app), 'If-Match': stale_version},
    )

    assert_precondition_failed(response)
    assert pruned_users == []
    with app.app_context():
        assert scim_user(user_id).enabled is True


def test_scim_session_revocation_failure_does_not_roll_back_committed_user_change(
    app,
    client,
    monkeypatch,
):
    with app.app_context():
        user_id = scim_id(create_user(localpart='revoke-failure'))

    def fail_revocation(**_kwargs):
        raise RuntimeError('session store unavailable')

    monkeypatch.setattr(
        models.utils.MailuSessionExtension,
        'prune_sessions',
        fail_revocation,
    )
    response = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'active',
                'value': False,
            }],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 200
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['active'] is False
    with app.app_context():
        assert scim_user(user_id).enabled is False


def test_scim_lock_failure_returns_scim_error_without_mutation(
    app,
    client,
    monkeypatch,
):
    with app.app_context():
        user_id = scim_id(create_user(localpart='lock-failure'))
    original_get_scim_for_update = scim._get_scim_for_update

    def fail_user_lock(resource_id, resource_type):
        if resource_type == 'User' and resource_id == user_id:
            raise scim.SQLAlchemyError('lock unavailable')
        return original_get_scim_for_update(resource_id, resource_type)

    monkeypatch.setattr(scim, '_get_scim_for_update', fail_user_lock)
    response = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'active',
                'value': False,
            }],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 500
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['detail'] == 'The SCIM User could not be patched'
    with app.app_context():
        assert scim_user(user_id).enabled is True


def test_scim_sqlite_lock_refreshes_an_unexpired_identity(app):
    with app.app_context():
        user = create_user(localpart='stale-identity')
        user_id = scim_id(user)
        user_email = user.email
        session = models.db.session()
        cached = session.get(models.User, user_email)
        session.commit()
        assert cached.displayed_name == 'Original user'

        concurrent_session = Session(models.db.engine)
        try:
            concurrent = concurrent_session.get(models.User, user_email)
            concurrent.displayed_name = 'Concurrent user'
            concurrent_session.commit()
        finally:
            concurrent_session.close()

        models.lock_scim_graph()
        locked = scim._get_scim_for_update(user_id, 'User')
        assert locked.user is cached
        assert locked.user.displayed_name == 'Concurrent user'
        models.db.session.rollback()


def test_scim_bulk_continues_after_session_revocation_failure(
    app,
    client,
    monkeypatch,
):
    with app.app_context():
        user_id = scim_id(create_user(localpart='bulk-revoke-failure'))

    def fail_revocation(**_kwargs):
        raise RuntimeError('session store unavailable')

    monkeypatch.setattr(
        models.utils.MailuSessionExtension,
        'prune_sessions',
        fail_revocation,
    )
    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [
                {
                    'method': 'PATCH',
                    'path': f'/Users/{user_id}',
                    'data': {
                        'schemas': [PATCH_SCHEMA],
                        'Operations': [{
                            'op': 'replace',
                            'path': 'active',
                            'value': False,
                        }],
                    },
                },
                {
                    'method': 'POST',
                    'path': '/Users',
                    'bulkId': 'created-after-revocation-error',
                    'data': {
                        'schemas': [USER_SCHEMA],
                        'userName': 'after-revocation-error@example.com',
                    },
                },
            ],
        },
        headers=auth_headers(app),
    )

    assert [item['status'] for item in response.get_json()['Operations']] == ['200', '201']
    with app.app_context():
        assert scim_user(user_id).enabled is False
        assert models.db.session.get(models.User, 'after-revocation-error@example.com') is not None


def test_scim_create_and_get_user(app, client):
    with app.app_context():
        create_domain()

    payload = {
        'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
        'userName': 'Alice@example.com',
        'active': True,
        'displayName': 'Alice Example',
    }
    rv = client.post('/api/scim/v2/Users', json=payload, headers=auth_headers(app))

    assert rv.status_code == 201
    data = rv.get_json()
    assert data['id'] != 'alice@example.com'
    assert data['id']
    assert data['userName'] == 'alice@example.com'
    assert data['active'] is True
    assert data['displayName'] == 'Alice Example'
    assert data['emails'][0]['value'] == 'alice@example.com'

    with app.app_context():
        user = models.db.session.get(models.User, 'alice@example.com')
        assert user is not None
        assert user.enabled is True
        assert user.displayed_name == 'Alice Example'

    rv = client.get(
        f'/api/scim/v2/Users/{data["id"]}',
        headers=auth_headers(app),
    )
    assert rv.status_code == 200
    assert rv.get_json()['userName'] == 'alice@example.com'


def test_scim_create_requires_existing_domain(app, client):
    payload = {
        'schemas': [USER_SCHEMA],
        'userName': 'missing@example.com',
    }
    rv = client.post('/api/scim/v2/Users', json=payload, headers=auth_headers(app))

    assert rv.status_code == 404
    assert rv.get_json()['schemas'] == ['urn:ietf:params:scim:api:messages:2.0:Error']


def test_scim_filter_user_by_username(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='bob', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.get('/api/scim/v2/Users?filter=userName eq "bob@example.com"', headers=auth_headers(app))

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['totalResults'] == 1
    assert data['Resources'][0]['userName'] == 'bob@example.com'


def test_scim_patch_active_and_display_name(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='carol', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    payload = {
        'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
        'Operations': [
            {'op': 'replace', 'path': 'active', 'value': False},
            {'op': 'replace', 'path': 'displayName', 'value': 'Carol Disabled'},
        ],
    }
    rv = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json=payload,
        headers=auth_headers(app),
    )

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['active'] is False
    assert data['displayName'] == 'Carol Disabled'

    with app.app_context():
        user = models.db.session.get(models.User, 'carol@example.com')
        assert user.enabled is False
        assert user.displayed_name == 'Carol Disabled'


def test_scim_patch_accepts_schema_qualified_core_path(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='qualified-path'))

    response = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': (
                    'urn:ietf:params:scim:schemas:core:2.0:User:displayName'
                ),
                'value': 'Qualified path',
            }],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 200
    assert response.get_json()['displayName'] == 'Qualified path'


def test_scim_resource_attribute_names_are_case_insensitive(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='attribute-case'))

    response = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'SCHEMAS': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'operations': [{
                'OP': 'replace',
                'PATH': 'DISPLAYNAME',
                'VALUE': 'Case insensitive',
            }],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 200
    assert response.get_json()['displayName'] == 'Case insensitive'


def test_scim_delete_disables_user_without_removing_mailbox(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='dave', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.delete(
        f'/api/scim/v2/Users/{user_id}',
        headers=auth_headers(app),
    )

    assert rv.status_code == 204
    assert client.get(
        f'/api/scim/v2/Users/{user_id}',
        headers=auth_headers(app),
    ).status_code == 404
    with app.app_context():
        user = models.db.session.get(models.User, 'dave@example.com')
        assert user is not None
        assert user.enabled is False


@pytest.mark.parametrize('resource_type', ['Users', 'Groups'])
def test_scim_delete_missing_resource_returns_scim_404(app, client, resource_type):
    response = client.delete(
        f'/api/scim/v2/{resource_type}/missing@example.com',
        headers=auth_headers(app),
    )

    assert response.status_code == 404
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['status'] == '404'


def test_scim_repeated_group_delete_returns_scim_404(app, client):
    with app.app_context():
        group_id = scim_id(create_group(localpart='delete-twice'))
    url = f'/api/scim/v2/Groups/{group_id}'

    assert client.delete(url, headers=auth_headers(app)).status_code == 204
    repeated = client.delete(url, headers=auth_headers(app))

    assert repeated.status_code == 404
    assert repeated.get_json()['status'] == '404'


def test_scim_list_rejects_invalid_pagination(app, client):
    rv = client.get('/api/scim/v2/Users?startIndex=nope', headers=auth_headers(app))

    assert rv.status_code == 400
    data = rv.get_json()
    assert data['schemas'] == ['urn:ietf:params:scim:api:messages:2.0:Error']
    assert data['scimType'] == 'invalidValue'


def test_scim_create_rejects_non_object_payload(app, client):
    rv = client.post('/api/scim/v2/Users', json=[], headers=auth_headers(app))

    assert rv.status_code == 400
    data = rv.get_json()
    assert data['scimType'] == 'invalidSyntax'


def test_scim_create_parses_string_false_active(app, client):
    with app.app_context():
        create_domain()

    payload = {
        'schemas': [USER_SCHEMA],
        'userName': 'erin@example.com',
        'active': 'false',
    }
    rv = client.post('/api/scim/v2/Users', json=payload, headers=auth_headers(app))

    assert rv.status_code == 201
    assert rv.get_json()['active'] is False
    with app.app_context():
        user = models.db.session.get(models.User, 'erin@example.com')
        assert user.enabled is False


def test_scim_patch_rejects_invalid_active_value(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='frank', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    payload = {
        'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
        'Operations': [{'op': 'replace', 'path': 'active', 'value': 'maybe'}],
    }
    rv = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json=payload,
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        user = models.db.session.get(models.User, 'frank@example.com')
        assert user.enabled is True


def test_scim_patch_rejects_non_object_operations(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='grace', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': ['not-an-object'],
        },
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidSyntax'


def test_scim_create_handles_non_string_username_and_name(app, client):
    with app.app_context():
        create_domain('123.example')

    rv = client.post(
        '/api/scim/v2/Users',
        json={
            'schemas': [USER_SCHEMA],
            'userName': 123,
            'name': 'not-an-object',
        },
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidValue'


def test_scim_patch_rejects_non_string_op_and_path(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='heidi', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{'op': 7, 'path': 9, 'value': 'ignored'}],
        },
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidSyntax'
    with app.app_context():
        user = models.db.session.get(models.User, 'heidi@example.com')
        assert user.enabled is True


def test_scim_patch_remove_clears_optional_display_name(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='ivan', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{'op': 'remove', 'path': 'displayName'}],
        },
        headers=auth_headers(app),
    )

    assert rv.status_code == 200
    assert rv.get_json()['displayName'] == 'ivan@example.com'
    with app.app_context():
        assert models.db.session.get(models.User, 'ivan@example.com').displayed_name == ''


def test_scim_patch_rejects_unknown_path(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='judy', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'title',
                'value': 'Boss',
            }],
        },
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidPath'


def test_scim_list_caps_count_to_advertised_max_results(app, client):
    with app.app_context():
        domain = create_domain()
        for localpart in ('kate', 'louis'):
            user = models.User(localpart=localpart, domain=domain)
            user.set_password('secret')
            models.db.session.add(user)
        models.db.session.commit()

    rv = client.get('/api/scim/v2/Users?count=999999', headers=auth_headers(app))

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['itemsPerPage'] == 2
    assert data['totalResults'] == 2


def test_scim_patch_rejects_empty_operations(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='mallory', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={'schemas': [PATCH_SCHEMA], 'Operations': []},
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidValue'


def test_scim_create_rejects_non_string_password(app, client):
    with app.app_context():
        create_domain()

    rv = client.post(
        '/api/scim/v2/Users',
        json={
            'schemas': [USER_SCHEMA],
            'userName': 'nick@example.com',
            'password': {'cleartext': 'nope'},
        },
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        assert models.db.session.get(models.User, 'nick@example.com') is None


def test_scim_patch_rejects_existing_password_changes(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='olivia', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()
        user_id = scim_id(user)

    rv = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'password',
                'value': ['bad'],
            }],
        },
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'mutability'


def test_scim_create_rejects_malformed_json(app, client):
    rv = client.post(
        '/api/scim/v2/Users',
        data='{',
        content_type='application/scim+json',
        headers={'Authorization': f'Bearer {app.config["API_TOKEN"]}'},
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidSyntax'


def test_scim_bulk_creates_user_and_group(app, client):
    with app.app_context():
        create_domain()

    payload = {
        'schemas': ['urn:ietf:params:scim:api:messages:2.0:BulkRequest'],
        'Operations': [
            {
                'method': 'POST',
                'path': '/Users',
                'bulkId': 'user1',
                'data': {
                    'schemas': [USER_SCHEMA],
                    'userName': 'bulkuser@example.com',
                    'active': True,
                },
            },
            {
                'method': 'POST',
                'path': '/Groups',
                'bulkId': 'group1',
                'data': group_payload(
                    'bulkgroup@example.com',
                    display_name='Bulk group',
                    members=['bulkId:user1'],
                ),
            },
        ],
    }
    rv = client.post('/api/scim/v2/Bulk', json=payload, headers=auth_headers(app))

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['schemas'] == ['urn:ietf:params:scim:api:messages:2.0:BulkResponse']
    assert [operation['status'] for operation in data['Operations']] == ['201', '201']
    assert [operation['method'] for operation in data['Operations']] == ['POST', 'POST']
    assert all(operation['version'] for operation in data['Operations'])
    with app.app_context():
        assert models.db.session.get(models.User, 'bulkuser@example.com') is not None
        alias = models.db.session.get(models.Alias, 'bulkgroup@example.com')
        assert alias is not None
        assert alias.destination == ['bulkuser@example.com']


def test_scim_bulk_resolves_forward_bulk_id_dependencies(app, client):
    with app.app_context():
        create_domain()

    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [
                {
                    'method': 'POST',
                    'path': '/Groups',
                    'bulkId': 'group-first',
                    'data': group_payload(
                        'forward-group@example.com',
                        display_name='Forward group',
                        members=['bulkId:user-later'],
                    ),
                },
                {
                    'method': 'POST',
                    'path': '/Users',
                    'bulkId': 'user-later',
                    'data': {
                        'schemas': [USER_SCHEMA],
                        'userName': 'forward-user@example.com',
                    },
                },
            ],
        },
        headers=auth_headers(app),
    )

    assert [item['status'] for item in response.get_json()['Operations']] == ['201', '201']
    with app.app_context():
        group = models.db.session.get(models.Alias, 'forward-group@example.com')
        assert group.destination == ['forward-user@example.com']


def test_scim_bulk_rejects_circular_bulk_id_dependencies_without_partial_commit(
    app,
    client,
):
    with app.app_context():
        create_domain()

    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'failOnErrors': 0,
            'Operations': [
                {
                    'method': 'POST',
                    'path': '/Groups',
                    'bulkId': 'group-a',
                    'data': group_payload(
                        'group-a@example.com',
                        display_name='Group A',
                        members=['bulkId:group-b'],
                    ),
                },
                {
                    'method': 'POST',
                    'path': '/Groups',
                    'bulkId': 'group-b',
                    'data': group_payload(
                        'group-b@example.com',
                        display_name='Group B',
                        members=[
                            'bulkId:group-a',
                            'not-an-id',
                        ],
                    ),
                },
            ],
        },
        headers=auth_headers(app),
    )

    assert [item['status'] for item in response.get_json()['Operations']] == ['409', '409']
    with app.app_context():
        group_a = models.db.session.get(models.Alias, 'group-a@example.com')
        group_b = models.db.session.get(models.Alias, 'group-b@example.com')
        assert group_a is None
        assert group_b is None


def test_scim_bulk_stops_after_fail_on_errors(app, client):
    payload = {
        'schemas': [BULK_SCHEMA],
        'failOnErrors': 1,
        'Operations': [
            {
                'method': 'POST',
                'path': '/Users',
                'bulkId': 'missing',
                'data': {
                    'schemas': [USER_SCHEMA],
                    'userName': 'missing@example.com',
                },
            },
            {
                'method': 'POST',
                'path': '/Users',
                'bulkId': 'never',
                'data': {
                    'schemas': [USER_SCHEMA],
                    'userName': 'never@example.com',
                },
            },
        ],
    }
    rv = client.post('/api/scim/v2/Bulk', json=payload, headers=auth_headers(app))

    assert rv.status_code == 200
    operations = rv.get_json()['Operations']
    assert len(operations) == 1
    assert operations[0]['status'] == '404'


@pytest.mark.parametrize('resource_type', ['Users', 'Groups'])
def test_scim_bulk_version_rejects_stale_resource_without_changes(app, client, resource_type):
    with app.app_context():
        resource = create_user() if resource_type == 'Users' else create_group()
        resource_id = scim_id(resource)
    url = f'/api/scim/v2/{resource_type}/{resource_id}'
    stale_version = client.get(url, headers=auth_headers(app)).headers['ETag']

    with app.app_context():
        if resource_type == 'Users':
            resource = scim_user(resource_id)
            resource.displayed_name = 'Concurrent user'
        else:
            resource = scim_group(resource_id)
            models.permit_scim_managed_alias_edit(resource)
            resource.comment = 'Concurrent group'
        models.db.session.commit()

    if resource_type == 'Users':
        patch = {
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'displayName',
                'value': 'Rejected',
            }],
        }
    else:
        patch = {
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': f'{GROUP_EXTENSION}:externalDestinations',
                'value': ['rejected@example.net'],
            }],
        }
    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'PATCH',
                'path': f'/{resource_type}/{resource_id}',
                'version': stale_version,
                'data': patch,
            }],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 200
    operation = response.get_json()['Operations'][0]
    assert operation['method'] == 'PATCH'
    assert operation['status'] == '412'
    assert operation['response']['status'] == '412'
    assert operation['location'].endswith(f'/{resource_type}/{resource_id}')
    with app.app_context():
        if resource_type == 'Users':
            assert scim_user(resource_id).displayed_name == 'Concurrent user'
        else:
            group = scim_group(resource_id)
            assert group.comment == 'Concurrent group'
            assert group.destination == ['original@example.net']


def test_scim_bulk_delete_response_includes_resource_location(app, client):
    with app.app_context():
        group_id = scim_id(create_group(localpart='bulk-delete-location'))

    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'DELETE',
                'path': f'/Groups/{group_id}',
            }],
        },
        headers=auth_headers(app),
    )

    operation = response.get_json()['Operations'][0]
    assert operation['status'] == '204'
    assert operation['location'].endswith(f'/Groups/{group_id}')
    with app.app_context():
        assert scim_group(group_id) is None


def test_scim_bulk_does_not_leak_failed_operation_state_into_later_commit(app, client):
    with app.app_context():
        group = create_group(localpart='bulk-rollback')
        group_id = scim_id(group)
        group_email = group.email
    invalid_group = group_payload(
        group_email,
        display_name='Must roll back',
    )
    invalid_group['id'] = group_id
    invalid_group['members'] = [{}]

    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [
                {
                    'method': 'PUT',
                    'path': f'/Groups/{group_id}',
                    'data': invalid_group,
                },
                {
                    'method': 'POST',
                    'path': '/Users',
                    'bulkId': 'commit-after-error',
                    'data': {
                        'schemas': [USER_SCHEMA],
                        'userName': 'committed@example.com',
                    },
                },
            ],
        },
        headers=auth_headers(app),
    )

    assert [item['status'] for item in response.get_json()['Operations']] == ['400', '201']
    with app.app_context():
        group = scim_group(group_id)
        assert group.comment == 'Original group'
        assert group.destination == ['original@example.net']
        assert models.db.session.get(models.User, 'committed@example.com') is not None


def test_scim_bulk_ignores_outer_if_match_and_preserves_absent_version_behavior(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='bulk-outer-header'))

    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'PATCH',
                'path': f'/Users/{user_id}',
                'data': {
                    'schemas': [PATCH_SCHEMA],
                    'Operations': [{
                        'op': 'replace',
                        'path': 'displayName',
                        'value': 'Bulk update',
                    }],
                },
            }],
        },
        headers={**auth_headers(app), 'If-Match': '"outer-request-tag"'},
    )

    operation = response.get_json()['Operations'][0]
    assert operation['status'] == '200'
    assert operation['version'] == operation['response']['meta']['version']
    assert operation['response']['displayName'] == 'Bulk update'


@pytest.mark.parametrize(
    ('payload', 'detail'),
    [
        (
            {
                'schemas': [BULK_SCHEMA],
                'Operations': [{
                    'method': 'POST',
                    'path': '/Users',
                    'data': {'userName': 'x@example.com'},
                }],
            },
            'POST bulk operations require a non-empty bulkId',
        ),
        (
            {
                'schemas': [BULK_SCHEMA],
                'Operations': [
                    {'method': 'POST', 'path': '/Users', 'bulkId': 'duplicate', 'data': {}},
                    {'method': 'POST', 'path': '/Groups', 'bulkId': 'duplicate', 'data': {}},
                ],
            },
            "Duplicate bulkId 'duplicate'",
        ),
        (
            {
                'schemas': [BULK_SCHEMA],
                'failOnErrors': 'not-an-integer',
                'Operations': [{
                    'method': 'DELETE',
                    'path': '/Users/a@example.com',
                }],
            },
            'failOnErrors must be a non-negative integer',
        ),
        (
            {
                'schemas': [BULK_SCHEMA],
                'failOnErrors': -1,
                'Operations': [{
                    'method': 'DELETE',
                    'path': '/Users/a@example.com',
                }],
            },
            'failOnErrors must be a non-negative integer',
        ),
    ],
)
def test_scim_bulk_rejects_invalid_request_contract(app, client, payload, detail):
    response = client.post('/api/scim/v2/Bulk', json=payload, headers=auth_headers(app))

    assert response.status_code == 400
    assert response.get_json()['detail'] == detail


def test_scim_bulk_enforces_advertised_payload_limit_before_json_parsing(app, client):
    response = client.post(
        '/api/scim/v2/Bulk',
        data=b'x' * (1048576 + 1),
        headers=auth_headers(app),
    )

    assert response.status_code == 413
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['detail'] == 'Bulk request exceeds maxPayloadSize'


def test_scim_bulk_validation_error_includes_non_post_resource_location(app, client):
    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'PATCH',
                'path': '/Users/invalid-data@example.com',
                'data': [],
            }],
        },
        headers=auth_headers(app),
    )

    operation = response.get_json()['Operations'][0]
    assert operation['status'] == '400'
    assert operation['location'].endswith('/Users/invalid-data@example.com')


@pytest.mark.parametrize('method', ['PUT', 'PATCH', 'DELETE'])
def test_scim_bulk_accepts_canonical_percent_encoded_resource_paths(
    app,
    client,
    method,
):
    with app.app_context():
        user = create_user(localpart=f'bulk-{method.lower()}#question?percent%')
        user_id = scim_id(user)
        user_email = user.email
    direct_path = f'/api/scim/v2/Users/{urllib.parse.quote(user_id, safe="@")}'
    direct = client.get(direct_path, headers=auth_headers(app))
    location = direct.get_json()['meta']['location']
    bulk_path = urllib.parse.urlsplit(location).path.split('/scim/v2', 1)[1]
    if method == 'PUT':
        data = {
            'schemas': [USER_SCHEMA],
            'userName': user_email,
            'displayName': 'Bulk encoded PUT',
        }
    elif method == 'PATCH':
        data = {
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'displayName',
                'value': 'Bulk encoded PATCH',
            }],
        }
    else:
        data = None
    operation = {
        'method': method,
        'path': bulk_path,
    }
    if data is not None:
        operation['data'] = data

    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [operation],
        },
        headers=auth_headers(app),
    )

    result = response.get_json()['Operations'][0]
    assert result['status'] == ('204' if method == 'DELETE' else '200')
    assert result['location'] == location
    with app.app_context():
        user = scim_user(user_id)
        if method == 'DELETE':
            assert user.enabled is False
        else:
            assert user.displayed_name == f'Bulk encoded {method}'


@pytest.mark.parametrize('path', [
    'https://evil.example/Users/alice@example.com',
    '//[',
    '/Users/alice@example.com?active=false',
    '/Users/alice@example.com#fragment',
])
def test_scim_bulk_rejects_non_relative_resource_paths(app, client, path):
    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'DELETE',
                'path': path,
            }],
        },
        headers=auth_headers(app),
    )

    operation = response.get_json()['Operations'][0]
    assert operation['status'] == '400'
    assert operation['response']['scimType'] == 'invalidPath'


@pytest.mark.parametrize('resource_type', ['Users', 'Groups'])
def test_scim_unknown_opaque_resource_id_returns_scim_404(app, client, resource_type):
    response = client.get(
        f'/api/scim/v2/{resource_type}/not-an-email',
        headers=auth_headers(app),
    )

    assert response.status_code == 404
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['status'] == '404'


def test_scim_filters_validate_syntax_and_group_display_name_semantics(app, client):
    with app.app_context():
        label_id = scim_id(
            create_group(localpart='filter-label', comment='Operations Team')
        )
        address_id = scim_id(
            create_group(localpart='filter-address', comment='')
        )

    label = client.get(
        '/api/scim/v2/Groups?filter=displayName%20eq%20%22operations%20team%22',
        headers=auth_headers(app),
    )
    assert label.status_code == 200
    assert [group['id'] for group in label.get_json()['Resources']] == [label_id]

    address = client.get(
        '/api/scim/v2/Groups?filter=displayName%20eq%20%22filter-address@example.com%22',
        headers=auth_headers(app),
    )
    assert address.status_code == 200
    assert [group['id'] for group in address.get_json()['Resources']] == [address_id]

    malformed = client.get(
        '/api/scim/v2/Users?filter=userName%20eq%20not-an-email',
        headers=auth_headers(app),
    )
    assert malformed.status_code == 400
    assert malformed.get_json()['scimType'] == 'invalidFilter'


def test_scim_rejects_user_alias_address_collisions(app, client):
    with app.app_context():
        create_user(localpart='user-first')

    group_collision = client.post(
        '/api/scim/v2/Groups',
        json=group_payload(
            'user-first@example.com',
            display_name='User collision',
        ),
        headers=auth_headers(app),
    )
    assert group_collision.status_code == 409
    assert group_collision.get_json()['scimType'] == 'uniqueness'

    with app.app_context():
        create_group(localpart='group-first')

    user_collision = client.post(
        '/api/scim/v2/Users',
        json={
            'schemas': [USER_SCHEMA],
            'userName': 'group-first@example.com',
        },
        headers=auth_headers(app),
    )
    assert user_collision.status_code == 409
    assert user_collision.get_json()['scimType'] == 'uniqueness'
    with app.app_context():
        assert models.db.session.get(models.Alias, 'user-first@example.com') is None
        assert models.db.session.get(models.User, 'group-first@example.com') is None


def test_scim_external_group_destination_has_no_dangling_user_reference(app, client):
    with app.app_context():
        group_id = scim_id(create_group(localpart='external-member'))

    response = client.get(
        f'/api/scim/v2/Groups/{group_id}',
        headers=auth_headers(app),
    )
    payload = response.get_json()
    assert payload['members'] == []
    assert payload[GROUP_EXTENSION]['externalDestinations'] == [
        'original@example.net',
    ]


@pytest.mark.parametrize('resource_type', ['Users', 'Groups'])
def test_scim_put_requires_complete_identity_fields_without_mutation(app, client, resource_type):
    with app.app_context():
        resource = create_user() if resource_type == 'Users' else create_group()
        resource_id = scim_id(resource)

    response = client.put(
        f'/api/scim/v2/{resource_type}/{resource_id}',
        json={
            'schemas': (
                [USER_SCHEMA]
                if resource_type == 'Users'
                else [GROUP_SCHEMA, GROUP_EXTENSION]
            ),
        },
        headers=auth_headers(app),
    )
    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        if resource_type == 'Users':
            user = scim_user(resource_id)
            assert user.displayed_name == 'Original user'
            assert user.enabled is True
        else:
            group = scim_group(resource_id)
            assert group.comment == 'Original group'
            assert group.destination == ['original@example.net']


def test_scim_user_put_rejects_conflicting_immutable_email_identity(app, client):
    with app.app_context():
        user = create_user(localpart='identity-conflict')
        user_id = scim_id(user)
        user_email = user.email

    response = client.put(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [USER_SCHEMA],
            'userName': user_email,
            'emails': [{'value': 'different@example.com'}],
            'active': False,
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'mutability'
    with app.app_context():
        user = scim_user(user_id)
        assert user.enabled is True
        assert user.displayed_name == 'Original user'


@pytest.mark.parametrize('resource_type', ['Users', 'Groups'])
def test_scim_patch_requires_explicit_operation(app, client, resource_type):
    with app.app_context():
        resource = create_user() if resource_type == 'Users' else create_group()
        resource_id = scim_id(resource)

    response = client.patch(
        f'/api/scim/v2/{resource_type}/{resource_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'path': 'displayName',
                'value': 'Must not change',
            }],
        },
        headers=auth_headers(app),
    )
    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidSyntax'


def test_scim_rejects_incorrect_schema_envelope_without_mutation(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='wrong-schema'))

    response = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:Group'],
            'Operations': [{
                'op': 'replace',
                'path': 'active',
                'value': False,
            }],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        assert scim_user(user_id).enabled is True


def test_scim_discovery_self_links_are_retrievable_and_schemas_are_not_empty(app, client):
    resource_type = client.get(
        '/api/scim/v2/ResourceTypes/User',
        headers=auth_headers(app),
    )
    assert resource_type.status_code == 200
    assert resource_type.get_json()['endpoint'] == '/Users'

    schema_id = 'urn:ietf:params:scim:schemas:core:2.0:Group'
    schema = client.get(
        f'/api/scim/v2/Schemas/{schema_id}',
        headers=auth_headers(app),
    )
    assert schema.status_code == 200
    assert schema.get_json()['schemas'] == ['urn:ietf:params:scim:schemas:core:2.0:Schema']
    assert {attribute['name'] for attribute in schema.get_json()['attributes']} == {
        'externalId',
        'displayName',
        'members',
    }
    members = next(
        attribute
        for attribute in schema.get_json()['attributes']
        if attribute['name'] == 'members'
    )
    value = next(
        attribute
        for attribute in members['subAttributes']
        if attribute['name'] == 'value'
    )
    assert value['mutability'] == 'immutable'
    followed_schema = client.get(
        urllib.parse.urlsplit(schema.get_json()['meta']['location']).path,
        headers=auth_headers(app),
    )
    assert followed_schema.status_code == 200
    assert followed_schema.get_json()['id'] == schema_id


def test_scim_authentication_failure_uses_scim_error_envelope(app, client):
    response = client.get('/api/scim/v2/Users')

    assert response.status_code == 401
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['schemas'] == ['urn:ietf:params:scim:api:messages:2.0:Error']


def test_scim_attributes_projection_applies_to_single_and_list_resources(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='project-user'))
        group_id = scim_id(create_group(localpart='project-group'))

    user = client.get(
        f'/api/scim/v2/Users/{user_id}?attributes=userName',
        headers=auth_headers(app),
    )
    assert user.status_code == 200
    assert set(user.get_json()) == {'schemas', 'id', 'userName'}
    assert user.headers['ETag']

    users = client.get(
        '/api/scim/v2/Users?excludedAttributes=displayName,name,emails,active,meta',
        headers=auth_headers(app),
    )
    projected_user = next(
        resource for resource in users.get_json()['Resources']
        if resource['id'] == user_id
    )
    assert set(projected_user) == {'schemas', 'id', 'userName'}

    group = client.get(
        f'/api/scim/v2/Groups/{group_id}?attributes=members.value',
        headers=auth_headers(app),
    )
    group_payload = group.get_json()
    assert group.status_code == 200
    assert set(group_payload) == {
        'schemas',
        'id',
        'displayName',
        'members',
    }, group_payload
    assert group_payload['members'] == []
    assert group.headers['ETag']

    groups = client.get(
        '/api/scim/v2/Groups?excludedAttributes=displayName,members,meta',
        headers=auth_headers(app),
    )
    projected_group = next(
        resource for resource in groups.get_json()['Resources']
        if resource['id'] == group_id
    )
    assert set(projected_group) == {
        'schemas',
        'id',
        'displayName',
        GROUP_EXTENSION,
    }
    assert projected_group[GROUP_EXTENSION]['externalDestinations'] == [
        'original@example.net',
    ]

    id_only = client.get(
        f'/api/scim/v2/Users/{user_id}?attributes=id',
        headers=auth_headers(app),
    )
    assert set(id_only.get_json()) == {'schemas', 'id', 'userName'}


@pytest.mark.parametrize('query', [
    'attributes=',
    'excludedAttributes=',
    'attributes=userName&excludedAttributes=displayName',
    'attributes=name..formatted',
    'attributes=unknownAttribute',
    'attributes=name.unknownSubAttribute',
    f'attributes={GROUP_SCHEMA}:displayName',
])
def test_scim_rejects_invalid_projection_queries(app, client, query):
    response = client.get(
        f'/api/scim/v2/Users?{query}',
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'


def test_scim_projection_parent_dominates_children_and_never_returns_password(
    app,
    client,
):
    with app.app_context():
        user = create_user(localpart='projection-tree')
        user_id = scim_id(user)
        user_email = user.email

    parent = client.get(
        f'/api/scim/v2/Users/{user_id}?attributes=emails.value,emails',
        headers=auth_headers(app),
    )
    assert parent.status_code == 200
    assert parent.get_json()['emails'] == [{
        'value': user_email,
        'primary': True,
        'type': 'work',
    }]

    password = client.get(
        f'/api/scim/v2/Users/{user_id}?attributes=password',
        headers=auth_headers(app),
    )
    assert set(password.get_json()) == {'schemas', 'id', 'userName'}


def test_scim_projection_applies_to_mutation_responses_but_not_discovery(app, client):
    with app.app_context():
        user = create_user(localpart='project-mutation')
        user_id = scim_id(user)
        user_email = user.email

    replaced = client.put(
        f'/api/scim/v2/Users/{user_id}?attributes=id',
        json={
            'schemas': [USER_SCHEMA],
            'userName': user_email,
            'displayName': 'Projected mutation',
        },
        headers=auth_headers(app),
    )
    assert replaced.status_code == 200
    assert set(replaced.get_json()) == {'schemas', 'id', 'userName'}
    assert replaced.headers['ETag']
    assert replaced.headers['Content-Location']
    with app.app_context():
        assert scim_user(user_id).displayed_name == 'Projected mutation'

    discovery = client.get(
        '/api/scim/v2/Schemas?attributes=&excludedAttributes=id',
        headers=auth_headers(app),
    )
    assert discovery.status_code == 200
    assert discovery.get_json()['Resources']

    user_schema = next(
        resource
        for resource in discovery.get_json()['Resources']
        if resource['id'] == USER_SCHEMA
    )
    user_name = next(
        attribute
        for attribute in user_schema['attributes']
        if attribute['name'] == 'userName'
    )
    assert user_name['returned'] == 'always'


@pytest.mark.parametrize('schemas', [
    None,
    [],
    USER_SCHEMA,
    [USER_SCHEMA, USER_SCHEMA],
    [USER_SCHEMA, USER_SCHEMA.upper()],
    [USER_SCHEMA, GROUP_SCHEMA],
    [GROUP_SCHEMA],
])
def test_scim_user_create_requires_exact_unique_schema_without_mutation(
    app,
    client,
    schemas,
):
    payload = {'userName': 'schema-create@example.com'}
    if schemas is not None:
        payload['schemas'] = schemas

    response = client.post(
        '/api/scim/v2/Users',
        json=payload,
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        assert models.db.session.get(models.User, 'schema-create@example.com') is None


def test_scim_schema_uri_matching_is_case_insensitive(app, client):
    with app.app_context():
        create_domain()

    response = client.post(
        '/api/scim/v2/Users',
        json={
            'schemas': [USER_SCHEMA.upper()],
            'userName': 'case-schema@example.com',
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 201


def test_scim_put_patch_and_bulk_require_their_schema_envelopes(app, client):
    with app.app_context():
        user = create_user(localpart='schema-envelope')
        user_id = scim_id(user)
        user_email = user.email

    put_response = client.put(
        f'/api/scim/v2/Users/{user_id}',
        json={'userName': user_email, 'displayName': 'Must not change'},
        headers=auth_headers(app),
    )
    patch_response = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'Operations': [{
                'op': 'replace',
                'path': 'displayName',
                'value': 'Must not change',
            }],
        },
        headers=auth_headers(app),
    )
    bulk_response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'Operations': [{
                'method': 'PATCH',
                'path': f'/Users/{user_id}',
                'data': {
                    'schemas': [PATCH_SCHEMA],
                    'Operations': [{
                        'op': 'replace',
                        'path': 'displayName',
                        'value': 'Must not change',
                    }],
                },
            }],
        },
        headers=auth_headers(app),
    )

    assert put_response.status_code == 400
    assert patch_response.status_code == 400
    assert bulk_response.status_code == 400
    with app.app_context():
        assert scim_user(user_id).displayed_name == 'Original user'


@pytest.mark.parametrize('method', ['post', 'put'])
def test_scim_user_create_and_replace_require_explicit_username(app, client, method):
    with app.app_context():
        create_domain()
        user_id = 'required-username@example.com'
        if method == 'put':
            user_id = scim_id(create_user(localpart='required-username'))

    response = getattr(client, method)(
        '/api/scim/v2/Users' if method == 'post' else f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [USER_SCHEMA],
            'emails': [{'value': 'required-username@example.com'}],
            'active': False,
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        if method == 'post':
            assert scim_user(user_id) is None
        else:
            user = scim_user(user_id)
            assert user.enabled is True
            assert user.displayed_name == 'Original user'


@pytest.mark.parametrize('payload', [
    {
        'schemas': [USER_SCHEMA],
        'userName': 'ambiguous@example.com',
        'USERNAME': 'other@example.com',
    },
    {
        'schemas': [USER_SCHEMA],
        'userName': 'ambiguous@example.com',
        'name': {'formatted': 'First', 'FORMATTED': 'Second'},
    },
])
def test_scim_rejects_case_equivalent_attribute_collisions_without_mutation(
    app,
    client,
    payload,
):
    with app.app_context():
        create_domain()

    response = client.post(
        '/api/scim/v2/Users',
        json=payload,
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidSyntax'
    with app.app_context():
        assert models.db.session.get(models.User, 'ambiguous@example.com') is None


def test_scim_rejects_case_equivalent_patch_and_bulk_keys_without_mutation(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='ambiguous-operation'))

    patch_response = client.patch(
        f'/api/scim/v2/Users/{user_id}',
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'OP': 'remove',
                'path': 'active',
                'value': False,
            }],
        },
        headers=auth_headers(app),
    )
    bulk_response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'PATCH',
                'METHOD': 'DELETE',
                'path': f'/Users/{user_id}',
                'data': {
                    'schemas': [PATCH_SCHEMA],
                    'Operations': [{
                        'op': 'replace',
                        'path': 'active',
                        'value': False,
                    }],
                },
            }],
        },
        headers=auth_headers(app),
    )

    assert patch_response.status_code == 400
    assert patch_response.get_json()['scimType'] == 'invalidSyntax'
    assert bulk_response.status_code == 400
    assert bulk_response.get_json()['scimType'] == 'invalidSyntax'
    with app.app_context():
        assert scim_user(user_id).enabled is True


@pytest.mark.parametrize('duplicate_name', ['userName', r'user\u004eame'])
def test_scim_rejects_exact_duplicate_json_names_without_mutation(
    app,
    client,
    duplicate_name,
):
    with app.app_context():
        create_domain()

    response = client.post(
        '/api/scim/v2/Users',
        data=(
            '{"schemas":["' + USER_SCHEMA + '"],'
            '"userName":"first-duplicate@example.com",'
            '"' + duplicate_name + '":"second-duplicate@example.com"}'
        ),
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['scimType'] == 'invalidSyntax'
    with app.app_context():
        assert models.db.session.get(models.User, 'first-duplicate@example.com') is None
        assert models.db.session.get(models.User, 'second-duplicate@example.com') is None


def test_scim_rejects_nested_exact_duplicate_json_names_without_mutation(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='nested-duplicate'))

    response = client.post(
        '/api/scim/v2/Bulk',
        data=(
            '{"schemas":["' + BULK_SCHEMA + '"],"Operations":[{'
            '"method":"PATCH","method":"DELETE",'
            '"path":"/Users/' + user_id + '",'
            '"data":{"schemas":["' + PATCH_SCHEMA + '"],"Operations":[{'
            '"op":"replace","path":"active","value":false}]}}]}'
        ),
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['scimType'] == 'invalidSyntax'
    with app.app_context():
        assert scim_user(user_id).enabled is True


@pytest.mark.parametrize(
    'malformed',
    [
        'unquoted',
        'lowercase-weak',
        'wildcard-list',
        'unterminated',
        'space-in-opaque-tag',
    ],
)
def test_scim_rejects_malformed_if_match_without_mutation(
    app,
    client,
    malformed,
):
    with app.app_context():
        user_id = scim_id(create_user(localpart=f'malformed-{malformed}'))

    url = f'/api/scim/v2/Users/{user_id}'
    version = client.get(url, headers=auth_headers(app)).headers['ETag']
    values = {
        'unquoted': version[1:-1],
        'lowercase-weak': f'w/{version}',
        'wildcard-list': f'*, {version}',
        'unterminated': version[:-1],
        'space-in-opaque-tag': '"invalid entity tag"',
    }
    response = client.patch(
        url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'displayName',
                'value': 'Must not change',
            }],
        },
        headers={**auth_headers(app), 'If-Match': values[malformed]},
    )

    assert response.status_code == 400
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        assert scim_user(user_id).displayed_name == 'Original user'


def test_scim_rejects_malformed_if_none_match(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='malformed-if-none-match'))

    url = f'/api/scim/v2/Users/{user_id}'
    version = client.get(url, headers=auth_headers(app)).headers['ETag']
    response = client.get(
        url,
        headers={**auth_headers(app), 'If-None-Match': version[1:-1]},
    )

    assert response.status_code == 400
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['scimType'] == 'invalidValue'


def test_scim_accepts_empty_entity_tag_list_elements(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='empty-etag-elements'))

    url = f'/api/scim/v2/Users/{user_id}'
    version = client.get(url, headers=auth_headers(app)).headers['ETag']
    empty_only = client.patch(
        url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'displayName',
                'value': 'Must not change',
            }],
        },
        headers={**auth_headers(app), 'If-Match': ','},
    )
    assert_precondition_failed(empty_only)

    comma_in_opaque_tag = client.patch(
        url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'displayName',
                'value': 'Must not change',
            }],
        },
        headers={**auth_headers(app), 'If-Match': '"valid,opaque-tag"'},
    )
    assert_precondition_failed(comma_in_opaque_tag)

    response = client.patch(
        url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'displayName',
                'value': 'Empty elements ignored',
            }],
        },
        headers={**auth_headers(app), 'If-Match': f', {version},,'},
    )

    assert response.status_code == 200
    assert response.get_json()['displayName'] == 'Empty elements ignored'


def test_scim_accepts_ows_around_entity_tag_field_values(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='etag-ows'))

    url = f'/api/scim/v2/Users/{user_id}'
    version = client.get(url, headers=auth_headers(app)).headers['ETag']
    changed = client.patch(
        url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'displayName',
                'value': 'OWS accepted',
            }],
        },
        headers={**auth_headers(app), 'If-Match': f' \t{version}\t '},
    )

    assert changed.status_code == 200
    current_version = changed.headers['ETag']
    not_modified = client.get(
        url,
        headers={
            **auth_headers(app),
            'If-None-Match': f' \tW/{current_version}\t ',
        },
    )
    assert not_modified.status_code == 304


def test_scim_rejects_large_malformed_bulk_version_in_linear_time(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='large-malformed-version'))

    started = time.monotonic()
    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'DELETE',
                'path': f'/Users/{user_id}',
                'version': (' ' * 24000) + 'x',
            }],
        },
        headers=auth_headers(app),
    )
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert response.status_code == 200
    operation = response.get_json()['Operations'][0]
    assert operation['status'] == '400'
    assert operation['response']['scimType'] == 'invalidValue'
    with app.app_context():
        assert scim_user(user_id).enabled is True


def test_scim_validates_if_none_match_before_missing_resource(app, client):
    response = client.put(
        '/api/scim/v2/Users/missing@example.com',
        json={
            'schemas': [USER_SCHEMA],
            'userName': 'missing@example.com',
        },
        headers={**auth_headers(app), 'If-None-Match': 'unquoted'},
    )

    assert response.status_code == 400
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['scimType'] == 'invalidValue'


def test_scim_bulk_rejects_malformed_version_without_mutation(app, client):
    with app.app_context():
        user_id = scim_id(create_user(localpart='malformed-bulk-version'))

    url = f'/api/scim/v2/Users/{user_id}'
    version = client.get(url, headers=auth_headers(app)).headers['ETag']
    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'PATCH',
                'path': f'/Users/{user_id}',
                'version': version[1:-1],
                'data': {
                    'schemas': [PATCH_SCHEMA],
                    'Operations': [{
                        'op': 'replace',
                        'path': 'displayName',
                        'value': 'Must not change',
                    }],
                },
            }],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 200
    operation = response.get_json()['Operations'][0]
    assert operation['status'] == '400'
    assert operation['response']['scimType'] == 'invalidValue'
    with app.app_context():
        assert scim_user(user_id).displayed_name == 'Original user'


def test_scim_bulk_rejects_empty_operations_with_invalid_value(app, client):
    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [],
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.content_type == 'application/scim+json'
    assert response.get_json()['scimType'] == 'invalidValue'
    assert response.get_json()['detail'] == 'Operations must not be empty'
