Outgoing-only domains
=====================

Overview
--------

The **Outgoing only** flag marks a domain as one Mailu is used only to send
mail *from* — incoming mail for that domain is delivered by another provider
(for example Google Workspace, Microsoft 365, or a corporate MX elsewhere).

When the flag is set, Postfix no longer treats the domain as a local mailbox
domain: another Mailu-hosted domain sending mail to an address at this
outgoing-only domain will be routed out through DNS/MX like any external
recipient, instead of being (incorrectly) resolved locally and bouncing with
``User doesn't exist``.

Common use case
---------------

You host ``example.com`` mailboxes on Google Workspace, but want to send
outbound mail through your Mailu instance so it is DKIM-signed with your key
and comes from your IP range. In Mailu's admin UI you add ``example.com`` as
a domain (so you can create users/aliases that authenticate against Mailu
for submission, and set up DKIM), and tick **Outgoing only**.

Without the flag, any *other* Mailu-hosted domain that sends mail to
``someone@example.com`` will have Mailu attempt local delivery, fail because
no such mailbox exists on Mailu, and bounce — even though the message should
have gone to Google's MX.

Enabling
--------

In the admin UI, open the domain's edit page and check **Outgoing only**.
The flag is also settable via the REST API (``outgoing_only``) and via the
YAML config import/export.

Effect on Postfix
-----------------

The internal ``/postfix/domain/<name>`` lookup used by ``mailbox_domains``
returns 404 for outgoing-only domains, so Postfix does not include them in
its local delivery domain set. Alternative names of the domain are not
affected by the flag.

DKIM signing, submission authentication, and per-user rate limiting keep
working as usual for the domain — only local recipient resolution is
disabled.
