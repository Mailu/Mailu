"""Focused model and migration tests for persistent SCIM identity.

These tests deliberately stay below the HTTP API.  They prove that identity,
graph, deletion, and authority invariants exist at the model/migration layer
instead of depending on one endpoint remembering a convention.
"""

import importlib.util
import pathlib
import re
import threading
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from mailu import models, utils


MIGRATIONS = pathlib.Path(models.__file__).resolve().parent.parent / 'migrations' / 'versions'
IDENTITY_MIGRATION = MIGRATIONS / 'e7c9a4f2b631_.py'
ADDRESS_MIGRATION = MIGRATIONS / 'd4a6f2b8c901_.py'
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-'
    r'[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)


def _domain(name='example.com'):
    domain = models.db.session.get(models.Domain, name)
    if domain is None:
        domain = models.Domain(name=name)
        models.db.session.add(domain)
        models.db.session.commit()
    return domain


def _user(localpart, domain=None):
    user = models.User(localpart=localpart, domain=domain or _domain())
    user.set_password('not-a-real-password')
    models.db.session.add(user)
    models.db.session.commit()
    return user


def _alias(localpart, *, domain=None, destination=None, **values):
    alias = models.Alias(
        localpart=localpart,
        domain=domain or _domain(),
        destination=destination or ['outside@example.net'],
        **values,
    )
    models.db.session.add(alias)
    models.db.session.commit()
    return alias


def _managed_group(localpart, *, destination=None):
    alias = _alias(localpart, destination=destination)
    resource = models.ScimResource(
        id=models.new_scim_id(),
        resource_type='Group',
        alias_email=alias.email,
        subject_address=alias.email,
    )
    models.db.session.add(resource)
    models.db.session.commit()
    return resource


@contextmanager
def _captured_sql():
    statements = []

    def capture(_conn, _cursor, statement, _parameters, context, _executemany):
        bound_strings = tuple(
            value
            for parameter_set in context.compiled_parameters
            for value in parameter_set.values()
            if isinstance(value, str)
        )
        statements.append((
            ' '.join(statement.lower().split()),
            bound_strings,
        ))

    sa.event.listen(models.db.engine, 'before_cursor_execute', capture)
    try:
        yield statements
    finally:
        sa.event.remove(models.db.engine, 'before_cursor_execute', capture)


def _seed_cycle_probe_graph(edge_rows, extra_ids=()):
    resource_ids = sorted({
        resource_id
        for edge in edge_rows
        for resource_id in edge
    }.union(extra_ids))
    models.db.session.execute(
        models.ScimResource.__table__.insert(),
        [
            {
                'id': resource_id,
                'resource_type': 'Group',
                'external_id_bytes': None,
                'user_email': None,
                'alias_email': None,
                'subject_address': (
                    f'fixture-{index:05d}@cycle.invalid'
                ),
                'deleted_at': datetime(2000, 1, 1),
                'created_at': date(2000, 1, 1),
                'updated_at': None,
                'comment': 'cycle fixture',
            }
            for index, resource_id in enumerate(resource_ids)
        ],
    )
    if edge_rows:
        models.db.session.execute(
            models.ScimGroupMember.__table__.insert(),
            [
                {'group_id': group_id, 'member_id': member_id}
                for group_id, member_id in edge_rows
            ],
        )
    models.db.session.commit()


def _cycle_statements(statements):
    return [
        (statement, bound_strings)
        for statement, bound_strings in statements
        if ' from scim_group_member' in statement
    ]


def _group_graph_snapshot(group_id):
    group = models.db.session.get(models.ScimResource, group_id)
    alias = models.db.session.get(models.Alias, group.alias_email)
    return {
        'alias_comment': alias.comment,
        'alias_destination': tuple(alias.destination),
        'destinations': tuple(models.db.session.execute(
            sa.select(models.ScimGroupDestination.destination)
            .where(models.ScimGroupDestination.group_id == group_id)
            .order_by(models.ScimGroupDestination.destination)
        ).scalars()),
        'external_id': group.external_id,
        'members': tuple(models.db.session.execute(
            sa.select(models.ScimGroupMember.member_id)
            .where(models.ScimGroupMember.group_id == group_id)
            .order_by(models.ScimGroupMember.member_id)
        ).scalars()),
    }


def test_sqlite_foreign_keys_are_enabled_without_fixture_pragma(app):
    engine = sa.create_engine('sqlite://')
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                'PRAGMA foreign_keys'
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_address_conflict_preserves_integrity_error_contract():
    assert issubclass(models.AddressConflict, IntegrityError)


def test_fetch_protocol_enum_matches_migration_name():
    assert models.Fetch.__table__.c.protocol.type.name == 'enum_protocol'


def test_scim_group_member_reverse_index_is_declared():
    assert 'scim_group_member_member_id_idx' in {
        index.name for index in models.ScimGroupMember.__table__.indexes
    }


def test_new_orm_user_gets_random_generation_and_uuid_mapping(app):
    user = _user('new-identity')
    mapping = models.ScimResource.query.filter_by(
        resource_type='User',
        user_email=user.email,
        deleted_at=None,
    ).one()

    assert user.auth_generation != utils.INITIAL_AUTH_GENERATION
    assert re.fullmatch(r'[0-9a-f]{32}', user.auth_generation)
    assert UUID_PATTERN.fullmatch(mapping.id)
    assert mapping.subject_address == user.email
    assert mapping.external_id is None
    assert models.db.session.get(models.ScimState, 1).revision == 0


