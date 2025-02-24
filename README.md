<!-- markdownlint-disable MD033 MD041 MD042 -->
<p align="center">
  <img src="docs/assets/logomark.png" alt="Mailu" width="128" />
  <img src="docs/assets/plus.svg" alt="+" width="96" />
  <img src="docs/assets/oidc.svg" alt="OIDC" width="128" />
</p>
<h1 align="center">Mailu-OIDC</h1>
<p align="center">
  Multi-container mail server landscape<br />
  featuring OpenID Connect authentication
</p>

---

Mailu is a simple yet full-featured mail server as a set of Docker images.
It is free software (both as in free beer and as in free speech), open to
suggestions and external contributions. The project aims at providing people
with an easily setup, easily maintained and full-featured mail server while
not shipping proprietary software nor unrelated features often found in
popular groupware.

Most of the documentation is available [below](#getting-started), and on the [Mailu Website](https://mailu.io).

> [!NOTE]
> This fork is extended by an OpenID Connect implementation to enable single
> sign-on user session handling and authentication using OIDC providers. The
> fork is maintained by [Heviat](https://heviat.com), a German cloud computing
> company based in Potsdam. Feel free to contribute to this repository!

## Features

![Domains](docs/assets/screenshots/domains.png)

Main features include:

- **Standard email server**, IMAP and IMAP+, SMTP and Submission with auto-configuration profiles for clients
- **Advanced email features**, aliases, domain aliases, custom routing, full-text search of email attachments
- **Web access**, multiple Webmails and administration interface
- **User features**, aliases, auto-reply, auto-forward, fetched accounts, managesieve
- **Admin features**, global admins, announcements, per-domain delegation, quotas
- **Security**, enforced TLS, DANE, MTA-STS, Letsencrypt!, outgoing DKIM, anti-virus scanner, [Snuffleupagus](https://github.com/jvoisin/snuffleupagus/), block malicious attachments
- **Antispam**, auto-learn, greylisting, DMARC and SPF, anti-spoofing
- **Freedom**, all FOSS components, no tracker included
- **Integration** with OpenID Connect providers for single sign-on

## Getting Started

### Quick Overview

1. Check the [Docker Compose Requirements](https://mailu.io/2024.06/compose/requirements.html)
2. Create your installation directory (e.g. `mkdir /mailu && cd /mailu`)
3. Generate a `docker-compose.yml` file and a `mailu.env` file using the
   [Mailu Configuration Assistant](https://setup.mailu.io/2024.06/).
4. Replace all `mailu` docker images with `heviat/mailu-oidc` in the `docker-compose.yml` file. See [details below](#replacing-docker-images).
5. Add the [required OIDC environment variables](#setting-up-variables) to the `mailu.env` file
6. Continue with the official setup guide [from here](https://mailu.io/2024.06/compose/setup.html#tls-certificates)

### Replacing Docker Images

To use the OIDC-enabled Mailu images, the Docker images have to be downloaded
from `ghcr.io/heviat` instead of `ghcr.io/mailu`. To do so, you can simply
place a `.env` file in the installation directory and set `DOCKER_ORG` and
`MAILU_VERSION` environment variables matching our Docker images:

Example `.env` file:

```properties
DOCKER_ORG=ghcr.io/heviat
MAILU_VERSION=2024.06
```

### Setting Up Variables

To enable OpenID Connect authentication, the following additional configuration
properties are needed in `mailu.env`:

|             Property Name               |                                                      Description                                                    |           Example         |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `OIDC_ENABLED`                          | Enable OpenID Connect                                                                                               | `True` \| `False`         |
| `OIDC_PROVIDER_INFO_URL`                | OpenID Connect provider information url (without `/.well-known/openid-configuration` suffix)                        | [https://`host`:`port`/auth/realms/`realm`]() |
| `OIDC_REDIRECT_URL`                     | OpenID Connect custom redirect URL if HOSTNAME not matching your login url                                          | [https://`host`]()        |
| `OIDC_CLIENT_ID`                        | OpenID Connect Client ID for Mailu                                                                                  | `6779ef20e75817b79602`    |
| `OIDC_CLIENT_SECRET`                    | OpenID Connect Client Secret for Mailu                                                                              | `3d66bbd6d0a69af62de7...` |
| `OIDC_BUTTON_NAME`                      | Label text for the "login-with-OpenID" button                                                                       | `OpenID Connect`          |
| `OIDC_VERIFY_SSL`                       | Disable TLS certificate verification for the OIDC client                                                            | `True` \| `False`         |
| `OIDC_CHANGE_PASSWORD_REDIRECT_ENABLED` | If enabled, OIDC users will have an button to get redirect to their OIDC provider to change their password          | `True` \| `False`         |
| `OIDC_CHANGE_PASSWORD_REDIRECT_URL`     | Defaults to provider issuer url appended by `/.well-known/change-password`.                                         | [https://`host`/pw-change]() |

Here is a snippet for easy copy paste:

```properties
################################### 
# OpenID Connect settings
###################################

# Enable OpenID Connect. Possible values: True, False
OIDC_ENABLED=True
# OpenID Connect provider configuration URL
OIDC_PROVIDER_INFO_URL=https://<host>:<port>/auth/realms/.well-known/openid-configuration
# OpenID redirect URL if HOSTNAME not matching your login url
OIDC_REDIRECT_URL=https://mail.example.com
# OpenID Connect Client ID for Mailu
OIDC_CLIENT_ID=<CLIENT_ID>
# OpenID Connect Client secret for Mailu
OIDC_CLIENT_SECRET=<CLIENT_SECRET>
# Label text for OpenID Connect login button. Default: OpenID Connect
OIDC_BUTTON_NAME=OpenID Connect
# Disable TLS certificate verification for the OIDC client. Possible values: True, False
OIDC_VERIFY_SSL=True
# Enable redirect to OIDC provider for password change. Possible values: True, False
OIDC_CHANGE_PASSWORD_REDIRECT_ENABLED=True
# Redirect URL for password change. Defaults to provider issuer url appended by /.well-known/change-password
OIDC_CHANGE_PASSWORD_REDIRECT_URL=https://oidc.example.com/pw-change
```

### Signing In

Click on the "OpenID Connect" button[^1] on the login page to sign in with your
OpenID Connect provider. You will be redirected to the provider's login page
where you can sign in with your credentials. After successful authentication,
you will be redirected to the Mailu admin panel.

[^1]: If you don't see the "OpenID Connect" button, make sure you have set up
      the OIDC environment variables correctly in the `mailu.env` file.

Use the button in the sidebar to open your mailbox on the web. Set up a user
token to sign in to external email clients like Thunderbird or Outlook. See
[Authentication tokens](https://mailu.io/2024.06/webadministration.html#authentication-tokens)
in the Mailu documentation for more information.

## Contributing

Mailu-OIDC is free software, open to suggestions and contributions. All
components are free software and compatible with the MIT license. All
specific configuration files, Dockerfiles and code are placed under the
MIT license.
