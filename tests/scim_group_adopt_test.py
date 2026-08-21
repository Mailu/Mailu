"""Focused tests for the explicit legacy-alias SCIM adoption command."""

import os
import re
import select
import subprocess
import sys

import pytest
from sqlalchemy.orm import Session

from mailu import models


GROUP_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Group'
GROUP_EXTENSION = 'https://mailu.io/schemas/scim/2.0/Group'
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-'
    r'[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)
ALIAS_UPDATE_PROCESS = r'''
from mailu import configuration, create_app_from_config, models

app = create_app_from_config(configuration.ConfigManager())
app.config['TESTING'] = True
with app.app_context():
    original_lock = models.lock_scim_graph

    def observed_lock(session=None):
        print('LOCK_ATTEMPT', flush=True)
        return original_lock(session)

    models.lock_scim_graph = observed_lock
    alias = models.db.session.get(models.Alias, 'lock-winner@example.com')
    alias.destination = ['lost@outside.example']
    try:
        models.db.session.commit()
    except models.ScimManagedAliasError as exc:
        models.db.session.rollback()
        print(f'REJECTED:{exc}', flush=True)
    else:
        print('UPDATED', flush=True)
        raise SystemExit(2)
    finally:
        models.db.session.remove()
'''


def _domain(name='example.com'):
    domain = models.db.session.get(models.Domain, name)
    if domain is None:
        domain = models.Domain(name=name)
        models.db.session.add(domain)
        models.db.session.commit()
    return domain


def _user(localpart='member'):
    user = models.User(localpart=localpart, domain=_domain())
    user.set_password('not-a-real-password')
    models.db.session.add(user)
    models.db.session.commit()
    return user


def _alias(localpart, destination, **values):
    alias = models.Alias(
        localpart=localpart,
        domain=_domain(),
        destination=destination,
        **values,
    )
    models.db.session.add(alias)
    models.db.session.commit()
    return alias


def _invoke(app, *arguments):
    return app.test_cli_runner().invoke(
        args=['mailu', 'scim-group-adopt', *arguments],
    )


def test_adopt_normalizes_existing_routing_without_changing_delivery(app):
    with app.app_context():
        member = _user()
        member_id = member.scim_resource.id
        _alias(
            'legacy-list',
            ['member@example.com', 'pager@outside.example'],
        )

    result = _invoke(
        app,
        'legacy-list@example.com',
        '--external-id',
        'directory-group-7',
    )
    assert result.exit_code == 0, result.output

    with app.app_context():
        alias = models.db.session.get(
            models.Alias,
            'legacy-list@example.com',
        )
        group = alias.scim_resource
        assert group is not None
        assert UUID_PATTERN.fullmatch(group.id)
        assert group.external_id == 'directory-group-7'
        assert group.alias.destination == [
            'member@example.com',
            'pager@outside.example',
        ]
        assert [edge.member_id for edge in group.member_edges] == [member_id]
        assert [
            edge.destination for edge in group.destinations
        ] == ['pager@outside.example']


def test_adopt_is_one_shot_and_second_attempt_changes_nothing(app):
    with app.app_context():
        _alias('one-shot', ['pager@outside.example'])

    first = _invoke(app, 'one-shot@example.com')
    assert first.exit_code == 0, first.output

    second = _invoke(app, 'one-shot@example.com')
    assert second.exit_code != 0
    assert 'already' in second.output.lower()

    with app.app_context():
        groups = models.ScimResource.query.filter_by(
            resource_type='Group',
            subject_address='one-shot@example.com',
        ).all()
        assert len(groups) == 1
        assert groups[0].alias.destination == ['pager@outside.example']


def test_adopt_rejects_ineligible_alias_and_rolls_back(app):
    with app.app_context():
        _alias(
            'disabled',
            ['pager@outside.example'],
            disabled=True,
        )

    result = _invoke(app, 'disabled@example.com')
    assert result.exit_code != 0

    with app.app_context():
        alias = models.db.session.get(models.Alias, 'disabled@example.com')
        assert alias.scim_resource is None
        assert alias.destination == ['pager@outside.example']


def test_adopt_rejects_unmanaged_local_alias_destination_atomically(app):
    with app.app_context():
        _alias('unmanaged-member', ['pager@outside.example'])
        _alias('candidate', ['unmanaged-member@example.com'])

    result = _invoke(app, 'candidate@example.com')
    assert result.exit_code != 0
    assert 'not an active SCIM resource' in result.output

    with app.app_context():
        candidate = models.db.session.get(models.Alias, 'candidate@example.com')
        assert candidate.scim_resource is None
        assert candidate.destination == ['unmanaged-member@example.com']
        assert models.ScimResource.query.filter_by(
            resource_type='Group',
            subject_address='candidate@example.com',
        ).count() == 0