def test_user_mapping_helper_reuses_automatic_mapping(app):
    user = _user('mapping-helper')
    automatic = user.scim_resource

    assert models.create_scim_user_mapping(
        user,
        external_id='upstream-42',
    ) is automatic
    assert automatic.external_id == 'upstream-42'
    assert models.create_scim_user_mapping(
        user,
        resource_id=automatic.id,
    ) is automatic
    with pytest.raises(models.ScimIdentityError, match='different'):
        models.create_scim_user_mapping(
            user,
            resource_id=models.new_scim_id(),
        )


def test_hard_delete_recreate_cannot_reuse_identity_or_session_generation(app):
    user = _user('recreated')
    old_generation = user.auth_generation
    old_mapping = user.scim_resource
    old_id = old_mapping.id

    models.db.session.delete(user)
    models.db.session.commit()

    tombstone = models.db.session.get(models.ScimResource, old_id)
    assert tombstone.deleted_at is not None
    assert tombstone.user_email is None
    assert tombstone.subject_address == 'recreated@example.com'

    replacement = _user('recreated')
    assert replacement.auth_generation != old_generation
    assert replacement.scim_resource.id != old_id
    assert models.db.session.get(models.ScimResource, old_id) is tombstone


def test_external_id_is_byte_exact_and_bounded(app):
    user = _user('external-id')
    mapping = user.scim_resource

    mapping.external_id = 'Case-Sensitive-é'
    models.db.session.commit()
    assert mapping.external_id == 'Case-Sensitive-é'
    assert mapping.external_id_bytes == 'Case-Sensitive-é'.encode()

    mapping.external_id = 'a' * 1024
    assert len(mapping.external_id_bytes) == 1024
    with pytest.raises(ValueError, match='1024'):
        mapping.external_id = 'é' * 513
    with pytest.raises(TypeError):
        mapping.external_id = b'not-a-string'


def test_exact_provider_id_lookup_rejects_case_variant(app):
    user = _user('exact-id')
    mapping = user.scim_resource

    assert models.ScimResource.get_exact(mapping.id) is mapping
    assert models.ScimResource.get_exact(mapping.id.upper()) is None


def test_scim_resource_hard_delete_is_rejected(app):
    user = _user('immutable-tombstone')
    resource_id = user.scim_resource.id

    models.db.session.delete(user.scim_resource)
    with pytest.raises(models.ScimIdentityError, match='tombstone'):
        models.db.session.commit()
    models.db.session.rollback()

    assert models.ScimResource.get_exact(resource_id) is not None


def test_scim_resource_principal_binding_is_immutable(app):
    alice = _user('binding-alice')
    bob = _user('binding-bob')
    mapping = alice.scim_resource

    mapping.user = bob
    with pytest.raises(models.ScimIdentityError, match='binding'):
        models.db.session.commit()
    models.db.session.rollback()

    assert mapping.user_email == alice.email


def test_scim_tombstone_cannot_be_resurrected_or_edited(app):
    user = _user('immutable-deleted-resource')
    mapping = user.scim_resource
    original_external_id = mapping.external_id
    models.tombstone_scim_resource(mapping, retain_subject=True)
    models.db.session.commit()
    deleted_at = mapping.deleted_at

    mapping.deleted_at = None
    mapping.user = user
    mapping.external_id = 'changed-after-delete'
    with pytest.raises(models.ScimIdentityError, match='tombstone'):
        models.db.session.commit()
    models.db.session.rollback()

    assert mapping.deleted_at == deleted_at
    assert mapping.user_email is None
    assert mapping.external_id == original_external_id


def test_scim_tombstone_scrubs_retained_user_authority(app):
    user = _user('authority')
    user_domain = user.domain
    user.global_admin = True
    user.allow_spoofing = True
    user.forward_enabled = True
    user.forward_destination = ['old-owner@example.net']
    user.reply_enabled = True
    managed_domain = _domain('managed.example')
    models.db.session.execute(
        models.managers.insert().values(
            domain_name=managed_domain.name,
            user_email=user.email,
        )
    )
    token = models.Token(user=user)
    token.set_password('a' * 32)
    access = models.DomainAccess(
        domain_name='managed.example',
        user=user,
    )
    owned_alias = models.Alias(
        localpart='old-owner-alias',
        domain=user_domain,
        owner=user,
        destination=[user.email],
    )
    fetch = models.Fetch(
        user=user,
        protocol='imap',
        host='mail.old-owner.example',
        port=993,
        tls=True,
        username='old-owner',
        password='remote-secret',
    )
    models.db.session.add_all([token, access, owned_alias, fetch])
    models.db.session.commit()
    mapping = user.scim_resource

    models.tombstone_scim_resource(
        mapping,
        retain_subject=True,
        scrub_user_authority=True,
    )
    models.db.session.commit()

    assert mapping.deleted_at is not None
    assert mapping.user_email is None
    assert user.enabled is False
    assert user.global_admin is False
    assert user.allow_spoofing is False
    assert user.forward_enabled is False
    assert user.forward_destination == []
    assert user.reply_enabled is False
    assert models.Token.query.filter_by(user_email=user.email).count() == 0
    assert models.Fetch.query.filter_by(user_email=user.email).count() == 0
    assert models.Alias.query.filter_by(owner_email=user.email).count() == 0
    assert models.DomainAccess.query.filter_by(user_email=user.email).count() == 0
    assert models.db.session.execute(
        sa.select(sa.func.count()).select_from(models.managers).where(
            models.managers.c.user_email == user.email
        )
    ).scalar_one() == 0


def test_deleted_user_address_cannot_receive_a_new_scim_identity(app):
    user = _user('reserved-authority')
    mapping = user.scim_resource

    models.tombstone_scim_resource(
        mapping,
        retain_subject=True,
        scrub_user_authority=True,
    )
    models.db.session.commit()

    with pytest.raises(
        models.ScimIdentityError,
        match='permanently reserved',
    ):
        models.create_scim_user_mapping(user)


