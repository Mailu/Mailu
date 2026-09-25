"""Regression specifications for mailbox syntax and internationalization."""

from urllib.parse import quote

import pytest
import sqlalchemy

from mailu import models
from mailu.internal import nginx
from mailu.ui import forms


EAI_LOCALPART = "\u6d4b\u8bd52"
IDN_DOMAIN = "b\u00fccher.example"
IDN_ALABEL = "xn--bcher-kva.example"


def bearer(app):
    return {"Authorization": f'Bearer {app.config["API_TOKEN"]}'}


def make_email(model, localpart, domain_name="example.com"):
    if model is models.User:
        email = model(localpart=localpart, domain_name=domain_name)
        email.set_password("password")
        return email
    return model(
        localpart=localpart,
        domain_name=domain_name,
        destination=["target@example.net"],
    )


@pytest.mark.parametrize(
    "domain",
    [
        "invalid_example.test",
        "-invalid.example",
        "invalid-.example",
        "invalid..example",
    ],
)
def test_postfix_alias_map_rejects_invalid_domains_cleanly(app, client, domain):
    """#4053: malformed domains must not turn a map miss into a temporary error."""
    with app.app_context():
        address = quote(f"recipient@{domain}", safe="")
        response = client.get(f"/internal/postfix/alias/{address}")

        assert response.status_code == 404


def test_postfix_alias_map_accepts_unicode_and_alabel_domains(app, client):
    """Valid IDNA U-label and A-label forms must resolve identically."""
    with app.app_context():
        models.db.session.add(models.Domain(name=IDN_DOMAIN))
        user = make_email(models.User, "recipient", IDN_DOMAIN)
        models.db.session.add(user)
        models.db.session.commit()

        for domain in (IDN_DOMAIN, IDN_ALABEL):
            address = quote(f"recipient@{domain}", safe="")
            response = client.get(f"/internal/postfix/alias/{address}")

            assert response.status_code == 200
            assert response.get_json() == f"recipient@{IDN_ALABEL}"


@pytest.mark.parametrize("endpoint", ["mailbox", "sender/rate"])
def test_postfix_mailbox_maps_reject_keys_without_at(app, client, endpoint):
    with app.app_context():
        response = client.get(f"/internal/postfix/{endpoint}/localpart")

        assert response.status_code == 404


@pytest.mark.parametrize("resource", ["user", "alias"])
@pytest.mark.parametrize("domain", ["\U0001f600.example", "xn--e28h.example"])
def test_api_rejects_non_idna_domains_cleanly(app, client, resource, domain):
    address = quote(f"recipient@{domain}", safe="")
    with app.app_context():
        response = client.get(
            f"/api/v1/{resource}/{address}",
            headers=bearer(app),
        )

        assert response.status_code == 400


@pytest.mark.parametrize(
    "model",
    [
        pytest.param(models.User, id="user"),
        pytest.param(models.Alias, id="alias"),
    ],
)
@pytest.mark.parametrize(
    "localpart",
    [
        pytest.param("a" * 65, id="65-ascii-octets"),
        pytest.param("a" * 63 + "\u00e9", id="65-utf8-octets"),
    ],
)
def test_localpart_over_64_octets_is_rejected(app, model, localpart):
    """#2696: RFC 5321 and RFC 6531 limit a local-part to 64 octets."""
    assert len(localpart.encode("utf-8")) == 65

    with app.app_context():
        models.db.session.add(models.Domain(name="example.com"))

        with pytest.raises((ValueError, sqlalchemy.exc.StatementError)):
            email = make_email(model, localpart)
            models.db.session.add(email)
            models.db.session.commit()


@pytest.mark.parametrize(
    "model",
    [
        pytest.param(models.User, id="user"),
        pytest.param(models.Alias, id="alias"),
    ],
)
def test_localpart_lowercase_form_must_fit_in_64_octets(app, model):
    localpart = "A" * 62 + "\u0130"
    assert len(localpart.encode("utf-8")) == 64
    assert len(localpart.lower().encode("utf-8")) == 65

    with app.app_context():
        models.db.session.add(models.Domain(name="example.com"))

        with pytest.raises((ValueError, sqlalchemy.exc.StatementError)):
            email = make_email(model, localpart)
            models.db.session.add(email)
            models.db.session.commit()