def test_adopt_uses_routing_committed_before_graph_lock(app, monkeypatch):
    if models.db.engine.dialect.name == 'sqlite':
        pytest.skip('requires native row locking')

    with app.app_context():
        _alias('fresh-snapshot', ['old@outside.example'])

    original_create = models.create_scim_group_mapping

    def create_after_concurrent_update(alias, **values):
        with Session(models.db.engine) as writer:
            current = writer.get(models.Alias, alias.email)
            current.destination = ['new@outside.example']
            writer.commit()
        return original_create(alias, **values)

    monkeypatch.setattr(
        models,
        'create_scim_group_mapping',
        create_after_concurrent_update,
    )

    result = _invoke(app, 'fresh-snapshot@example.com')
    assert result.exit_code == 0, result.output

    with app.app_context():
        alias = models.db.session.get(
            models.Alias,
            'fresh-snapshot@example.com',
        )
        assert alias.destination == ['new@outside.example']
        assert [
            edge.destination for edge in alias.scim_resource.destinations
        ] == ['new@outside.example']


def test_alias_update_losing_adoption_lock_is_rejected(app):
    if models.db.engine.dialect.name == 'sqlite':
        pytest.skip('requires native row locking')

    session = models.db.session()
    alias = _alias('lock-winner', ['kept@outside.example'])
    group = models.create_scim_group_mapping(alias)
    models.replace_scim_group_graph(
        group,
        member_ids=[],
        external_destinations=['kept@outside.example'],
    )

    writer = subprocess.Popen(
        [sys.executable, '-c', ALIAS_UPDATE_PROCESS],
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout = ''
    stderr = ''
    try:
        ready, _, _ = select.select([writer.stdout], [], [], 15)
        assert ready, 'concurrent Alias writer did not reach the graph lock'
        assert writer.stdout.readline().strip() == 'LOCK_ATTEMPT'
        session.commit()
        stdout, stderr = writer.communicate(timeout=15)
    finally:
        if writer.poll() is None:
            writer.kill()
            stdout, stderr = writer.communicate()
        if session.in_transaction():
            session.rollback()

    assert writer.returncode == 0, stderr
    assert stdout.startswith('REJECTED:Alias lock-winner@example.com')
    session.expire_all()
    alias = session.get(models.Alias, 'lock-winner@example.com')
    assert alias.destination == ['kept@outside.example']
    assert [
        edge.destination for edge in alias.scim_resource.destinations
    ] == ['kept@outside.example']


@pytest.mark.parametrize('origin', ['legacy-adopted', 'scim-created'])
def test_deleted_group_address_can_be_readopted_with_new_id(
    app,
    client,
    origin,
):
    address = f'{origin}@example.com'
    with app.app_context():
        _domain()
        if origin == 'legacy-adopted':
            _alias(origin, ['pager@outside.example'])

    headers = {
        'Authorization': f'Bearer {app.config["API_TOKEN"]}',
        'Content-Type': 'application/scim+json',
    }
    if origin == 'legacy-adopted':
        with app.app_context():
            alias = models.db.session.get(models.Alias, address)
            group = models.create_scim_group_mapping(
                alias,
                resource_id=address,
            )
            models.replace_scim_group_graph(
                group,
                member_ids=[],
                external_destinations=['pager@outside.example'],
            )
            models.db.session.commit()
            old_id = group.id
            assert old_id == address
    else:
        response = client.post(
            '/api/scim/v2/Groups',
            json={
                'schemas': [GROUP_SCHEMA, GROUP_EXTENSION],
                'displayName': 'SCIM-created group',
                'members': [],
                GROUP_EXTENSION: {
                    'aliasAddress': address,
                    'externalDestinations': ['pager@outside.example'],
                },
            },
            headers=headers,
        )
        assert response.status_code == 201, response.get_json()
        old_id = response.get_json()['id']

    response = client.delete(
        f'/api/scim/v2/Groups/{old_id}',
        headers=headers,
    )
    assert response.status_code == 204

    with app.app_context():
        assert models.db.session.get(models.Alias, address) is None
        _alias(origin, ['replacement@outside.example'])

    result = _invoke(app, address)
    assert result.exit_code == 0, result.output

    with app.app_context():
        replacement = models.db.session.get(models.Alias, address).scim_resource
        assert UUID_PATTERN.fullmatch(replacement.id)
        assert replacement.id != old_id
        replacement_id = replacement.id
        assert replacement.subject_address == address
        assert replacement.alias.destination == [
            'replacement@outside.example'
        ]
        assert [
            edge.destination for edge in replacement.destinations
        ] == ['replacement@outside.example']
        tombstone = models.db.session.get(models.ScimResource, old_id)
        assert tombstone.deleted_at is not None

    assert client.get(
        f'/api/scim/v2/Groups/{old_id}',
        headers=headers,
    ).status_code == 404
    response = client.get(
        f'/api/scim/v2/Groups/{replacement_id}',
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()[GROUP_EXTENSION]['aliasAddress'] == address
