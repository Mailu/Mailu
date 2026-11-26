import re

import pytest

from mailu import models


USER_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:User'
GROUP_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Group'
PATCH_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:PatchOp'
BULK_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:BulkRequest'
GROUP_EXTENSION = 'https://mailu.io/schemas/scim/2.0/Group'
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-'
    r'[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)


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


def create_local_user(localpart='local-user'):
    domain = models.db.session.get(models.Domain, 'example.com') or create_domain()
    user = models.User(localpart=localpart, domain=domain)
    user.set_password('secret', keep_sessions=True)
    models.db.session.add(user)
    models.db.session.commit()
    return user


def provision_user(client, app, localpart, *, external_id=None, supplied_id=None):
    payload = {
        'schemas': [USER_SCHEMA],
        'userName': f'{localpart}@example.com',
        'password': 'secret',
        'active': True,
    }
    if external_id is not None:
        payload['externalId'] = external_id
    if supplied_id is not None:
        payload['id'] = supplied_id
    return client.post(
        '/api/scim/v2/Users',
        json=payload,
        headers=auth_headers(app),
    )


def provision_group(
    client,
    app,
    *,
    alias_address,
    display_name='Operations',
    members=None,
    external_destinations=None,
    supplied_id=None,
):
    extension = {
        'aliasAddress': alias_address,
        'externalDestinations': external_destinations or [],
    }
    payload = {
        'schemas': [GROUP_SCHEMA, GROUP_EXTENSION],
        'displayName': display_name,
        'members': [{'value': value} for value in (members or [])],
        GROUP_EXTENSION: extension,
    }
    if supplied_id is not None:
        payload['id'] = supplied_id
    return client.post(
        '/api/scim/v2/Groups',
        json=payload,
        headers=auth_headers(app),
    )


def test_new_local_user_gets_provider_uuid_mapping(app, client):
    with app.app_context():
        user = create_local_user()
        mapping = models.ScimResource.query.filter_by(
            resource_type='User',
            user_email=user.email,
            deleted_at=None,
        ).one()
        resource_id = mapping.id

    assert UUID_PATTERN.fullmatch(resource_id)
    response = client.get(
        f'/api/scim/v2/Users/{resource_id}',
        headers=auth_headers(app),
    )
    assert response.status_code == 200
    assert response.get_json()['id'] == resource_id
    assert client.get(
        '/api/scim/v2/Users/local-user@example.com',
        headers=auth_headers(app),
    ).status_code == 404


def test_user_create_ignores_client_id_and_persists_external_id(app, client):
    with app.app_context():
        create_domain()

    response = provision_user(
        client,
        app,
        'provisioned',
        external_id='directory-object-7',
        supplied_id='client-controlled-id',
    )

    assert response.status_code == 201
    resource = response.get_json()
    assert UUID_PATTERN.fullmatch(resource['id'])
    assert resource['id'] != 'client-controlled-id'
    assert resource['externalId'] == 'directory-object-7'
    assert response.headers['Location'].endswith(f"/Users/{resource['id']}")

    fetched = client.get(
        f"/api/scim/v2/Users/{resource['id']}",
        headers=auth_headers(app),
    )
    assert fetched.status_code == 200
    assert fetched.get_json()['externalId'] == 'directory-object-7'