@pytest.mark.parametrize(
    'values',
    [
        {'disabled': True},
        {'wildcard': True},
    ],
)
def test_group_adoption_rejects_ineligible_alias_state(app, values):
    alias = _alias('ineligible', **values)
    with pytest.raises(models.ScimGroupAdoptionError):
        models.validate_scim_group_adoption(alias)


def test_group_adoption_rejects_owned_alias(app):
    owner = _user('owner')
    alias = _alias('owned', owner=owner)
    with pytest.raises(models.ScimGroupAdoptionError):
        models.validate_scim_group_adoption(alias)


def test_managed_alias_ordinary_edit_is_blocked_but_one_shot_edit_is_allowed(app):
    group = _managed_group('managed-edit')
    alias = group.alias

    alias.comment = 'ordinary edit'
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()

    alias = models.db.session.get(models.Alias, 'managed-edit@example.com')
    models.permit_scim_managed_alias_edit(alias)
    alias.comment = 'SCIM edit'
    models.db.session.commit()
    assert alias.comment == 'SCIM edit'


def test_managed_alias_destination_edit_is_blocked(app):
    group = _managed_group('managed-destination')
    alias = group.alias

    alias.destination = ['other@example.net']
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()


def test_managed_alias_ordinary_delete_is_blocked(app):
    group = _managed_group('managed-delete')
    resource_id = group.id
    alias_email = group.alias.email

    models.db.session.delete(group.alias)
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()

    assert models.db.session.get(models.Alias, alias_email) is not None
    assert models.ScimResource.get_exact(resource_id) is not None


def test_managed_alias_edit_permit_does_not_survive_rollback(app):
    group = _managed_group('managed-rollback')
    alias = group.alias
    models.permit_scim_managed_alias_edit(alias)
    alias.comment = 'permitted but rolled back'
    models.db.session.rollback()

    alias = models.db.session.get(models.Alias, alias.email)
    alias.comment = 'ordinary edit after rollback'
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()


@pytest.mark.parametrize('population', [1, 8])
def test_graph_validation_probe_count_is_population_independent(
    app,
    population,
):
    members = [
        _user(f'batched-member-{population}-{index}')
        for index in range(population)
    ]
    member_ids = [member.scim_resource.id for member in members]
    group = _managed_group(f'batched-group-{population}')
    assert group.alias is not None
    destinations = [
        f'external-{population}-{index}@outside.test'
        for index in range(population)
    ]
    with _captured_sql() as statements:
        models.replace_scim_group_graph(
            group,
            member_ids=member_ids,
            external_destinations=destinations,
        )

    member_probes = [
        statement
        for statement, bound_strings in statements
        if (
            ' from scim_resource where scim_resource.id ' in statement
            and set(bound_strings).intersection(member_ids)
        )
    ]
    local_address_probes = [
        statement
        for statement, bound_strings in statements
        if (
            ' from mail_address where mail_address.email ' in statement
            and set(bound_strings).intersection(destinations)
        )
    ]
    assert (len(member_probes), len(local_address_probes)) == (1, 1), {
        'member_probes': member_probes,
        'local_address_probes': local_address_probes,
    }

    models.db.session.commit()
    assert {edge.member_id for edge in group.member_edges} == set(member_ids)
    assert {
        destination.destination
        for destination in group.destinations
    } == set(destinations)


def test_graph_validation_probe_chunk_boundary(app):
    domain = _domain()
    models.db.session.add_all(
        models.User(
            localpart=f'chunk-member-{index:03d}',
            domain=domain,
            password='not-a-real-password',
        )
        for index in range(models._SCIM_GRAPH_PROBE_CHUNK_SIZE)
    )
    models.db.session.commit()
    member_ids = list(models.db.session.execute(
        sa.select(models.ScimResource.id)
        .where(models.ScimResource.resource_type == 'User')
        .order_by(models.ScimResource.id)
    ).scalars())
    assert len(member_ids) == models._SCIM_GRAPH_PROBE_CHUNK_SIZE
    missing_id = 'missing-member-id'
    requested_member_ids = [*member_ids, missing_id]
    destinations = [
        f'chunk-destination-{index:03d}@outside.test'
        for index in range(models._SCIM_GRAPH_PROBE_CHUNK_SIZE + 1)
    ]

    with _captured_sql() as statements:
        with pytest.raises(
            models.ScimGraphError,
            match=re.escape(
                f'SCIM member {missing_id!r} is not an active resource'
            ),
        ):
            models._active_scim_resources(requested_member_ids)
        models._reject_local_scim_destinations(destinations)

    member_id_set = set(requested_member_ids)
    destination_set = set(destinations)
    member_probe_sizes = [
        len(member_id_set.intersection(bound_strings))
        for statement, bound_strings in statements
        if ' from scim_resource where scim_resource.id in ' in statement
    ]
    destination_probe_sizes = [
        len(destination_set.intersection(bound_strings))
        for statement, bound_strings in statements
        if ' from mail_address where mail_address.email in ' in statement
    ]
    assert member_probe_sizes == [500, 1]
    assert destination_probe_sizes == [500, 1]


