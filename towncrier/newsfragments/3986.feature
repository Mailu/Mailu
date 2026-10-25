The generated Compose configuration now limits Linux capabilities for the front,
IMAP, and SMTP containers. Dovecot login processes use the dedicated `dovenull`
account, Dovecot authentication workers run as the internal `dovecot` user, and
Postfix's SMTP servers run chrooted under the queue directory.
