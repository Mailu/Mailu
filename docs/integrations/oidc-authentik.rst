OpenID Connect with Authentik
=============================

Mailu can use OpenID Connect for web/admin authentication. This is intended for
browser login only. SMTP, IMAP, POP3, submission, and sieve clients continue to
use Mailu-managed passwords or application-specific passwords.

Provider settings
-----------------

Create an Authentik OAuth2/OpenID provider with:

* Client type: confidential
* Grant type: authorization code
* Scopes: ``openid email profile``
* Redirect URI: ``https://<mail-host>/sso/oidc/callback``

Mailu configuration
-------------------

Enable OIDC and point Mailu at the provider discovery document:

.. code-block:: text

   OIDC_ENABLED=true
   OIDC_DISCOVERY_URL=https://<auth-host>/application/o/<application-slug>/.well-known/openid-configuration
   OIDC_CLIENT_ID=<client-id>
   OIDC_CLIENT_SECRET=<client-secret>
   OIDC_REDIRECT_URI=https://<mail-host>/sso/oidc/callback

The discovery document should provide the authorization, token, and UserInfo
endpoints. If discovery is not available, configure the endpoints explicitly:

.. code-block:: text

   OIDC_AUTHORIZATION_ENDPOINT=https://<auth-host>/application/o/authorize/
   OIDC_TOKEN_ENDPOINT=https://<auth-host>/application/o/token/
   OIDC_USERINFO_ENDPOINT=https://<auth-host>/application/o/userinfo/

Optional settings:

.. code-block:: text

   OIDC_SCOPES=openid email profile
   OIDC_EMAIL_CLAIM=email
   OIDC_REQUIRE_EMAIL_VERIFIED=true
   OIDC_CREATE_USER=false
   OIDC_ALLOWED_DOMAINS=example.com,example.org
   OIDC_CLIENT_AUTH_METHOD=client_secret_basic

By default, OIDC login only succeeds for existing enabled Mailu users. Set
``OIDC_CREATE_USER=true`` to create a Mailu mailbox automatically when the
provider returns a verified email address in an existing Mailu domain. Automatic
creation respects ``Domain.max_users`` and can be restricted with
``OIDC_ALLOWED_DOMAINS``.

Security notes
--------------

The login flow uses authorization-code login with state checking and PKCE. Mailu
exchanges the code server-side, calls the provider UserInfo endpoint with the
returned access token, and maps the configured email claim to a Mailu user.

Use HTTPS for Mailu and the identity provider, keep client secrets out of source
control, and keep ``OIDC_REQUIRE_EMAIL_VERIFIED=true`` unless your provider has a
separate trusted email-verification policy.

Operational notes
-----------------

Deployments can still place an external authentication proxy in front of Mailu
as an additional access gate. Native OIDC support does not depend on that proxy
being present.
