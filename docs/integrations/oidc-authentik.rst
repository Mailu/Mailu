OpenID Connect with Authentik
=============================

This document tracks planned native OpenID Connect support for Mailu's web
interfaces using Authentik as an example identity provider.

This is intended for web authentication only. SMTP, IMAP, POP3, and submission
clients should continue to use Mailu-managed passwords or application-specific
passwords.

Provider settings
-----------------

Create an Authentik OAuth2/OpenID provider with:

* Client type: confidential
* Grant types: authorization code, refresh token
* Scopes: ``openid email profile``
* Subject mode: user email, or another stable identifier if preferred
* Redirect URI: ``https://<mail-host>/sso/oidc/callback``

Mailu-side configuration should be expressed with environment variables similar
to:

.. code-block:: text

   OIDC_PROVIDER_NAME=authentik
   OIDC_ISSUER=https://<auth-host>/application/o/<application-slug>/
   OIDC_DISCOVERY_URL=https://<auth-host>/application/o/<application-slug>/.well-known/openid-configuration
   OIDC_CLIENT_ID=<client-id>
   OIDC_CLIENT_SECRET=<client-secret>
   OIDC_REDIRECT_URI=https://<mail-host>/sso/oidc/callback
   OIDC_SCOPES=openid email profile
   OIDC_EMAIL_CLAIM=email
   OIDC_SUB_CLAIM=sub

Implementation goals
--------------------

* Add an OIDC login button to the web/admin login flow.
* Exchange authorization codes server-side.
* Validate issuer, audience, signature, expiry, nonce, and state.
* Map the configured email claim to an existing Mailu user.
* Keep mailbox protocol authentication separate from web SSO.
* Avoid committing client secrets or deployment-specific hostnames.

Operational notes
-----------------

Deployments can still place an external authentication proxy in front of Mailu
as an additional access gate. Native OIDC support should not depend on that
proxy being present.
