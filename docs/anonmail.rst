Anonymous Email Service
=================================

Overview
--------
This document describes the Anonymous Email Service. The feature provides an API and UI to create
random/anonymous aliases. The API is modelled after SimpleLogin and works with clients like Bitwarden to generate per-login aliases.

Key capabilities

- Create a random alias via API or via the web UI.
- Optionally derive alias localparts from a provided website hostname (readable prefix + word format, e.g. github.alpha@example.com).
- Per-domain access controls so users can be permitted to create aliases for specific domains.
- Aliases include metadata such as the originating website, owner address, and an enabled/disabled state.


API: create a random alias
-------------------------

Endpoint
~~~~~~~

Anonymous aliases — quick API guide
===================================

This page shows the single, user-facing API you need: creating a random
anonymous alias using your user token and how to store/use that token in a
password manager such as Bitwarden.

What you need
-------------

- A personal application token (create it in the Admin UI under
  "Authentication tokens").
- Your Mailu admin must have enabled anonymous aliases for the domain you
  intend to use.

Create a random alias (API)
---------------------------

Endpoint: ``POST /api/alias/random/new``

Authentication: pass your token in the header

- Header name: use either ``Authorization: Bearer <TOKEN>`` or
  ``Authentication: <TOKEN>`` (Bitwarden compatibility).

Query parameters / body

- ``hostname`` (query param): optional website hostname to influence the
  alias prefix (e.g. ``www.github.com`` → ``github.word@domain``).
- JSON body (optional): ``note`` (string), ``destination`` (string or array).

Minimal curl example

::

  TOKEN="<PASTE_YOUR_TOKEN_HERE>"
  curl -s -X POST "https://admin.example.com/api/alias/random/new?hostname=www.github.com" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"note":"Signup for example.com"}' | jq .

Alternative with HTTPie

::

  http POST https://admin.example.com/api/alias/random/new Authorization:"Bearer ${TOKEN}" hostname=="www.github.com" note="Signup for example"

Using Bitwarden (browser extension)
-----------------------------------

1. Create a new item in Bitwarden (Login or Secure Note).
2. Store your token in the Password field (or add a custom field named
   ``Authentication`` containing the token). Save the item.
3. When you need to call the API, open the Bitwarden item and copy the token
   to the clipboard, then paste it into the ``Authorization`` header value in
   your HTTP client (or into the shell variable shown above).

Notes and tips
--------------

- The alias will be shown in the API response. Save it where you need it.
- You can temporarily disable an alias from the Admin UI instead of deleting it
  if you want to stop receiving mail for a while.
- The forward email destination is always your own address (the one
  associated with your token or login); you cannot set arbitrary destinations.

Troubleshooting
---------------

- 403 / 401: ensure your token is valid and that anonymous aliases are
  enabled for the target domain; check with your Mailu administrator.
- 404: host/domain not enabled or alias does not exist.

Screenshot placeholders
----------------------

.. image:: _static/screenshots/bitwarden-token-placeholder.png
   :alt: Bitwarden token placeholder

.. image:: _static/screenshots/mailu-anonaliases-ui-placeholder.png
   :alt: Mailu anonaliases UI placeholder
    -d '{"note":"Signup for example service"}'


Mail delivery
-----------------------

Aliases created with this feature are regular mail alias addresses on the
server. Incoming mail to an alias is forwarded to the configured destination
addresses. If an alias is disabled it will no longer accept messages.

Troubleshooting
---------------

- "I can't create an alias": confirm your domain has anonymous aliasing
  enabled and that you were granted access by a domain manager if required.
- "Postfix doesn't route messages": check that the alias is enabled and that
  destinations are valid addresses in the system.

Screenshots (placeholders)
-------------------------

- UI: Create alias dialog

.. image:: _static/screenshots/mailu-anonaliases-ui-placeholder.png
   :alt: Create anonymous alias dialog

- Example: storing token in Bitwarden

.. image:: _static/screenshots/bitwarden-token-placeholder.png
   :alt: Bitwarden token placeholder

Privacy & security notes
------------------------

- Aliases are reversible — the server stores which user created each alias so
  administrators may link an alias to an owner for moderation or abuse
  handling. The anonimity is in the random/opaque nature of the alias towards
  third parties.
- Revoke tokens immediately if you believe they were compromised.