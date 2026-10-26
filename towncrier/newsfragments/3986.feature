The generated Compose configuration now limits Linux capabilities for the front,
IMAP, and SMTP containers. Dovecot login processes use the dedicated `dovenull`
account, Dovecot authentication workers run as the internal `dovecot` user, and
Postfix's SMTP servers run chrooted under the queue directory. SMTP keeps
no-new-privileges disabled because Postfix's `postdrop` helper relies on setgid
execution; adding the `postdrop` group to the container would grant it to
processes that inherit container supplementary groups.
