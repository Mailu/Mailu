Separate Dovecot mailbox homes, Maildir messages, and persistent indexes. Assign
mailboxes distinct Unix identities, chroot mail processes to the mail storage
tree, and rebuild Maildir size metadata and indexes during resumable startup
migration. Rebuild FTS indexes on migration or language changes, and stage ICU
data, stopword files, and required sockets inside the mail chroot. Stage
filesystem imports in the legacy per-address location before restarting IMAP;
recognized imports are migrated incrementally after the initial layout
migration has completed.