@pytest.mark.parametrize('failure', ['wrong-case', 'tombstoned'])
def test_graph_batch_member_failure_preserves_order_and_old_graph(
    app,
    monkeypatch,
    failure,
):
    original_member = _user(f'original-{failure}')
    original_member_id = original_member.scim_resource.id
    group = _managed_group(f'member-failure-{failure}')
    models.replace_scim_group_graph(
        group,
        member_ids=[original_member_id],
        external_destinations=['original@outside.test'],
    )
    models.db.session.commit()
    group_id = group.id

    if failure == 'wrong-case':
        exact_id = 'abcdef01-2345-6789-abcd-ef0123456789'
        monkeypatch.setattr(models, 'new_scim_id', lambda: exact_id)
        _user('wrong-case-candidate')
        bad_id = exact_id.upper()
    else:
        candidate = _user('tombstoned-candidate')
        bad_id = candidate.scim_resource.id
        models.tombstone_scim_resource(candidate.scim_resource)
        models.db.session.commit()

    before = _group_graph_snapshot(group_id)
    group = models.db.session.get(models.ScimResource, group_id)
    later_missing_id = 'later-missing-member-id'
    with pytest.raises(
        models.ScimGraphError,
        match=re.escape(
            f'SCIM member {bad_id!r} is not an active resource'
        ),
    ):
        models.replace_scim_group_graph(
            group,
            member_ids=[original_member_id, bad_id, later_missing_id],
            external_destinations=['replacement@outside.test'],
        )
    models.db.session.rollback()

    assert _group_graph_snapshot(group_id) == before


def test_graph_batch_local_conflict_uses_sorted_request_order_and_rolls_back(app):
    original_member = _user('local-conflict-original')
    group = _managed_group('local-conflict-group')
    models.replace_scim_group_graph(
        group,
        member_ids=[original_member.scim_resource.id],
        external_destinations=['original@outside.test'],
    )
    models.db.session.commit()
    group_id = group.id
    _user('z-local-conflict')
    _user('m-local-conflict')
    before = _group_graph_snapshot(group_id)
    first_conflict = 'm-local-conflict@example.com'

    with pytest.raises(
        models.ScimExternalDestinationError,
        match=re.escape(
            f'External destination {first_conflict!r} is locally owned'
        ),
    ):
        models.replace_scim_group_graph(
            models.db.session.get(models.ScimResource, group_id),
            member_ids=[],
            external_destinations=[
                'z-local-conflict@example.com',
                'a-harmless@outside.test',
                first_conflict,
            ],
        )
    models.db.session.rollback()

    assert _group_graph_snapshot(group_id) == before


def test_mysql_batch_destination_conflict_preserves_routing_collation(app):
    if models.db.engine.dialect.name not in {'mysql', 'mariadb'}:
        pytest.skip('requires MySQL/MariaDB routing collation')

    stored_first = _user('café-collation')
    stored_second = _user('résumé-collation')
    requested_first = 'cafe-collation@example.com'
    requested_second = 'resume-collation@example.com'
    assert models.db.session.execute(
        sa.select(models.MailAddress.email)
        .where(models.MailAddress.email == requested_first)
    ).scalar_one() == stored_first.email
    assert models.db.session.execute(
        sa.select(models.MailAddress.email)
        .where(models.MailAddress.email == requested_second)
    ).scalar_one() == stored_second.email
    group = _managed_group('collation-conflict-group')

    with pytest.raises(
        models.ScimExternalDestinationError,
        match=re.escape(
            f'External destination {requested_first!r} is locally owned'
        ),
    ):
        models.replace_scim_group_graph(
            group,
            member_ids=[],
            external_destinations=[
                requested_second,
                requested_first,
                'a-harmless@outside.test',
            ],
        )
    models.db.session.rollback()


def test_graph_replace_rolls_back_after_staging_failure(app, monkeypatch):
    original_member = _user('staging-original')
    replacement_member = _user('staging-replacement')
    group = _managed_group('staging-failure-group')
    group.external_id = 'original-external-id'
    models.permit_scim_managed_alias_edit(group.alias)
    group.alias.comment = 'Original comment'
    models.replace_scim_group_graph(
        group,
        member_ids=[original_member.scim_resource.id],
        external_destinations=['original@outside.test'],
    )
    models.db.session.commit()
    group_id = group.id
    before = _group_graph_snapshot(group_id)

    def fail_materialization(failing_group):
        models.permit_scim_managed_alias_edit(failing_group.alias)
        raise models.ScimGraphError('injected post-staging failure')

    monkeypatch.setattr(models, 'materialize_scim_group', fail_materialization)
    group = models.db.session.get(models.ScimResource, group_id)
    models.permit_scim_managed_alias_edit(group.alias)
    group.alias.comment = 'Replacement comment'
    group.external_id = 'replacement-external-id'
    with pytest.raises(
        models.ScimGraphError,
        match='injected post-staging failure',
    ):
        models.replace_scim_group_graph(
            group,
            member_ids=[replacement_member.scim_resource.id],
            external_destinations=['replacement@outside.test'],
        )
    models.db.session.rollback()

    assert _group_graph_snapshot(group_id) == before
    alias = models.db.session.get(models.ScimResource, group_id).alias
    alias.comment = 'Unpermitted edit after rollback'
    with pytest.raises(models.ScimManagedAliasError):
        models.db.session.commit()
    models.db.session.rollback()


def test_graph_materialization_uses_ids_and_rejects_local_external_values(app):
    member = _user('member')
    group = _managed_group('graph')

    models.replace_scim_group_graph(
        group,
        member_ids=[member.scim_resource.id],
        external_destinations=['pager@outside.test'],
    )
    models.db.session.commit()

    assert group.alias.destination == [
        'member@example.com',
        'pager@outside.test',
    ]
    assert {(edge.group_id, edge.member_id) for edge in group.member_edges} == {
        (group.id, member.scim_resource.id)
    }

    with pytest.raises(models.ScimExternalDestinationError):
        models.replace_scim_group_graph(
            group,
            member_ids=[],
            external_destinations=['member@example.com'],
        )
    models.db.session.rollback()


