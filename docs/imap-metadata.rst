IMAP METADATA and BURL
======================

Mailu supports the IMAP METADATA extension and BURL message submission for
compatible mail clients. METADATA lets clients store and retrieve annotations
for an IMAP server or mailbox, as defined by `RFC 5464
<https://www.rfc-editor.org/rfc/rfc5464.html>`_.

BURL lets a submission client send a reference to message content already
available from IMAP instead of downloading that content and uploading it again
over SMTP. The client obtains an authorized IMAP URL with URLAUTH and submits it
using BURL (`RFC 4467 <https://www.rfc-editor.org/rfc/rfc4467.html>`_ and
`RFC 4468 <https://www.rfc-editor.org/rfc/rfc4468.html>`_). Mailu's storage
Dovecot resolves the URL and passes the resulting message to the normal
outgoing mail path.

Using these extensions
----------------------

No additional Mailu setup is needed. Connect to IMAP and authenticated message
submission as usual. The server advertises METADATA and URLAUTH over IMAP, and
advertises BURL after authentication to the submission service. A mail client
must implement the relevant extensions to use them; clients without BURL
support continue to submit message content over SMTP normally.

Treat URLAUTH URLs as authorization-bearing references to mailbox content. Let
the mail client generate and use these URLs rather than sharing or editing them
manually.