@pytest.mark.parametrize(
    'user_name',
    [
        'not-an-email',
        'foo bar@example.com',
        'user@exa mple.com',
        'double@@example.com',
    ],
)
def test_user_create_rejects_malformed_username_without_mutation(
    app,
    client,
    user_name,
):
    with app.app_context():
        create_domain()

    response = client.post(
        '/api/scim/v2/Users',
        json={
            'schemas': [USER_SCHEMA],
            'userName': user_name,
            'active': True,
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        assert models.User.query.count() == 0
        assert models.ScimResource.query.count() == 0


def test_bulk_user_create_rejects_malformed_username_without_mutation(
    app,
    client,
):
    with app.app_context():
        create_domain()

    response = client.post(
        '/api/scim/v2/Bulk',
        json={
            'schemas': [BULK_SCHEMA],
            'Operations': [{
                'method': 'POST',
                'path': '/Users',
                'bulkId': 'invalid-user',
                'data': {
                    'schemas': [USER_SCHEMA],
                    'userName': 'not-an-email',
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
        assert models.User.query.count() == 0
        assert models.ScimResource.query.count() == 0


def test_user_create_accepts_valid_idna_domain(app, client):
    with app.app_context():
        create_domain('bücher.example')

    response = client.post(
        '/api/scim/v2/Users',
        json={
            'schemas': [USER_SCHEMA],
            'userName': 'unicode@bücher.example',
            'active': True,
        },
        headers=auth_headers(app),
    )

    assert response.status_code == 201
    assert response.get_json()['userName'] == 'unicode@bücher.example'


def test_user_patch_rejects_partial_immutable_and_missing_value(app, client):
    with app.app_context():
        create_domain()
    created = provision_user(
        client,
        app,
        'patch-contract',
        external_id='keep-me',
    ).get_json()
    resource_url = f"/api/scim/v2/Users/{created['id']}"

    partial = client.patch(
        resource_url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'value': {
                    'userName': 'changed@example.com',
                    'active': False,
                },
            }],
        },
        headers=auth_headers(app),
    )
    assert partial.status_code == 400
    assert partial.get_json()['scimType'] == 'mutability'

    missing = client.patch(
        resource_url,
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': 'externalId',
            }],
        },
        headers=auth_headers(app),
    )
    assert missing.status_code == 400
    assert missing.get_json()['scimType'] == 'invalidValue'

    unchanged = client.get(resource_url, headers=auth_headers(app)).get_json()
    assert unchanged['active'] is True
    assert unchanged['externalId'] == 'keep-me'


def test_user_patch_applies_final_active_value_once(app, client):
    with app.app_context():
        create_domain()
    created = provision_user(client, app, 'final-active').get_json()
    with app.app_context():
        user = models.db.session.get(models.User, 'final-active@example.com')
        generation = user.auth_generation

    response = client.patch(
        f"/api/scim/v2/Users/{created['id']}",
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [
                {'op': 'replace', 'path': 'active', 'value': False},
                {'op': 'replace', 'path': 'active', 'value': True},
            ],
        },
        headers=auth_headers(app),
    )
    assert response.status_code == 200
    assert response.get_json()['active'] is True
    with app.app_context():
        user = models.db.session.get(models.User, 'final-active@example.com')
        assert user.auth_generation == generation


def test_group_request_types_and_pathless_immutable_noop(app, client):
    with app.app_context():
        create_domain()
    invalid = client.post(
        '/api/scim/v2/Groups',
        json={
            'schemas': [GROUP_SCHEMA, GROUP_EXTENSION],
            'displayName': 'Invalid destination type',
            GROUP_EXTENSION: {
                'aliasAddress': 'invalid-type@example.com',
                'externalDestinations': '',
            },
        },
        headers=auth_headers(app),
    )
    assert invalid.status_code == 400
    assert invalid.get_json()['scimType'] == 'invalidValue'

    created = provision_group(
        client,
        app,
        alias_address='pathless-noop@example.com',
    ).get_json()
    patched = client.patch(
        f"/api/scim/v2/Groups/{created['id']}",
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'value': {
                    GROUP_EXTENSION: {
                        'aliasAddress': 'pathless-noop@example.com',
                        'externalDestinations': ['outside@example.net'],
                    },
                },
            }],
        },
        headers=auth_headers(app),
    )
    assert patched.status_code == 200
    assert patched.get_json()[GROUP_EXTENSION][
        'externalDestinations'
    ] == ['outside@example.net']


@pytest.mark.parametrize(
    'extra',
    [
        {'failOnErrors': 1.5},
        {'operation_bulk_id': 'not-a-create'},
    ],
)
def test_bulk_rejects_non_integer_limit_and_non_post_bulk_id(
    app,
    client,
    extra,
):
    request = {
        'schemas': [BULK_SCHEMA],
        'Operations': [{
            'method': 'PATCH',
            'path': '/Users/missing',
            'data': {
                'schemas': [PATCH_SCHEMA],
                'Operations': [{
                    'op': 'replace',
                    'path': 'active',
                    'value': False,
                }],
            },
        }],
    }
    if 'failOnErrors' in extra:
        request['failOnErrors'] = extra['failOnErrors']
    if 'operation_bulk_id' in extra:
        request['Operations'][0]['bulkId'] = extra['operation_bulk_id']

    response = client.post(
        '/api/scim/v2/Bulk',
        json=request,
        headers=auth_headers(app),
    )
    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'


def test_user_delete_tombstones_id_and_reserves_subject_address(app, client):
    with app.app_context():
        create_domain()
    created = provision_user(client, app, 'deleted-user')
    assert created.status_code == 201
    old_id = created.get_json()['id']

    deleted = client.delete(
        f'/api/scim/v2/Users/{old_id}',
        headers=auth_headers(app),
    )
    assert deleted.status_code == 204

    for method in ('get', 'delete'):
        response = getattr(client, method)(
            f'/api/scim/v2/Users/{old_id}',
            headers=auth_headers(app),
        )
        assert response.status_code == 404

    listing = client.get('/api/scim/v2/Users', headers=auth_headers(app))
    assert old_id not in {
        resource['id'] for resource in listing.get_json()['Resources']
    }

    with app.app_context():
        retained = models.db.session.get(models.User, 'deleted-user@example.com')
        tombstone = models.db.session.get(models.ScimResource, old_id)
        assert retained is not None
        assert retained.enabled is False
        assert tombstone.deleted_at is not None
        assert tombstone.user_email is None

    recreated = provision_user(client, app, 'deleted-user')
    assert recreated.status_code == 409
    assert recreated.get_json()['scimType'] == 'uniqueness'
    assert client.get(
        f'/api/scim/v2/Users/{old_id}',
        headers=auth_headers(app),
    ).status_code == 404