@pytest.mark.parametrize(
    'destination',
    [
        'foo bar@example.com',
        'foo..bar@example.com',
        '.foo@example.com',
    ],
)
def test_external_destination_rejects_malformed_localpart(app, destination):
    with pytest.raises(models.ScimExternalDestinationError):
        models.canonicalize_scim_destination(destination)


def test_external_destination_reservation_blocks_later_local_address(app):
    group = _managed_group('external-reservation')
    models.replace_scim_group_graph(
        group,
        member_ids=[],
        external_destinations=['future@future.example'],
    )
    models.db.session.commit()

    domain = _domain('future.example')
    candidate = models.User(localpart='future', domain=domain)
    candidate.set_password('not-a-real-password')
    models.db.session.add(candidate)
    with pytest.raises(models.AddressConflict):
        models.db.session.commit()
    models.db.session.rollback()


def test_mysql_engine_uses_read_committed(app):
    if models.db.engine.dialect.name not in {'mysql', 'mariadb'}:
        pytest.skip('requires MySQL/MariaDB')

    assert sa.event.contains(
        models.db.engine,
        'connect',
        models._reject_mysql_statement_binlog,
    )
    assert (
        models.db.session.connection().get_isolation_level()
        == 'READ COMMITTED'
    )


def test_mysql_scim_id_columns_use_binary_collation(app):
    if models.db.engine.dialect.name not in {'mysql', 'mariadb'}:
        pytest.skip('requires MySQL/MariaDB')

    rows = models.db.session.execute(sa.text(
        """
        SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME
          FROM information_schema.COLUMNS
         WHERE TABLE_SCHEMA = DATABASE()
           AND (
             (TABLE_NAME = 'scim_resource' AND COLUMN_NAME = 'id') OR
             (TABLE_NAME = 'scim_group_member' AND COLUMN_NAME IN
               ('group_id', 'member_id')) OR
             (TABLE_NAME = 'scim_group_destination' AND COLUMN_NAME = 'group_id')
           )
        """
    )).all()
    assert len(rows) == 4
    character_sets = {
        character_set
        for _table, _column, character_set, _collation in rows
    }
    assert character_sets == {'utf8mb4'}
    collations = {
        collation
        for _table, _column, _character_set, collation in rows
    }
    assert collations == {'utf8mb4_bin'}


def test_mysql_external_reservation_sees_local_commit_after_prior_read(app):
    if models.db.engine.dialect.name not in {'mysql', 'mariadb'}:
        pytest.skip('requires MySQL/MariaDB')

    group = _managed_group('snapshot-external')
    group_id = group.id
    _domain('future.example')
    models.db.session.remove()

    snapshot_ready = threading.Event()
    local_committed = threading.Event()
    outcome = []

    def reserve_external():
        with app.app_context():
            stale_group = models.db.session.get(
                models.ScimResource,
                group_id,
            )
            models.db.session.execute(sa.select(models.Domain)).all()
            snapshot_ready.set()
            assert local_committed.wait(timeout=10)
            try:
                models.replace_scim_group_graph(
                    stale_group,
                    member_ids=[],
                    external_destinations=['future@future.example'],
                )
                models.db.session.commit()
            except models.ScimExternalDestinationError:
                models.db.session.rollback()
                outcome.append('conflict')
            else:
                outcome.append('reserved')
            finally:
                models.db.session.remove()

    worker = threading.Thread(target=reserve_external)
    worker.start()
    assert snapshot_ready.wait(timeout=10)

    domain = models.db.session.get(models.Domain, 'future.example')
    candidate = models.User(localpart='future', domain=domain)
    candidate.set_password('not-a-real-password')
    models.db.session.add(candidate)
    models.db.session.commit()
    local_committed.set()
    worker.join(timeout=15)

    assert not worker.is_alive()
    assert outcome == ['conflict']
    assert models.db.session.get(
        models.User,
        'future@future.example',
    ) is not None
    assert models.ScimGroupDestination.query.filter_by(
        destination='future@future.example',
    ).count() == 0


def test_mysql_local_claim_sees_external_commit_after_prior_read(app):
    if models.db.engine.dialect.name not in {'mysql', 'mariadb'}:
        pytest.skip('requires MySQL/MariaDB')

    group = _managed_group('snapshot-local')
    group_id = group.id
    domain = _domain('future.example')
    models.db.session.execute(sa.select(models.Domain)).all()

    def reserve_external():
        with app.app_context():
            current_group = models.db.session.get(
                models.ScimResource,
                group_id,
            )
            models.replace_scim_group_graph(
                current_group,
                member_ids=[],
                external_destinations=['future@future.example'],
            )
            models.db.session.commit()
            models.db.session.remove()

    worker = threading.Thread(target=reserve_external)
    worker.start()
    worker.join(timeout=15)
    assert not worker.is_alive()

    candidate = models.User(localpart='future', domain=domain)
    candidate.set_password('not-a-real-password')
    models.db.session.add(candidate)
    with pytest.raises(models.AddressConflict):
        models.db.session.commit()
    models.db.session.rollback()

    assert models.db.session.get(
        models.User,
        'future@future.example',
    ) is None
    assert models.ScimGroupDestination.query.filter_by(
        destination='future@future.example',
    ).count() == 1


