from urllib.parse import quote

from mailu import models


class TestOutgoingOnlyDomain:
    """Tests for the Domain.outgoing_only flag.

    When outgoing_only is True, Postfix must not treat the domain as a local
    mailbox domain: the /internal/postfix/domain/<name> endpoint must answer
    404 for it. This keeps other Mailu-hosted domains from bouncing mail sent
    to the outgoing-only domain (whose MX points elsewhere) with a spurious
    'User doesn't exist' instead of routing it out via DNS.
    """

    def test_default_domain_is_delivered_locally(self, app, client):
        with app.app_context():
            models.db.session.add(models.Domain(name='example.com'))
            models.db.session.commit()
            rv = client.get(f"/internal/postfix/domain/{quote('example.com')}")
            assert rv.status_code == 200
            assert rv.get_json() == 'example.com'

    def test_outgoing_only_domain_returns_404(self, app, client):
        with app.app_context():
            models.db.session.add(models.Domain(name='sendonly.example', outgoing_only=True))
            models.db.session.commit()
            rv = client.get(f"/internal/postfix/domain/{quote('sendonly.example')}")
            assert rv.status_code == 404

    def test_toggling_flag_changes_lookup(self, app, client):
        with app.app_context():
            d = models.Domain(name='toggle.example')
            models.db.session.add(d)
            models.db.session.commit()
            assert client.get(f"/internal/postfix/domain/{quote('toggle.example')}").status_code == 200

            d.outgoing_only = True
            models.db.session.commit()
            assert client.get(f"/internal/postfix/domain/{quote('toggle.example')}").status_code == 404

            d.outgoing_only = False
            models.db.session.commit()
            assert client.get(f"/internal/postfix/domain/{quote('toggle.example')}").status_code == 200

    def test_default_value_is_false(self, app):
        with app.app_context():
            d = models.Domain(name='default.example')
            models.db.session.add(d)
            models.db.session.commit()
            fetched = models.Domain.query.get('default.example')
            assert fetched.outgoing_only in (False, None)
