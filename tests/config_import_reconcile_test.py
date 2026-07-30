"""Full config replacement must preserve persistent SCIM identity."""

from copy import deepcopy

import pytest
from marshmallow import ValidationError

from mailu import models
from mailu.schemas import MailuSchema, RenderYAML


def _domain(name='example.com'):
    domain = models.db.session.get(models.Domain, name)
    if domain is None:
        domain = models.Domain(name=name)
        models.db.session.add(domain)
        models.db.session.commit()
    return domain


def _user(localpart, *, domain=None):
    user = models.User(
        localpart=localpart,
        domain=domain or _domain(),
    )
    user.set_password('not-a-real-password')
    models.db.session.add(user)
    models.db.session.commit()
    return user


def _export_data():
    schema = MailuSchema(
        only=MailuSchema.Meta.order,
        context={'secrets': True},
    )
    return schema.dump(models.MailuConfig())


def _invoke(app, command, *arguments, input=None):
    return app.test_cli_runner().invoke(
        args=['mailu', command, *arguments],
        input=input,
    )


def _replace_import(data, *, dry_run=False):
    context = {
        'import': True,
        'update': False,
        'clear': True,
        'callback': lambda *args, **kwargs: None,
    }
    schema = MailuSchema(only=MailuSchema.Meta.order, context=context)
    source = RenderYAML.dumps(deepcopy(data))
    with models.db.session.no_autoflush:
        config = schema.loads(source)
    models.db.session.flush()
    config.check()
    if dry_run:
        models.db.session.rollback()
    else:
        models.db.session.commit()


def _managed_group(localpart='list'):
    member = _user('member')
    alias = models.Alias(
        localpart=localpart,
        domain=_domain(),
        destination=[
            member.email,
            'pager@outside.example',
        ],
    )
    models.db.session.add(alias)
    models.db.session.commit()
    group = models.create_scim_group_mapping(
        alias,
        external_id='directory-group-7',
    )
    models.db.session.flush()
    models.replace_scim_group_graph(
        group,
        member_ids=[member.scim_resource.id],
        external_destinations=['pager@outside.example'],
    )
    models.db.session.commit()
    return group, member


def test_export_default_import_preserves_user_identity_and_authority(
    app,
    tmp_path,
):
    with app.app_context():
        user = _user('alice')
        user.scim_resource.external_id = 'directory-user-7'
        models.db.session.commit()
        email = user.email
        resource_id = user.scim_resource.id
        generation = user.auth_generation
        password = user.password
        token = models.Token(user_email=user.email)
        token.set_password('a' * 32)
        models.db.session.add(token)
        models.db.session.commit()
        token_id = token.id
        token_password = token.password

    export_path = tmp_path / 'mailu-config.yaml'
    exported = _invoke(
        app,
        'config-export',
        '--secrets',
        '--output-file',
        str(export_path),
    )
    assert exported.exit_code == 0, exported.output
    source = export_path.read_text(encoding='utf-8')
    exported_data = RenderYAML.loads(source)
    assert 'scim_resource' not in exported_data['user'][0]

    imported = _invoke(
        app,
        'config-import',
        '--quiet',
        '-',
        input=source,
    )
    assert imported.exit_code == 0, imported.output

    with app.app_context():
        models.db.session.remove()
        restored = models.db.session.get(models.User, email)
        assert restored.scim_resource.id == resource_id
        assert restored.scim_resource.external_id == 'directory-user-7'
        assert restored.auth_generation == generation
        assert restored.password == password
        restored_token = models.db.session.get(models.Token, token_id)
        assert restored_token.password == token_password
        assert models.ScimResource.query.count() == 1
        assert models.ScimResource.query.filter(
            models.ScimResource.deleted_at.is_not(None)
        ).count() == 0


