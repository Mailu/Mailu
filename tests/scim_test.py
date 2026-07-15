from mailu import models


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


def test_scim_service_provider_config(app, client):
    rv = client.get('/api/scim/v2/ServiceProviderConfig', headers=auth_headers(app))

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['patch']['supported'] is True
    assert data['bulk']['supported'] is True
    assert data['etag']['supported'] is True
    assert data['authenticationSchemes'][0]['type'] == 'oauthbearertoken'


def test_scim_groups_are_backed_by_aliases(app, client):
    with app.app_context():
        create_domain()
        domain = models.db.session.get(models.Domain, 'example.com')
        user = models.User(localpart='alice', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()

    payload = {
        'schemas': ['urn:ietf:params:scim:schemas:core:2.0:Group'],
        'displayName': 'admins@example.com',
        'members': [{'value': 'alice@example.com'}],
    }
    rv = client.post('/api/scim/v2/Groups', json=payload, headers=auth_headers(app))

    assert rv.status_code == 201
    data = rv.get_json()
    assert data['id'] == 'admins@example.com'
    assert data['displayName'] == 'admins@example.com'
    assert data['members'][0]['value'] == 'alice@example.com'
    assert data['meta']['resourceType'] == 'Group'
    assert data['meta']['version'].startswith('W/"')

    with app.app_context():
        alias = models.db.session.get(models.Alias, 'admins@example.com')
        assert alias is not None
        assert alias.destination == ['alice@example.com']

    rv = client.get('/api/scim/v2/Groups/admins@example.com', headers=auth_headers(app))
    assert rv.status_code == 200
    assert rv.get_json()['members'][0]['value'] == 'alice@example.com'


def test_scim_group_patch_updates_alias_members(app, client):
    with app.app_context():
        domain = create_domain()
        alias = models.Alias(localpart='team', domain=domain, destination=['alice@example.com'])
        models.db.session.add(alias)
        models.db.session.commit()

    payload = {
        'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
        'Operations': [
            {'op': 'add', 'path': 'members', 'value': [{'value': 'bob@example.com'}]},
            {'op': 'remove', 'path': 'members', 'value': [{'value': 'alice@example.com'}]},
        ],
    }
    rv = client.patch('/api/scim/v2/Groups/team@example.com', json=payload, headers=auth_headers(app))

    assert rv.status_code == 200
    assert [member['value'] for member in rv.get_json()['members']] == ['bob@example.com']
    with app.app_context():
        alias = models.db.session.get(models.Alias, 'team@example.com')
        assert alias.destination == ['bob@example.com']



def test_scim_user_resources_include_etag_metadata(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='etag', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()

    rv = client.get('/api/scim/v2/Users/etag@example.com', headers=auth_headers(app))

    assert rv.status_code == 200
    meta = rv.get_json()['meta']
    assert meta['resourceType'] == 'User'
    assert meta['version'].startswith('W/"')
    assert meta['created']


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
    assert data['id'] == 'alice@example.com'
    assert data['userName'] == 'alice@example.com'
    assert data['active'] is True
    assert data['displayName'] == 'Alice Example'
    assert data['emails'][0]['value'] == 'alice@example.com'

    with app.app_context():
        user = models.db.session.get(models.User, 'alice@example.com')
        assert user is not None
        assert user.enabled is True
        assert user.displayed_name == 'Alice Example'

    rv = client.get('/api/scim/v2/Users/alice@example.com', headers=auth_headers(app))
    assert rv.status_code == 200
    assert rv.get_json()['userName'] == 'alice@example.com'


def test_scim_create_requires_existing_domain(app, client):
    payload = {'userName': 'missing@example.com'}
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

    payload = {
        'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
        'Operations': [
            {'op': 'replace', 'path': 'active', 'value': False},
            {'op': 'replace', 'path': 'displayName', 'value': 'Carol Disabled'},
        ],
    }
    rv = client.patch('/api/scim/v2/Users/carol@example.com', json=payload, headers=auth_headers(app))

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['active'] is False
    assert data['displayName'] == 'Carol Disabled'

    with app.app_context():
        user = models.db.session.get(models.User, 'carol@example.com')
        assert user.enabled is False
        assert user.displayed_name == 'Carol Disabled'


def test_scim_delete_disables_user_without_removing_mailbox(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='dave', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()

    rv = client.delete('/api/scim/v2/Users/dave@example.com', headers=auth_headers(app))

    assert rv.status_code == 204
    with app.app_context():
        user = models.db.session.get(models.User, 'dave@example.com')
        assert user is not None
        assert user.enabled is False


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

    payload = {
        'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
        'Operations': [{'op': 'replace', 'path': 'active', 'value': 'maybe'}],
    }
    rv = client.patch('/api/scim/v2/Users/frank@example.com', json=payload, headers=auth_headers(app))

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

    rv = client.patch(
        '/api/scim/v2/Users/grace@example.com',
        json={'Operations': ['not-an-object']},
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidSyntax'


def test_scim_create_handles_non_string_username_and_name(app, client):
    with app.app_context():
        create_domain('123.example')

    rv = client.post(
        '/api/scim/v2/Users',
        json={'userName': 123, 'name': 'not-an-object'},
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

    rv = client.patch(
        '/api/scim/v2/Users/heidi@example.com',
        json={'Operations': [{'op': 7, 'path': 9, 'value': 'ignored'}]},
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'mutability'
    with app.app_context():
        user = models.db.session.get(models.User, 'heidi@example.com')
        assert user.enabled is True


def test_scim_patch_rejects_remove_operation(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='ivan', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()

    rv = client.patch(
        '/api/scim/v2/Users/ivan@example.com',
        json={'Operations': [{'op': 'remove', 'path': 'displayName'}]},
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'mutability'


def test_scim_patch_rejects_unknown_path(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='judy', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()

    rv = client.patch(
        '/api/scim/v2/Users/judy@example.com',
        json={'Operations': [{'op': 'replace', 'path': 'title', 'value': 'Boss'}]},
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

    rv = client.patch(
        '/api/scim/v2/Users/mallory@example.com',
        json={'Operations': []},
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidValue'


def test_scim_create_rejects_non_string_password(app, client):
    with app.app_context():
        create_domain()

    rv = client.post(
        '/api/scim/v2/Users',
        json={'userName': 'nick@example.com', 'password': {'cleartext': 'nope'}},
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidValue'
    with app.app_context():
        assert models.db.session.get(models.User, 'nick@example.com') is None


def test_scim_patch_rejects_non_string_password(app, client):
    with app.app_context():
        domain = create_domain()
        user = models.User(localpart='olivia', domain=domain)
        user.set_password('secret')
        models.db.session.add(user)
        models.db.session.commit()

    rv = client.patch(
        '/api/scim/v2/Users/olivia@example.com',
        json={'Operations': [{'op': 'replace', 'path': 'password', 'value': ['bad']}]},
        headers=auth_headers(app),
    )

    assert rv.status_code == 400
    assert rv.get_json()['scimType'] == 'invalidValue'


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
                'data': {'userName': 'bulkuser@example.com', 'active': True},
            },
            {
                'method': 'POST',
                'path': '/Groups',
                'bulkId': 'group1',
                'data': {
                    'displayName': 'bulkgroup@example.com',
                    'members': [{'value': 'bulkuser@example.com'}],
                },
            },
        ],
    }
    rv = client.post('/api/scim/v2/Bulk', json=payload, headers=auth_headers(app))

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['schemas'] == ['urn:ietf:params:scim:api:messages:2.0:BulkResponse']
    assert [operation['status'] for operation in data['Operations']] == ['201', '201']
    with app.app_context():
        assert models.db.session.get(models.User, 'bulkuser@example.com') is not None
        alias = models.db.session.get(models.Alias, 'bulkgroup@example.com')
        assert alias is not None
        assert alias.destination == ['bulkuser@example.com']


def test_scim_bulk_stops_after_fail_on_errors(app, client):
    payload = {
        'failOnErrors': 1,
        'Operations': [
            {'method': 'POST', 'path': '/Users', 'data': {'userName': 'missing@example.com'}},
            {'method': 'POST', 'path': '/Users', 'data': {'userName': 'never@example.com'}},
        ],
    }
    rv = client.post('/api/scim/v2/Bulk', json=payload, headers=auth_headers(app))

    assert rv.status_code == 200
    operations = rv.get_json()['Operations']
    assert len(operations) == 1
    assert operations[0]['status'] == '404'
