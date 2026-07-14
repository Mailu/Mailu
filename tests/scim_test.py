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
    assert data['bulk']['supported'] is False
    assert data['authenticationSchemes'][0]['type'] == 'oauthbearertoken'


def test_scim_groups_are_explicitly_unsupported(app, client):
    rv = client.get('/api/scim/v2/Groups', headers=auth_headers(app))

    assert rv.status_code == 200
    assert rv.get_json()['Resources'] == []

    rv = client.post('/api/scim/v2/Groups', json={'displayName': 'admins'}, headers=auth_headers(app))
    assert rv.status_code == 501


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