def test_export_default_import_preserves_managed_group_graph(app):
    with app.app_context():
        group, member = _managed_group()
        group_id = group.id
        member_id = member.scim_resource.id

        _replace_import(_export_data())

        restored = models.ScimResource.get_exact(
            group_id,
            resource_type='Group',
        )
        assert restored is group
        assert restored.external_id == 'directory-group-7'
        assert restored.alias.destination == [
            member.email,
            'pager@outside.example',
        ]
        assert [edge.member_id for edge in restored.member_edges] == [member_id]
        assert [
            destination.destination
            for destination in restored.destinations
        ] == ['pager@outside.example']


def test_export_default_import_preserves_owned_alias(app):
    with app.app_context():
        owner = _user('alias-owner')
        alias = models.Alias(
            localpart='owned',
            domain=_domain(),
            destination=['outside@example.net'],
            owner_email=owner.email,
            hostname='app.example.net',
        )
        models.db.session.add(alias)
        models.db.session.commit()
        owner_id = owner.scim_resource.id

        _replace_import(_export_data())

        restored = models.db.session.get(models.Alias, alias.email)
        assert restored.owner_email == owner.email
        assert restored.hostname == 'app.example.net'
        assert owner.scim_resource.id == owner_id


def test_default_import_prunes_group_member_without_reloading_projection(app):
    with app.app_context():
        group, member = _managed_group('pruned-member-list')
        group_id = group.id
        member_id = member.scim_resource.id
        data = _export_data()
        data['user'] = [
            item for item in data['user']
            if item['email'] != member.email
        ]

        _replace_import(data)

        restored = models.ScimResource.get_exact(
            group_id,
            resource_type='Group',
        )
        assert restored is group
        assert restored.member_edges == []
        assert restored.alias.destination == ['pager@outside.example']
        assert models.ScimResource.get_exact(
            member_id,
            active_only=False,
        ).deleted_at is not None


def test_default_import_prunes_absent_user_once(app):
    with app.app_context():
        retained = _user('retained')
        removed = _user('removed')
        retained_id = retained.scim_resource.id
        retained_generation = retained.auth_generation
        removed_id = removed.scim_resource.id
        data = _export_data()
        data['user'] = [
            item for item in data['user']
            if item['email'] == retained.email
        ]

        _replace_import(data)

        assert models.db.session.get(models.User, retained.email) is retained
        assert retained.scim_resource.id == retained_id
        assert retained.auth_generation == retained_generation
        assert models.db.session.get(models.User, removed.email) is None
        tombstone = models.ScimResource.get_exact(
            removed_id,
            active_only=False,
        )
        assert tombstone.deleted_at is not None
        assert models.ScimResource.query.count() == 2

        _replace_import(_export_data())

        assert models.db.session.get(models.User, retained.email) is retained
        assert retained.scim_resource.id == retained_id
        assert retained.auth_generation == retained_generation
        assert models.ScimResource.query.count() == 2
        assert models.ScimResource.get_exact(
            removed_id,
            active_only=False,
        ).deleted_at == tombstone.deleted_at


def test_default_import_releases_absent_user_address_before_alias_load(app):
    with app.app_context():
        user = _user('address-swap')
        email = user.email
        resource_id = user.scim_resource.id
        data = _export_data()
        data['user'] = [
            item for item in data['user']
            if item['email'] != email
        ]
        data['alias'].append({
            'email': email,
            'destination': ['outside@example.net'],
        })

        _replace_import(data)

        assert models.db.session.get(models.User, email) is None
        assert models.db.session.get(models.Alias, email) is not None
        assert models.ScimResource.get_exact(
            resource_id,
            active_only=False,
        ).deleted_at is not None


def test_default_import_dry_run_rolls_back_reconciliation(app):
    with app.app_context():
        retained = _user('dry-run')
        resource_id = retained.scim_resource.id
        data = _export_data()
        data['user'] = []

        _replace_import(data, dry_run=True)

        restored = models.db.session.get(models.User, retained.email)
        assert restored is not None
        assert restored.scim_resource.id == resource_id
        assert models.ScimResource.get_exact(resource_id) is not None


