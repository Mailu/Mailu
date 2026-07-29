"""Focused tests for the explicit legacy-alias SCIM adoption command."""

from mailu import models


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
        group = models.ScimResource.get_exact(
            'legacy-list@example.com',
            resource_type='Group',
        )
        assert group is not None
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