def test_mysql_external_reservation_sees_local_delete_after_prior_read(app):
    if models.db.engine.dialect.name not in {'mysql', 'mariadb'}:
        pytest.skip('requires MySQL/MariaDB')

    group = _managed_group('delete-external')
    group_id = group.id
    domain = _domain('future.example')
    candidate = models.User(localpart='future', domain=domain)
    candidate.set_password('not-a-real-password')
    models.db.session.add(candidate)
    models.db.session.commit()
    models.db.session.remove()

    snapshot_ready = threading.Event()
    local_deleted = threading.Event()
    outcome = []

    def reserve_external():
        with app.app_context():
            try:
                stale_group = models.db.session.get(
                    models.ScimResource,
                    group_id,
                )
                models.db.session.execute(sa.select(models.Domain)).all()
                snapshot_ready.set()
                assert local_deleted.wait(timeout=10)
                models.replace_scim_group_graph(
                    stale_group,
                    member_ids=[],
                    external_destinations=['future@future.example'],
                )
                models.db.session.commit()
            except Exception as error:
                models.db.session.rollback()
                outcome.append(error)
            else:
                outcome.append('reserved')
            finally:
                models.db.session.remove()

    worker = threading.Thread(target=reserve_external)
    worker.start()
    assert snapshot_ready.wait(timeout=10)

    current = models.db.session.get(
        models.User,
        'future@future.example',
    )
    models.db.session.delete(current)
    models.db.session.commit()
    local_deleted.set()
    worker.join(timeout=15)

    assert not worker.is_alive()
    assert outcome == ['reserved']
    assert models.db.session.get(
        models.User,
        'future@future.example',
    ) is None
    assert models.ScimGroupDestination.query.filter_by(
        destination='future@future.example',
    ).count() == 1


def test_mysql_local_claim_sees_external_delete_after_prior_read(app):
    if models.db.engine.dialect.name not in {'mysql', 'mariadb'}:
        pytest.skip('requires MySQL/MariaDB')

    group = _managed_group('delete-local')
    group_id = group.id
    domain = _domain('future.example')
    models.replace_scim_group_graph(
        group,
        member_ids=[],
        external_destinations=['future@future.example'],
    )
    models.db.session.commit()
    models.db.session.execute(sa.select(models.Domain)).all()
    outcome = []

    def remove_external():
        with app.app_context():
            try:
                current_group = models.db.session.get(
                    models.ScimResource,
                    group_id,
                )
                models.replace_scim_group_graph(
                    current_group,
                    member_ids=[],
                    external_destinations=[],
                )
                models.db.session.commit()
            except Exception as error:
                models.db.session.rollback()
                outcome.append(error)
            else:
                outcome.append('removed')
            finally:
                models.db.session.remove()

    worker = threading.Thread(target=remove_external)
    worker.start()
    worker.join(timeout=15)
    assert not worker.is_alive()
    assert outcome == ['removed']

    candidate = models.User(localpart='future', domain=domain)
    candidate.set_password('not-a-real-password')
    models.db.session.add(candidate)
    models.db.session.commit()

    assert models.db.session.get(
        models.User,
        'future@future.example',
    ) is not None
    assert models.ScimGroupDestination.query.filter_by(
        destination='future@future.example',
    ).count() == 0


def test_cycle_full_scan_preserves_cycle_semantics_and_exact_ids(app):
    edges = [
        ('two:parent', 'two:target'),
        ('diamond:left', 'diamond:target'),
        ('diamond:right', 'diamond:target'),
        ('diamond:top', 'diamond:left'),
        ('diamond:top', 'diamond:right'),
        ('Exact:Parent', 'exact:target'),
        ('Exact:Positive', 'Exact:Target'),
        ('replace:target', 'replace:old'),
        ('disconnected:a', 'disconnected:b'),
        ('disconnected:b', 'disconnected:a'),
    ]
    _seed_cycle_probe_graph(
        edges,
        extra_ids={
            'diamond:safe',
            'disconnected:target',
            'empty:target',
            'self:target',
        },
    )
    cycle_error = re.escape('SCIM Group membership would create a cycle')

    with _captured_sql() as statements:
        with pytest.raises(models.ScimGraphError, match=cycle_error):
            models._validate_scim_cycle(
                SimpleNamespace(id='self:target'),
                ['self:target'],
            )
        models._validate_scim_cycle(
            SimpleNamespace(id='empty:target'),
            [],
        )
    assert _cycle_statements(statements) == []

    with pytest.raises(models.ScimGraphError, match=cycle_error):
        models._validate_scim_cycle(
            SimpleNamespace(id='two:target'),
            ['two:parent'],
        )
    with pytest.raises(models.ScimGraphError, match=cycle_error):
        models._validate_scim_cycle(
            SimpleNamespace(id='diamond:target'),
            ['diamond:top'],
        )
    with pytest.raises(models.ScimGraphError, match=cycle_error):
        models._validate_scim_cycle(
            SimpleNamespace(id='diamond:target'),
            ['diamond:safe', 'diamond:top'],
        )

    models._validate_scim_cycle(
        SimpleNamespace(id='Exact:Target'),
        ['Exact:Parent'],
    )
    with pytest.raises(models.ScimGraphError, match=cycle_error):
        models._validate_scim_cycle(
            SimpleNamespace(id='Exact:Target'),
            ['Exact:Positive'],
        )
    models._validate_scim_cycle(
        SimpleNamespace(id='replace:target'),
        ['replace:old'],
    )
    models._validate_scim_cycle(
        SimpleNamespace(id='disconnected:target'),
        ['disconnected:a'],
    )


def test_cycle_full_scan_reads_one_complete_locked_snapshot(app):
    unrelated_ids = [
        f'unrelated:{index:04d}'
        for index in range(1025)
    ]
    edges = [
        ('parent:0', 'shallow:target'),
        ('parent:1', 'parent:0'),
        *[
            (unrelated_ids[index + 1], unrelated_ids[index])
            for index in range(1024)
        ],
    ]
    _seed_cycle_probe_graph(edges, extra_ids={'shallow:outside'})

    with _captured_sql() as statements:
        models._validate_scim_cycle(
            SimpleNamespace(id='shallow:target'),
            ['shallow:outside'],
        )

    cycle_statements = _cycle_statements(statements)
    assert len(cycle_statements) == 1
    assert ' where ' not in cycle_statements[0][0]
    assert cycle_statements[0][1] == ()