def test_failed_default_import_cannot_defer_rejected_dkim_write(
    app,
    tmp_path,
):
    with app.app_context():
        app.config['DKIM_PATH'] = str(
            tmp_path / '{domain}.{selector}.key'
        )
        domain = _domain('dkim.example')
        domain.generate_dkim_key()
        models.db.session.commit()
        key_path = domain._dkim_file()  # pylint: disable=protected-access
        with open(key_path, 'rb') as handle:
            original_key = handle.read()
        user = _user('dkim-user', domain=domain)
        data = _export_data()
        domain_data = next(
            item for item in data['domain']
            if item['name'] == domain.name
        )
        user_data = next(
            item for item in data['user']
            if item['email'] == user.email
        )
        domain_data['dkim_key'] = '-generate-'
        user_data.pop('password')

        result = _invoke(
            app,
            'config-import',
            '--quiet',
            '-',
            input=RenderYAML.dumps(data),
        )
        assert result.exit_code != 0
        with open(key_path, 'rb') as handle:
            assert handle.read() == original_key

        restored = models.db.session.get(models.Domain, domain.name)
        restored.signup_enabled = not restored.signup_enabled
        models.db.session.commit()
        with open(key_path, 'rb') as handle:
            assert handle.read() == original_key


def test_default_import_keeps_replacement_semantics(app):
    with app.app_context():
        domain = _domain()
        user = _user('replace', domain=domain)
        user.displayed_name = 'Old name'
        user.allow_spoofing = True
        user.forward_enabled = True
        user.forward_destination = [
            'old-one@outside.example',
            'old-two@outside.example',
        ]
        alias = models.Alias(
            localpart='replace-list',
            domain=domain,
            destination=[
                'old-one@outside.example',
                'old-two@outside.example',
            ],
        )
        models.db.session.add(alias)
        models.db.session.commit()
        resource_id = user.scim_resource.id
        generation = user.auth_generation
        data = _export_data()
        user_data = next(
            item for item in data['user']
            if item['email'] == user.email
        )
        for field in (
            'displayed_name',
            'allow_spoofing',
            'forward_enabled',
            'forward_destination',
        ):
            user_data.pop(field, None)
        alias_data = next(
            item for item in data['alias']
            if item['email'] == alias.email
        )
        alias_data['destination'] = ['new@outside.example']

        _replace_import(data)

        assert user.scim_resource.id == resource_id
        assert user.auth_generation == generation
        assert user.displayed_name == ''
        assert user.allow_spoofing is False
        assert user.forward_enabled is False
        assert user.forward_destination == []
        assert alias.destination == ['new@outside.example']


def test_default_import_rejects_duplicate_canonical_keys(app):
    with app.app_context():
        user = _user('duplicate')
        resource_id = user.scim_resource.id
        data = _export_data()
        duplicate = deepcopy(data['user'][0])
        duplicate['email'] = duplicate['email'].upper()
        data['user'].append(duplicate)

        with pytest.raises(ValidationError, match='Duplicate email'):
            _replace_import(data)
        models.db.session.rollback()

        assert models.db.session.get(models.User, user.email) is not None
        assert models.ScimResource.get_exact(resource_id) is not None


def test_default_import_rejects_duplicate_nested_token_identity(app):
    with app.app_context():
        first = _user('token-owner')
        second = _user('token-target')
        token = models.Token(user_email=first.email)
        token.set_password('b' * 32)
        models.db.session.add(token)
        models.db.session.commit()
        token_id = token.id
        data = _export_data()
        first_data = next(
            item for item in data['user']
            if item['email'] == first.email
        )
        second_data = next(
            item for item in data['user']
            if item['email'] == second.email
        )
        second_data.setdefault('tokens', []).append(
            deepcopy(first_data['tokens'][0])
        )

        with pytest.raises(ValidationError, match='Duplicate id'):
            _replace_import(data)
        models.db.session.rollback()

        restored = models.db.session.get(models.Token, token_id)
        assert restored.user_email == first.email