def test_user_delete_scrubs_authority_and_rejects_reprovision(app, client):
    with app.app_context():
        create_domain()
    created = provision_user(client, app, 'prior-authority')
    assert created.status_code == 201
    old_id = created.get_json()['id']

    with app.app_context():
        user = models.db.session.get(
            models.User,
            'prior-authority@example.com',
        )
        example_domain = models.db.session.get(models.Domain, 'example.com')
        managed_domain = models.Domain(name='managed.example')
        user.global_admin = True
        user.allow_spoofing = True
        user.forward_enabled = True
        user.forward_destination = ['old-owner@outside.example']
        user.reply_enabled = True
        user.manager_of.append(managed_domain)

        token = models.Token(user=user)
        token.set_password('a' * 32)
        fetch = models.Fetch(
            user=user,
            protocol='imap',
            host='imap.outside.example',
            port=993,
            tls=True,
            username='old-owner',
            password='old-remote-secret',
        )
        access = models.DomainAccess(
            domain=managed_domain,
            user=user,
        )
        owned_alias = models.Alias(
            localpart='old-private-alias',
            domain=example_domain,
            destination=[user.email],
            owner=user,
        )
        models.db.session.add_all([
            managed_domain,
            token,
            fetch,
            access,
            owned_alias,
        ])
        models.db.session.commit()

    deleted = client.delete(
        f'/api/scim/v2/Users/{old_id}',
        headers=auth_headers(app),
    )
    assert deleted.status_code == 204

    with app.app_context():
        user = models.db.session.get(
            models.User,
            'prior-authority@example.com',
        )
        assert user is not None
        assert user.enabled is False
        assert user.global_admin is False
        assert user.allow_spoofing is False
        assert user.forward_enabled is False
        assert user.forward_destination == []
        assert user.reply_enabled is False
        assert user.tokens == []
        assert user.fetches == []
        assert user.manager_of == []
        assert user.domain_accesses == []
        assert models.db.session.get(
            models.Alias,
            'old-private-alias@example.com',
        ) is None

    recreated = provision_user(client, app, 'prior-authority')
    assert recreated.status_code == 409
    assert recreated.get_json()['scimType'] == 'uniqueness'

    with app.app_context():
        user = models.db.session.get(
            models.User,
            'prior-authority@example.com',
        )
        assert user.enabled is False
        assert user.global_admin is False
        assert user.allow_spoofing is False
        assert user.forward_enabled is False
        assert user.forward_destination == []
        assert user.reply_enabled is False
        assert user.tokens == []
        assert user.fetches == []
        assert user.manager_of == []
        assert user.domain_accesses == []


def test_unmanaged_alias_is_not_a_scim_group(app, client):
    with app.app_context():
        domain = create_domain()
        alias = models.Alias(
            localpart='ordinary',
            domain=domain,
            destination=['outside@example.net'],
        )
        models.db.session.add(alias)
        models.db.session.commit()

    listing = client.get('/api/scim/v2/Groups', headers=auth_headers(app))
    assert listing.status_code == 200
    assert listing.get_json()['totalResults'] == 0
    assert client.get(
        '/api/scim/v2/Groups/ordinary@example.com',
        headers=auth_headers(app),
    ).status_code == 404


def test_group_separates_member_ids_from_external_destinations(app, client):
    with app.app_context():
        create_domain()
    member_response = provision_user(client, app, 'member')
    assert member_response.status_code == 201
    member_id = member_response.get_json()['id']

    response = provision_group(
        client,
        app,
        alias_address='operations@example.com',
        display_name='Human operations label',
        members=[member_id],
        external_destinations=['pager@example.net'],
        supplied_id='client-group-id',
    )

    assert response.status_code == 201
    resource = response.get_json()
    assert UUID_PATTERN.fullmatch(resource['id'])
    assert resource['id'] != 'client-group-id'
    assert resource['displayName'] == 'Human operations label'
    assert resource['schemas'] == [GROUP_SCHEMA, GROUP_EXTENSION]
    assert resource['members'] == [{
        'value': member_id,
        '$ref': resource['members'][0]['$ref'],
        'display': resource['members'][0]['display'],
        'type': 'User',
    }]
    assert resource['members'][0]['$ref'].endswith(f'/Users/{member_id}')
    assert resource[GROUP_EXTENSION] == {
        'aliasAddress': 'operations@example.com',
        'externalDestinations': ['pager@example.net'],
    }

    with app.app_context():
        alias = models.db.session.get(models.Alias, 'operations@example.com')
        assert alias.destination == [
            'member@example.com',
            'pager@example.net',
        ]