@pytest.mark.parametrize(
    "model",
    [
        pytest.param(models.User, id="user"),
        pytest.param(models.Alias, id="alias"),
    ],
)
@pytest.mark.parametrize(
    "localpart",
    [
        pytest.param("a" * 64, id="64-ascii-octets"),
        pytest.param("a" * 62 + "\u00e9", id="64-utf8-octets"),
    ],
)
def test_localpart_at_64_octets_is_accepted(app, model, localpart):
    assert len(localpart.encode("utf-8")) == 64

    with app.app_context():
        models.db.session.add(models.Domain(name="example.com"))
        email = make_email(model, localpart)
        models.db.session.add(email)
        models.db.session.commit()

        email_address = email.email
        models.db.session.expire_all()
        assert models.db.session.get(model, email_address).localpart == localpart


def test_eai_localpart_round_trips_through_internal_lookups(
    app, client, monkeypatch
):
    """#989: document the EAI support already present below validation."""
    with app.app_context():
        models.db.session.add(models.Domain(name="example.com"))
        user = make_email(models.User, EAI_LOCALPART)
        alias = make_email(models.Alias, f"alias-{EAI_LOCALPART}")
        alias.destination = [user.email]
        models.db.session.add_all([user, alias])
        models.db.session.commit()

        models.db.session.expire_all()
        assert models.db.session.get(models.User, user.email).localpart == EAI_LOCALPART

        encoded_user = quote(user.email, safe="")
        response = client.get(f"/internal/dovecot/passdb/{encoded_user}")
        assert response.status_code == 200

        monkeypatch.setattr(
            nginx,
            "get_server",
            lambda protocol, authenticated: ("127.0.0.1", 143),
        )
        response = client.get(
            "/internal/auth/email",
            headers={
                "Auth-Method": "plain",
                "Auth-Protocol": "imap",
                "Auth-User": encoded_user,
                "Auth-Pass": "password",
                "Auth-Port": "143",
                "Client-Ip": "127.0.0.1",
                "Client-Port": "12345",
            },
        )
        assert response.status_code == 200
        assert response.headers["Auth-Status"] == "OK"
        assert "Auth-User" not in response.headers

        for endpoint, address, expected in (
            ("mailbox", user.email, user.email),
            ("alias", alias.email, user.email),
            ("sender/login", user.email, user.email),
        ):
            encoded = quote(address, safe="")
            response = client.get(f"/internal/postfix/{endpoint}/{encoded}")

            assert response.status_code == 200
            assert response.get_json() == expected


@pytest.mark.parametrize(
    ("form_type", "data"),
    [
        (
            forms.UserForm,
            {"localpart": EAI_LOCALPART, "pw": "", "pw2": ""},
        ),
        (
            forms.AliasForm,
            {
                "localpart": EAI_LOCALPART,
                "destination": ["target@example.net"],
            },
        ),
    ],
)
def test_ui_accepts_eai_localparts(app, form_type, data):
    """#989: RFC 6531 extends dot-atom local-parts with UTF-8 characters."""
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_request_context(method="POST", data=data):
        form = form_type()
        form.validate()

        assert not form.localpart.errors


def test_user_api_accepts_eai_localpart(app, client):
    """#989: account creation must accept an internationalized local-part."""
    email = f"{EAI_LOCALPART}@example.com"
    with app.app_context():
        models.db.session.add(models.Domain(name="example.com"))
        models.db.session.commit()

        response = client.post(
            "/api/v1/user",
            json={"email": email, "raw_password": "password"},
            headers=bearer(app),
        )

        assert response.status_code == 200
        assert models.db.session.get(models.User, email) is not None


def test_alias_api_accepts_eai_localpart(app, client):
    """#989: alias creation must accept an internationalized local-part."""
    alias_email = f"alias-{EAI_LOCALPART}@example.com"
    with app.app_context():
        models.db.session.add(models.Domain(name="example.com"))
        destination = make_email(models.User, "target")
        models.db.session.add(destination)
        models.db.session.commit()

        response = client.post(
            "/api/v1/alias",
            json={"email": alias_email, "destination": [destination.email]},
            headers=bearer(app),
        )

        assert response.status_code == 200
        assert models.db.session.get(models.Alias, alias_email) is not None