def test_default_import_rejects_duplicate_domain_alternative_owner(app):
    with app.app_context():
        first = _domain('first.example')
        second = _domain('second.example')
        alternative = models.Alternative(
            name='shared-alt.example',
            domain=first,
        )
        models.db.session.add(alternative)
        models.db.session.commit()
        data = _export_data()
        second_data = next(
            item for item in data['domain']
            if item['name'] == second.name
        )
        second_data.setdefault('alternatives', []).append(
            alternative.name.upper()
        )

        with pytest.raises(
            ValidationError,
            match='Duplicate related identity',
        ):
            _replace_import(data)
        models.db.session.rollback()

        restored = models.db.session.get(
            models.Alternative,
            alternative.name,
        )
        assert restored.domain_name == first.name


def test_default_import_rejects_duplicate_domain_access_owner(app):
    with app.app_context():
        domain = _domain()
        first = _user('grant-owner', domain=domain)
        second = _user('grant-target', domain=domain)
        access = models.DomainAccess(
            domain=domain,
            user=first,
        )
        models.db.session.add(access)
        models.db.session.commit()
        data = _export_data()
        second_data = next(
            item for item in data['user']
            if item['email'] == second.email
        )
        second_data.setdefault('domain_accesses', []).append(access.id)

        with pytest.raises(
            ValidationError,
            match='Duplicate related identity',
        ):
            _replace_import(data)
        models.db.session.rollback()

        restored = models.db.session.get(models.DomainAccess, access.id)
        assert restored.user_email == first.email


def test_default_import_preserves_idna_equivalent_primary_keys(app):
    with app.app_context():
        domain = _domain('täst.example')
        user = _user('alice', domain=domain)
        user_id = user.scim_resource.id
        data = _export_data()
        domain_data = next(
            item for item in data['domain']
            if item['name'] == domain.name
        )
        user_data = next(
            item for item in data['user']
            if item['email'] == user.email
        )
        domain_data['name'] = 'xn--tst-qla.example'
        user_data['email'] = 'alice@xn--tst-qla.example'

        _replace_import(data)

        assert models.db.session.get(models.Domain, domain.name) is domain
        assert models.db.session.get(models.User, user.email) is user
        assert user.scim_resource.id == user_id


def test_default_import_missing_required_password_is_validation_error(app):
    with app.app_context():
        user = _user('missing-password')
        resource_id = user.scim_resource.id
        data = _export_data()
        data['user'][0].pop('password')

        with pytest.raises(ValidationError) as error:
            _replace_import(data)
        models.db.session.rollback()

        assert 'password' in str(error.value)
        assert models.ScimResource.get_exact(resource_id) is not None


def test_default_import_tombstones_absent_managed_group(app):
    with app.app_context():
        group, _member = _managed_group('protected-list')
        data = _export_data()
        data['alias'] = [
            item for item in data['alias']
            if item['email'] != group.alias_email
        ]

        source = RenderYAML.dumps(data)
        group_id = group.id
        alias_email = group.alias_email

    result = _invoke(
        app,
        'config-import',
        '--quiet',
        '-',
        input=source,
    )
    assert result.exit_code == 0, result.output

    with app.app_context():
        models.db.session.remove()
        tombstone = models.ScimResource.get_exact(
            group_id,
            active_only=False,
        )
        assert tombstone.deleted_at is not None
        assert tombstone.alias_email is None
        assert models.db.session.get(
            models.Alias,
            alias_email,
        ) is None


def test_default_import_rejects_managed_group_mutation_atomically(app):
    with app.app_context():
        group, member = _managed_group('immutable-list')
        data = _export_data()
        alias_data = next(
            item for item in data['alias']
            if item['email'] == group.alias_email
        )
        alias_data['destination'] = ['changed@outside.example']
        source = RenderYAML.dumps(data)
        group_id = group.id
        member_id = member.scim_resource.id

    result = _invoke(
        app,
        'config-import',
        '--quiet',
        '-',
        input=source,
    )
    assert result.exit_code != 0
    assert 'provider-owned' in result.output

    with app.app_context():
        models.db.session.remove()
        restored = models.ScimResource.get_exact(group_id)
        assert restored.alias.destination == [
            'member@example.com',
            'pager@outside.example',
        ]
        assert [edge.member_id for edge in restored.member_edges] == [member_id]