def test_cycle_full_scan_handles_wide_fan_in_in_one_query(app):
    parent_ids = [
        f'wide:parent:{index:04d}'
        for index in range(1201)
    ]
    _seed_cycle_probe_graph(
        [(parent_id, 'wide:target') for parent_id in parent_ids],
        extra_ids={'wide:outside'},
    )

    with _captured_sql() as safe_statements:
        models._validate_scim_cycle(
            SimpleNamespace(id='wide:target'),
            ['wide:outside'],
        )

    with _captured_sql() as cycle_statements:
        with pytest.raises(
            models.ScimGraphError,
            match=re.escape('SCIM Group membership would create a cycle'),
        ):
            models._validate_scim_cycle(
                SimpleNamespace(id='wide:target'),
                [parent_ids[-1]],
            )

    for statements in (safe_statements, cycle_statements):
        cycle_queries = _cycle_statements(statements)
        assert len(cycle_queries) == 1
        assert ' where ' not in cycle_queries[0][0]
        assert cycle_queries[0][1] == ()


@pytest.mark.parametrize('depth', [999, 1000, 1001, 2500, 10000])
def test_cycle_full_scan_is_iterative_at_depth_boundaries(app, depth):
    parent_ids = [
        f'deep:parent:{index:05d}'
        for index in range(depth)
    ]
    edges = [
        (parent_ids[0], 'deep:target'),
        ('deep:target', 'deep:old'),
    ]
    edges.extend(
        (parent_ids[index], parent_ids[index - 1])
        for index in range(1, len(parent_ids))
    )
    _seed_cycle_probe_graph(edges, extra_ids={'deep:outside'})
    cycle_error = re.escape('SCIM Group membership would create a cycle')

    with _captured_sql() as cyclic_statements:
        with pytest.raises(models.ScimGraphError, match=cycle_error):
            models._validate_scim_cycle(
                SimpleNamespace(id='deep:target'),
                [parent_ids[-1]],
            )
    models.db.session.rollback()

    with _captured_sql() as acyclic_statements:
        models._validate_scim_cycle(
            SimpleNamespace(id='deep:target'),
            ['deep:outside'],
        )

    for statements in (cyclic_statements, acyclic_statements):
        cycle_statements = _cycle_statements(statements)
        assert len(cycle_statements) == 1
        assert ' where ' not in cycle_statements[0][0]
        assert cycle_statements[0][1] == ()


def test_cycle_full_scan_rejection_preserves_old_graph_and_projection(app):
    original_member = _user('cycle-original')
    first = _managed_group('cycle-a')
    second = _managed_group('cycle-b')
    first.external_id = 'original-external-id'
    models.permit_scim_managed_alias_edit(first.alias)
    first.alias.comment = 'Original comment'
    models.replace_scim_group_graph(
        first,
        member_ids=[original_member.scim_resource.id],
        external_destinations=['original@outside.test'],
    )
    models.replace_scim_group_graph(
        second,
        member_ids=[first.id],
        external_destinations=[],
    )
    models.db.session.commit()
    first_id = first.id
    before = _group_graph_snapshot(first_id)

    first = models.db.session.get(models.ScimResource, first_id)
    first.external_id = 'replacement-external-id'
    models.permit_scim_managed_alias_edit(first.alias)
    first.alias.comment = 'Replacement comment'
    with pytest.raises(
        models.ScimGraphError,
        match=re.escape('SCIM Group membership would create a cycle'),
    ):
        models.replace_scim_group_graph(
            first,
            member_ids=[second.id],
            external_destinations=['replacement@outside.test'],
        )
    models.db.session.rollback()
    assert _group_graph_snapshot(first_id) == before


def test_hard_deleted_member_is_tombstoned_and_removed_from_group(app):
    member = _user('departing')
    member_id = member.scim_resource.id
    group = _managed_group('member-delete')
    models.replace_scim_group_graph(
        group,
        member_ids=[member_id],
        external_destinations=['outside@example.net'],
    )
    models.db.session.commit()

    models.db.session.delete(member)
    models.db.session.commit()

    tombstone = models.db.session.get(models.ScimResource, member_id)
    assert tombstone.deleted_at is not None
    assert models.ScimGroupMember.query.filter_by(member_id=member_id).count() == 0
    assert group.alias.destination == ['outside@example.net']


def _load_migration(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity_legacy_engine():
    engine = sa.create_engine('sqlite://')
    metadata = sa.MetaData()
    sa.Table(
        'user',
        metadata,
        sa.Column('email', sa.String(255), primary_key=True),
        sa.Column('created_at', sa.Date, nullable=False),
        sa.Column('updated_at', sa.Date),
    )
    sa.Table(
        'alias',
        metadata,
        sa.Column('email', sa.String(255), primary_key=True),
        sa.Column(
            'owner_email',
            sa.String(255),
            sa.ForeignKey('user.email'),
        ),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO user (email, created_at, updated_at) VALUES "
            "('alice@example.com', '2024-01-02', NULL),"
            "('idna@xn--bcher-kva.example', '2024-01-03', '2024-01-04')"
        )
        connection.exec_driver_sql(
            "INSERT INTO alias (email, owner_email) VALUES "
            "('ordinary@example.com', 'alice@example.com')"
        )
    return engine


def _run_migration(engine, operation, *, destructive=False):
    migration = _load_migration(
        IDENTITY_MIGRATION,
        f'scim_identity_migration_{operation}_{destructive}',
    )
    x_arguments = []
    if destructive:
        x_arguments = [
            'allow_destructive_scim_identity=true',
            'scim_identity_exported=true',
        ]
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={'x_argument': x_arguments},
        )
        migration.op = Operations(context)
        with connection.begin():
            getattr(migration, operation)()


