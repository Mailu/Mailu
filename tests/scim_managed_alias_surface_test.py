"""User-facing contracts for ordinary writes to SCIM-managed Aliases."""

import pytest

from mailu import models


def _setup_managed_alias():
    domain = models.Domain(name='example.com')
    admin = models.User(
        localpart='admin',
        domain=domain,
        global_admin=True,
    )
    admin.set_password('not-a-real-password')
    alias = models.Alias(
        localpart='managed',
        domain=domain,
        destination=['kept@outside.example'],
        comment='Managed group',
    )
    models.db.session.add_all([domain, admin, alias])
    models.db.session.commit()
    group = models.create_scim_group_mapping(alias)
    models.replace_scim_group_graph(
        group,
        member_ids=[],
        external_destinations=['kept@outside.example'],
    )
    models.db.session.commit()
    return admin.email, alias.email, group.id


def _assert_graph_unchanged(alias_email, group_id):
    alias = models.db.session.get(models.Alias, alias_email)
    group = models.ScimResource.get_exact(group_id, resource_type='Group')
    assert alias is not None
    assert group is not None
    assert alias.scim_resource is group
    assert alias.comment == 'Managed group'
    assert alias.destination == ['kept@outside.example']
    assert [edge.destination for edge in group.destinations] == [
        'kept@outside.example'
    ]


def _bearer(app):
    return {'Authorization': f'Bearer {app.config["API_TOKEN"]}'}


def _add_removable_domain(name='removable.example'):
    domain = models.Domain(name=name)
    models.db.session.add(domain)
    models.db.session.commit()
    return domain