def test_group_rejects_unknown_or_tombstoned_member_without_mutation(app, client):
    with app.app_context():
        create_domain()
    response = provision_group(
        client,
        app,
        alias_address='invalid-members@example.com',
        members=['00000000-0000-4000-8000-000000000000'],
    )
    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'
    assert 'member' in response.get_json()['detail'].lower()
    assert 'active' in response.get_json()['detail'].lower()
    with app.app_context():
        assert models.db.session.get(
            models.Alias,
            'invalid-members@example.com',
        ) is None


def test_group_cycle_is_rejected_atomically(app, client):
    with app.app_context():
        create_domain()
    group_a = provision_group(
        client,
        app,
        alias_address='a@example.com',
        display_name='A',
    ).get_json()
    group_b = provision_group(
        client,
        app,
        alias_address='b@example.com',
        display_name='B',
        members=[group_a['id']],
    ).get_json()

    response = client.patch(
        f"/api/scim/v2/Groups/{group_a['id']}",
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'add',
                'path': 'members',
                'value': [{'value': group_b['id']}],
            }],
        },
        headers=auth_headers(app),
    )
    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'invalidValue'

    unchanged = client.get(
        f"/api/scim/v2/Groups/{group_a['id']}",
        headers=auth_headers(app),
    )
    assert unchanged.get_json()['members'] == []


def test_group_extension_patch_and_projection(app, client):
    with app.app_context():
        create_domain()
    created = provision_group(
        client,
        app,
        alias_address='projected@example.com',
        display_name='Projected',
        external_destinations=['one@example.net'],
    ).get_json()

    patched = client.patch(
        f"/api/scim/v2/Groups/{created['id']}",
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'add',
                'path': f'{GROUP_EXTENSION}:externalDestinations',
                'value': ['two@example.net'],
            }],
        },
        headers=auth_headers(app),
    )
    assert patched.status_code == 200
    assert patched.get_json()[GROUP_EXTENSION]['externalDestinations'] == [
        'one@example.net',
        'two@example.net',
    ]

    projected = client.get(
        f"/api/scim/v2/Groups/{created['id']}",
        query_string={
            'attributes': f'{GROUP_EXTENSION}:externalDestinations',
        },
        headers=auth_headers(app),
    )
    assert projected.status_code == 200
    assert projected.get_json() == {
        'schemas': [GROUP_SCHEMA, GROUP_EXTENSION],
        'id': created['id'],
        'displayName': 'Projected',
        GROUP_EXTENSION: {
            'externalDestinations': [
                'one@example.net',
                'two@example.net',
            ],
        },
    }


def test_group_alias_address_is_immutable(app, client):
    with app.app_context():
        create_domain()
    created = provision_group(
        client,
        app,
        alias_address='immutable@example.com',
    ).get_json()

    response = client.patch(
        f"/api/scim/v2/Groups/{created['id']}",
        json={
            'schemas': [PATCH_SCHEMA],
            'Operations': [{
                'op': 'replace',
                'path': f'{GROUP_EXTENSION}:aliasAddress',
                'value': 'changed@example.com',
            }],
        },
        headers=auth_headers(app),
    )
    assert response.status_code == 400
    assert response.get_json()['scimType'] == 'mutability'


@pytest.mark.parametrize('extra_length', [0, 1])
def test_group_materialized_destination_boundary_is_portable(
    app,
    client,
    extra_length,
):
    with app.app_context():
        create_domain()
    # One address whose serialized length is exactly the routing column limit,
    # then one character over. Domain syntax is not the point of this test, so
    # use many individually valid short addresses instead.
    addresses = []
    serialized = ''
    index = 0
    while len(serialized) < 1023 + extra_length:
        candidate = f'd{index}@x.example'
        next_value = ','.join(addresses + [candidate])
        if len(next_value) > 1023 + extra_length:
            break
        addresses.append(candidate)
        serialized = next_value
        index += 1
    if extra_length:
        addresses.append('overflow@x.example')

    response = provision_group(
        client,
        app,
        alias_address=f'boundary-{extra_length}@example.com',
        external_destinations=addresses,
    )
    if len(','.join(sorted(set(addresses)))) <= 1023:
        assert response.status_code == 201
    else:
        assert response.status_code == 400
        assert response.get_json()['scimType'] == 'invalidValue'
        assert '1023' in response.get_json()['detail']