def test_identity_migration_backfills_users_only_and_gates_downgrade():
    engine = _identity_legacy_engine()
    _run_migration(engine, 'upgrade')

    inspector = sa.inspect(engine)
    assert {
        'scim_state',
        'scim_resource',
        'scim_group_member',
        'scim_group_destination',
    } <= set(inspector.get_table_names())
    assert 'auth_generation' in {
        column['name'] for column in inspector.get_columns('user')
    }
    assert 'scim_group_member_member_id_idx' in {
        index['name']
        for index in inspector.get_indexes('scim_group_member')
    }

    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            'SELECT id, resource_type, user_email, alias_email '
            'FROM scim_resource ORDER BY user_email'
        ).all() == [
            ('alice@example.com', 'User', 'alice@example.com', None),
            (
                'idna@bücher.example',
                'User',
                'idna@xn--bcher-kva.example',
                None,
            ),
        ]
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM scim_resource WHERE resource_type='Group'"
        ).scalar_one() == 0
        assert connection.exec_driver_sql(
            'SELECT id, revision FROM scim_state'
        ).all() == [(1, 0)]
        assert set(connection.exec_driver_sql(
            'SELECT auth_generation FROM user'
        ).scalars()) == {utils.INITIAL_AUTH_GENERATION}
        assert connection.exec_driver_sql(
            'PRAGMA foreign_key_check'
        ).all() == []

    with pytest.raises(RuntimeError, match='identity export'):
        _run_migration(engine, 'downgrade')
    assert 'scim_resource' in sa.inspect(engine).get_table_names()

    _run_migration(engine, 'downgrade', destructive=True)
    inspector = sa.inspect(engine)
    assert 'scim_resource' not in inspector.get_table_names()
    assert 'auth_generation' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            'SELECT email, owner_email FROM alias'
        ).all() == [('ordinary@example.com', 'alice@example.com')]
        assert connection.exec_driver_sql(
            'PRAGMA foreign_key_check'
        ).all() == []
    engine.dispose()


def test_address_preflight_uses_native_database_collation():
    engine = sa.create_engine('sqlite://')

    def accent_insensitive(left, right):
        def normalized(value):
            decomposed = unicodedata.normalize('NFKD', value)
            return ''.join(
                char for char in decomposed
                if not unicodedata.combining(char)
            ).casefold()

        return (normalized(left) > normalized(right)) - (
            normalized(left) < normalized(right)
        )

    @sa.event.listens_for(engine, 'connect')
    def install_collation(connection, _record):
        connection.create_collation('mailu_ai', accent_insensitive)

    metadata = sa.MetaData()
    sa.Table(
        'user',
        metadata,
        sa.Column(
            'email',
            sa.String(255, collation='mailu_ai'),
            primary_key=True,
        ),
    )
    sa.Table(
        'alias',
        metadata,
        sa.Column(
            'email',
            sa.String(255, collation='mailu_ai'),
            primary_key=True,
        ),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO user (email) VALUES ('cafe@example.com')"
        )
        connection.exec_driver_sql(
            "INSERT INTO alias (email) VALUES ('café@example.com')"
        )

    migration = _load_migration(
        ADDRESS_MIGRATION,
        'address_native_collation_preflight',
    )
    with engine.connect() as connection:
        collisions, truncated = migration._cross_table_collisions(connection)
    assert collisions == [
        ('cafe@example.com', 'cafe@example.com', 'café@example.com')
    ]
    assert truncated is False
    engine.dispose()


def test_address_preflight_lowercase_probe_work_is_population_bounded():
    population_size = 32
    lower_calls = 0
    engine = sa.create_engine('sqlite://')

    @sa.event.listens_for(engine, 'connect')
    def count_lower_calls(connection, _record):
        def counted_lower(value):
            nonlocal lower_calls
            lower_calls += 1
            return value.lower()

        connection.create_function('lower', 1, counted_lower)

    metadata = sa.MetaData()
    user_table = sa.Table(
        'user',
        metadata,
        sa.Column('email', sa.String(255), primary_key=True),
    )
    alias_table = sa.Table(
        'alias',
        metadata,
        sa.Column('email', sa.String(255), primary_key=True),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(user_table.insert(), [
            {'email': f'user-{index:03d}@example.com'}
            for index in range(population_size)
        ])
        connection.execute(alias_table.insert(), [
            {'email': f'alias-{index:03d}@example.net'}
            for index in range(population_size)
        ])

    migration = _load_migration(
        ADDRESS_MIGRATION,
        'address_population_bounded_preflight',
    )
    lower_calls = 0
    with engine.connect() as connection:
        collisions, truncated = migration._cross_table_collisions(connection)

    assert collisions == []
    assert truncated is False
    assert lower_calls <= population_size * 8
    engine.dispose()


def test_address_migration_rebuilds_inbound_user_fks_only_on_sqlite():
    migration = _load_migration(
        ADDRESS_MIGRATION,
        'mail_address_backend_branching',
    )

    class Connection:
        def __init__(self, dialect_name):
            self.dialect = type('Dialect', (), {'name': dialect_name})()

    assert migration._requires_sqlite_reference_rebuild(
        Connection('sqlite')
    ) is True
    assert migration._requires_sqlite_reference_rebuild(
        Connection('postgresql')
    ) is False
    assert migration._requires_sqlite_reference_rebuild(
        Connection('mariadb')
    ) is False