def _login(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_auth_generation'] = user.auth_generation
        session['_fresh'] = True


@pytest.mark.parametrize('method', ['patch', 'delete'])
def test_v1_managed_alias_write_returns_conflict(app, client, method):
    with app.app_context():
        admin_email, alias_email, group_id = _setup_managed_alias()

    if method == 'patch':
        response = client.patch(
            f'/api/v1/alias/{alias_email}',
            json={
                'comment': 'ordinary edit',
                'destination': [admin_email],
            },
            headers=_bearer(app),
        )
    else:
        response = client.delete(
            f'/api/v1/alias/{alias_email}',
            headers=_bearer(app),
        )
    assert response.status_code == 409
    assert response.get_json() == {
        'code': 409,
        'message': f'Alias {alias_email} is exclusively SCIM managed',
    }

    assert client.get(
        f'/api/v1/alias/{alias_email}',
        headers=_bearer(app),
    ).status_code == 200
    with app.app_context():
        _assert_graph_unchanged(alias_email, group_id)


def test_v1_managed_alias_blocks_domain_cascade_and_rolls_back(app, client):
    with app.app_context():
        _admin_email, alias_email, group_id = _setup_managed_alias()
        _add_removable_domain()

    response = client.delete(
        '/api/v1/domain/example.com',
        headers=_bearer(app),
    )
    assert response.status_code == 409
    assert response.get_json() == {
        'code': 409,
        'message': f'Alias {alias_email} is exclusively SCIM managed',
    }

    follow_up = client.delete(
        '/api/v1/domain/removable.example',
        headers=_bearer(app),
    )
    assert follow_up.status_code == 200, follow_up.get_json()
    with app.app_context():
        assert models.db.session.get(models.Domain, 'example.com') is not None
        assert models.db.session.get(
            models.Domain,
            'removable.example',
        ) is None
        _assert_graph_unchanged(alias_email, group_id)


@pytest.mark.parametrize('operation', ['edit', 'delete'])
def test_ui_managed_alias_write_flashes_error(app, client, operation):
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        admin_email, alias_email, group_id = _setup_managed_alias()
        _login(client, models.db.session.get(models.User, admin_email))

    prefix = app.config['WEB_ADMIN']
    if operation == 'edit':
        response = client.post(
            f'{prefix}/alias/edit/{alias_email}',
            data={
                'localpart': 'managed',
                'destination': [admin_email],
                'comment': 'ordinary edit',
                'submit': 'Save',
            },
            follow_redirects=True,
        )
    else:
        response = client.post(
            f'{prefix}/alias/delete/{alias_email}',
            data={'submit': 'Confirm'},
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert b'exclusively SCIM managed' in response.data

    with app.app_context():
        _assert_graph_unchanged(alias_email, group_id)


def test_ui_managed_alias_blocks_domain_cascade_and_rolls_back(app, client):
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        admin_email, alias_email, group_id = _setup_managed_alias()
        _add_removable_domain()
        _login(client, models.db.session.get(models.User, admin_email))

    prefix = app.config['WEB_ADMIN']
    response = client.post(
        f'{prefix}/domain/delete/example.com',
        data={'submit': 'Confirm'},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b'exclusively SCIM managed' in response.data

    follow_up = client.post(
        f'{prefix}/domain/delete/removable.example',
        data={'submit': 'Confirm'},
        follow_redirects=True,
    )
    assert follow_up.status_code == 200
    with app.app_context():
        assert models.db.session.get(models.Domain, 'example.com') is not None
        assert models.db.session.get(
            models.Domain,
            'removable.example',
        ) is None
        _assert_graph_unchanged(alias_email, group_id)


def test_cli_managed_alias_delete_is_a_clean_error_and_rolls_back(app):
    with app.app_context():
        _admin_email, alias_email, group_id = _setup_managed_alias()
        removable = models.Alias(
            localpart='removable',
            domain=models.db.session.get(models.Domain, 'example.com'),
            destination=['outside@example.net'],
        )
        models.db.session.add(removable)
        models.db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=['mailu', 'alias-delete', alias_email])
    assert result.exit_code != 0
    assert 'exclusively SCIM managed' in result.output

    follow_up = runner.invoke(
        args=['mailu', 'alias-delete', 'removable@example.com'],
    )
    assert follow_up.exit_code == 0, follow_up.output

    with app.app_context():
        _assert_graph_unchanged(alias_email, group_id)
        assert models.db.session.get(
            models.Alias,
            'removable@example.com',
        ) is None


def test_cli_config_update_is_a_clean_error_and_rolls_back(app):
    with app.app_context():
        _admin_email, alias_email, group_id = _setup_managed_alias()
        removable = models.Alias(
            localpart='removable',
            domain=models.db.session.get(models.Domain, 'example.com'),
            destination=['outside@example.net'],
        )
        models.db.session.add(removable)
        models.db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(
        args=['mailu', 'config-update'],
        input='''
domains:
  - name: example.com
    max_users: 99
aliases:
  - localpart: managed
    domain: example.com
    destination: changed@outside.example
''',
    )
    assert result.exit_code != 0
    assert 'exclusively SCIM managed' in result.output

    follow_up = runner.invoke(
        args=['mailu', 'alias-delete', 'removable@example.com'],
    )
    assert follow_up.exit_code == 0, follow_up.output

    with app.app_context():
        assert models.db.session.get(models.Domain, 'example.com').max_users == -1
        _assert_graph_unchanged(alias_email, group_id)
        assert models.db.session.get(
            models.Alias,
            'removable@example.com',
        ) is None


@pytest.mark.parametrize('retain_managed_domain', [True, False])
def test_cli_config_update_delete_objects_is_atomic_for_managed_alias(
    app,
    retain_managed_domain,
):
    with app.app_context():
        admin_email, alias_email, group_id = _setup_managed_alias()
        ordinary_domain = _add_removable_domain('ordinary.example')
        removable = models.Alias(
            localpart='removable',
            domain=ordinary_domain,
            destination=['outside@example.net'],
        )
        models.db.session.add(removable)
        models.db.session.commit()

    config = [
        'domains:',
        '  - name: ordinary.example',
        '    max_users: 99',
    ]
    if retain_managed_domain:
        config.extend([
            '  - name: example.com',
            '    max_users: 99',
        ])
    config.extend(['aliases: []', ''])

    runner = app.test_cli_runner()
    result = runner.invoke(
        args=['mailu', 'config-update', '--delete-objects', 'true'],
        input='\n'.join(config),
    )
    assert result.exit_code != 0
    assert 'exclusively SCIM managed' in result.output

    follow_up = runner.invoke(
        args=['mailu', 'alias-delete', 'removable@ordinary.example'],
    )
    assert follow_up.exit_code == 0, follow_up.output

    with app.app_context():
        assert models.db.session.get(
            models.Domain,
            'ordinary.example',
        ).max_users == -1
        assert models.db.session.get(models.Domain, 'example.com') is not None
        assert models.db.session.get(models.User, admin_email) is not None
        _assert_graph_unchanged(alias_email, group_id)
        assert models.db.session.get(
            models.Alias,
            'removable@ordinary.example',
        ) is None
