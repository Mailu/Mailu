from mailu import models


def publish(user, uid_keys):
    addresses = models.wkd_addresses_for_user(user, {email for email, _, _ in uid_keys})
    models.update_wkd_keys(user, [entry for entry in uid_keys if entry[0] in addresses])


def test_wkd_alias_lookup_returns_keys_from_multiple_users_with_same_uid(app):
    domain = models.Domain(name='example.test')
    alternative = models.Alternative(name='alternate.test', domain=domain)
    alice = models.User(domain=domain, localpart='alice', gpg_key='alice-key')
    bob = models.User(domain=domain, localpart='bob', gpg_key='bob-key')
    alice.set_password('password')
    bob.set_password('password')
    alias = models.Alias(domain=domain, localpart='team',
        destination=['alice@alternate.test', 'bob@example.test'])
    models.db.session.add_all([domain, alternative, alice, bob, alias])
    models.db.session.commit()

    publish(alice, [
        (alice.email, 'alice-fingerprint', b'alice-key'),
        ('team@example.test', 'alice-fingerprint', b'alice-team-key'),
        ('alice@alternate.test', 'alice-fingerprint', b'alice-alt-key'),
        ('team@alternate.test', 'alice-fingerprint', b'alice-team-alt-key'),
    ])
    publish(bob, [
        (bob.email, 'bob-fingerprint', b'bob-key'),
        ('team@example.test', 'bob-fingerprint', b'bob-team-key'),
        ('bob@alternate.test', 'bob-fingerprint', b'bob-alt-key'),
        ('team@alternate.test', 'bob-fingerprint', b'bob-team-alt-key'),
    ])
    models.db.session.commit()

    def correspondences(localpart, domain_name='example.test'):
        key_hash = models.wkd_hash(localpart)
        return {
            row.user_email
            for row in models.WkdKey.query.filter_by(
                key_hash=key_hash, domain_name=domain_name).all()
        }

    assert correspondences('alice') == {alice.email}
    assert correspondences('team') == {alice.email, bob.email}
    assert correspondences('team', 'alternate.test') == {alice.email, bob.email}
    team_hash = models.wkd_hash('team')
    key_response = app.test_client().get(
        f'/.well-known/openpgpkey/hu/{team_hash}',
        base_url='https://example.test',
    )
    assert key_response.status_code == 200
    assert b'alice-team-key' in key_response.data
    assert b'bob-team-key' in key_response.data
    alternative_response = app.test_client().get(
        f'/.well-known/openpgpkey/hu/{team_hash}',
        base_url='https://alternate.test',
    )
    assert alternative_response.status_code == 200
    assert b'alice-team-alt-key' in alternative_response.data
    assert b'bob-team-alt-key' in alternative_response.data

    alias.destination = [bob.email]
    models.db.session.commit()
    # Alias changes are indexed when a mailbox key is next saved.
    assert correspondences('team') == {alice.email, bob.email}
    publish(alice, [
        (alice.email, 'alice-fingerprint', b'alice-key'),
        ('team@example.test', 'alice-fingerprint', b'alice-team-key'),
        ('alice@alternate.test', 'alice-fingerprint', b'alice-alt-key'),
        ('team@alternate.test', 'alice-fingerprint', b'alice-team-alt-key'),
    ])
    models.db.session.commit()
    assert correspondences('team') == {bob.email}
    assert correspondences('team', 'alternate.test') == {bob.email}

    alias.disabled = True
    models.db.session.commit()
    assert correspondences('team') == {bob.email}
    publish(bob, [
        (bob.email, 'bob-fingerprint', b'bob-key'),
        ('bob@alternate.test', 'bob-fingerprint', b'bob-alt-key'),
    ])
    models.db.session.commit()
    assert correspondences('team') == set()
    assert correspondences('team', 'alternate.test') == set()


def test_uid_authorization_requires_exact_alias_destination(app):
    domain = models.Domain(name='example.test')
    user = models.User(email='alice@example.test', domain=domain, password='unused')
    aliases = [
        models.Alias(email='allowed@example.test', domain=domain, destination=[user.email]),
        models.Alias(email='substring@example.test', domain=domain, destination=['notalice@example.test']),
        models.Alias(email='disabled@example.test', domain=domain, destination=[user.email], disabled=True),
        models.Alias(email='wildcard@example.test', domain=domain, destination=[user.email], wildcard=True),
    ]
    models.db.session.add_all([domain, user, *aliases])
    models.db.session.commit()
    uid_emails = {user.email, *(alias.email for alias in aliases), 'unknown@example.test'}
    assert models.wkd_addresses_for_user(user, uid_emails) == {user.email, 'allowed@example.test'}
