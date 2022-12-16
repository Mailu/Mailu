External OpenID Connect Provider
================================

Mailu supports the usage of an external OpenID Connect provider as identity provider.

For more information on OpenID Connect, please refer to https://openid.net/connect/

When an OpenID Connect provider is used, all authentication is handled by the OpenID provider.


Important notes
---------------

As the OpenID Connect provider is used as identity provider, the ``enabled`` flag of the user is ignored.

To disable a user, the user needs to be disabled in the OpenID Connect provider.


Configuration
-------------

The following environment variables are used to configure the OpenID Connect provider:

The following options need to be configured:

* ``OIDC_ENABLED`` (default: unset/disabled): Set to ``true`` to enable the feature.
* ``OIDC_CLIENT_ID``: The client ID of the Open ID Connect provider.
* ``OIDC_CLIENT_SECRET``: The client secret of the Open ID Connect provider.
* ``OIDC_PROVIDER_INFO_URL``: The discovery URL of the Open ID Connect provider. (example: ``https://accounts.google.com/.well-known/openid-configuration`` or ``https://<host>:<port>/auth/realms/.well-known/openid-configuration``)
* ``OIDC_BUTTON_NAME``: The name of the button to display on the login page.

Example configuration for Keycloak
``````````````````````````````````

Assumptions:

* Mailu is running on ``https://mailu.example.com``
* Keycloak is running on ``https://keycloak.example.com``


In Keycloak, click on ``Clients`` and then ``Create client``.

Set the following values:

* ``Client type``: ``OpenID Connect``
* ``Client ID``: ``mailu`` (or any other value you want)
* ``Name``: ``mailu`` (or any other value you want)

On the next page, set the following values:

* ``Client authentication``: ``On``
* ``Authentication flow``: select ``Standard Flow`` only

Click on ``Save``.

Under ``Settings``, add the following values:

.. code-block::

  Valid Redirect URIs:
    - https://mailu.example.com/sso/login
    - https://mailu.example.com/sso/login/oidc
    - https://mailu.example.com/sso/logout
  Valid post logout redirect URIs:
    - https://mailu.example.com/sso/logout
  Web Origins:
    - https://mailu.example.com/*

Under ``Credentials``, set the ``Client Authenticator`` to ``Client ID and Secret`` and generate a secret.
Save the secret somewhere safe, it will be needed later.

Under ``Client Scopes``, make sure ``email`` and ``profile`` client scopes are set.

Go back to the ``Settings`` tab and click on ``Save``.

Next, set the following environment variables in Mailu:

* ``OIDC_ENABLED=true``
* ``OIDC_CLIENT_ID=mailu`` (the client ID you set in Keycloak)
* ``OIDC_CLIENT_SECRET=secret`` (the secret generated in Keycloak)
* ``OIDC_PROVIDER_INFO_URL=https://keycloak.example.com/auth/realms/mailu/.well-known/openid-configuration``
* ``OIDC_BUTTON_NAME=Keycloak`` (or any other name you want)

(Re)start Mailu and you should be able to login with Keycloak by clicking on the ``Keycloak`` button on the login page.


F.A.Q.
------

How does the login work?
````````````````````````
When the user clicks on the login button, the user is redirected to the OpenID Connect provider.

How does the user creation work?
````````````````````````````````

If the user doesn't exist in Mailu, it will be created automatically. 
The email address of the user will be set to the email address provided by the OpenID Connect provider.
If the domain of the email address doesn't exist in Mailu, it will be created automatically.


OpenID Connect providers
------------------------

Below is a non exhaustive list of OpenID Connect providers:

* Keycloak: https://www.keycloak.org/
* Google: https://developers.google.com/identity/openid-connect/openid-connect
* Microsoft: https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-protocols-oidc
* Okta: https://www.okta.com/openid-connect/
* Ping Identity: https://docs.pingidentity.com/bundle/solution-guides/page/ywg1598030491145.html
* Auth0: https://auth0.com/docs/authenticate/protocols/openid-connect-protocol
