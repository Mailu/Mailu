# RFC: Mailu directory structure
The current layout of the Mailu directory structure can be improved to allow for easier replicated deployments, like Docker Swarm and Kubernetes. Please read https://usrpro.com/publications/mailu-persistent-storage/ for the background motivation of this RFC.

## Scope
This document only describes the re-arrangement of the `$ROOT` Mailu filesystem as-is. This means moving around of current files and directories. The linked article also proposes more advanced improvements. Those are not included in this RFC and need to be evaluated and implemented independently. However, the changes proposed in this document should make such improvements easier.

Currently some services are wrongfully sharing mountpoints or have unused volumes declared. Those are also taken care of in this RFC.

## Compatibility
If these changes were to be accepted, it will break compatibility with previous Mailu version `<=1.7`. As such, we will propably increment to version `2.0`.

## Root
The root of the Mailu filesystem is located at `/mailu` by default. For simplicity we will assume this location throughout the document. Within `/mailu` we will aim to define 3 main sub-directories:

### Config

- Path: `/mailu/config/`

Small config bearing files, sometimes shared between multiple services. The performance and storage needs for this filesystem are low. Availability is important for correct functioning of the mail server. No file locking issues are expected from concurrent access. A basic (and redundant) filesystem should suffice.

#### Dovecot

- Old path: `/mailu/overrides` (shared with postfix, nginx and rspamd)
- New Path `/mailu/config/dovecot`

Dovecot configuration overrides.

#### Postfix

- Old path: `/mailu/overrides` (shared with dovecot, nginx and rspamd)
- New Path `/mailu/config/posfix`

Postfix configuration overrides.

#### Rspamd

- Old path: `/mailu/overrides/rspamd`
- New path: `/mailu/config/rspamd`

RSpamD configuration overrides.

#### Snappymail

- Old path: `/mailu/webmail/_data_/_default_/storage` (part of `/mailu/webmail` mountpoint, shared with Roundcube)
- New path: `/mailu/config/snappymail`

User specific configs. The remaining files under the old `/mailu/webmail` don't need to be persistent. Except for `AddressBook.sqlite`, see `/mailu/data`.

#### Roundcube

- Old path: `/mailu/webmail/gpg` (part of `/mailu/webmail` mountpoint, shared with Snappymail)
- New path: `/mailu/config/roundcube/gpg`

User configured GPG keys.

#### Redis

- Old path: `/mailu/redis`
- New path: `/mailu/config/redis`

Holds `dump.rdb` for data restoration. Although technically a database, Redis works from memory. The dump file is only written to every minute and read from during start. Hence it fits better in the replicated config directory filesystem.

#### Share

- Path: `/mailu/config/share/`

Shared configuration between different services

##### DKIM

- Old path: `/mailu/dkim/`
- New path: `/mailu/config/share/dkim`

DKIM private keys store. Read/write access by Admin. Read only access by rSpamD.

##### Certs

- Old path: `/mailu/certs`
- New path: `/mailu/config/share/certs` (Proposal in anticipation of the RFC outcome at: https://github.com/Mailu/Mailu/issues/1222.)

TLS certificates. Write access from `nginx` in case `TLS_FLAVOR=letsencrypt`. Or write access from `treafik-certdumper` or any other tool obtaining certificates.

`letsencrypt` setting is not compatible with replicated setups. Multiple instances would disrupt the ACME challenge verification and cause race conditions on requesting certificates. In such cases certificates will need to be provided by other tools.

If RFC issue #1222 is accepted, Dovecot will need read-only access to the certificates.

### Data

- Path: `/mailu/data/`

Database files, like SQLite or PostgreSQL files. Databases don't perform well on network filesystems as they depend heavily on file locking and full controll on the database files. Making it unfit for concurrent access from multiple hosts. This directory should always live on a local filesystem. This makes it only usable in `docker compose` deployments. Usage of this directory should be avoided in Kubernetes and Docker Swarm deployments. Some services will need to be improved to allow for this.

#### admin data

- Old path: `/mailu/data/`
- New path: `/mailu/data/admin/` (mount point on `admin` directory)

Holds `main.db` SQLite database file holding domains, users, aliases etcetera. Read/write access only by admin. Can be avoided by using a remote DB server like PostgreSQL, MySQL or MariaDB.

Also holds `instance` for unique statistics transmission. Removing of this file is proposed in RFC [issue 129](https://github.com/Mailu/Mailu/issues/1219).

This move is needed in order to be able to mount the directory without exposing data files from other services into admin.

#### rspamd

- Old path: `/mailu/filter` (shared with ClamAV)
- New path: `/mailu/data/rspamd`

Storage of Bayes and Fuzzy learning SQLite databases and caches. As future optimization we should look into moving all this into Redis.

#### SnappyMail

- Old path: `/mailu/webmail/_data_/_default_/AddressBook.sqlite` (part of `/mailu/webmail` mountpoint, shared with Roundcube)
- New path: `/mailu/data/snappymail/AddressBook.sqlite` (mount on `snappymail` directory)

Addressbook SQLite file. For future replicated deployments this might better be configured to use an external DB.

For this modification, the `AddressBook.sqlite` will need to be moved to a different directory inside the container.

#### Roundcube

- Old path: `/mailu/webmail/roundcube.db` (part of `/mailu/webmail` mountpoint, shared with SnappyMail)
- New path: `/mailu/data/roundcube/roundcube.db` (mount on `roundcube` directory)

User settings SQLite database file for roundcube. For future replicated deployments this might better be configured to use an external DB.

For this modification, the `rouncube.db` file will need to be moved to a different directory inside the container.

### Mail

- Path: `/mailu/mail` (unmodified)

User mail, managed my Dovecot IMAP server. In replicated deployments, this filesystem needs to be shared over all IMAP server instances. It should be high performant and capable of propgating file locks. Storage size is proportional to the users and their quotas. Old versions of NFS are known to be buggy with file locking. Also Samaba or CIFS should be avoided.

In the old situation, Maildir indexes are stored on the same volume. However, they need not to be persistent and should be located on a voletile filesystem instead. This allows better performance on network filesystems.

### Local

- Path: `/mailu/local` (new)

Persistent storage not suitable for replication. In `docker compose` deployments it lives inside `/mailu` and in replicated deployments it should live somewhere on the local host machine.

#### Mailqueue

- Old path: `/mailu/mailqueue`
- New path: `/mailu/local/mailqueue`

The SMTP mailqueue should be persistant, as per SMTP spec it is not allowed to loose mail. However, persistance should be local only for performance reasons and the possibility to replicate Postfix servers. In setups like Docker Swarm and Kubernetes, admins should take care that Postfix is always restarted on same hosts in order to empty any remaining queue after a crash.

#### ClamAV

- Old path: `/mailu/filters` (shared with rSpamD)
- New path: `/mailu/local/clamav`

Virus definitions do not need to be replicated, as they can be easily pulled in when ClamAV instances migrate to other nodes. Persistance does allow for some bandwith and time saving if ClamAV would be restarted on a previously used node (in case of updates or similar cases). Local only storage also prevents `freshclam` race conditions.

## Conclusion

The final layout of the Mailu filesystem will look like:

````
/mailu
├── config
│   ├── dovecot
│   ├── postfix
│   ├── snappymail
│   ├── redis
│   ├── roundcube
│   │   └── gpg
│   ├── rspamd
│   └── share
│       ├── certs
│       └── dkim
├── data
│   ├── admin
│   ├── snappymail
│   ├── roundcube
│   └── rspamd
├── local
│   ├── clamav
│   └── mailqueue
└── mail
````

Where in replicated environments:

- `/mailu/config/`: should be a small, low performant and shared filesystem.
- `/mailu/data`: should be avoided. More work will need to be done to configure external DB servers for relevant services. Ideally, this directory should only exist on docker compose deployments.
- `/mailu/local/`: Should exist only on local file systems of worker nodes.
- `/mailu/mail`: A distributed filesystem with sufficient performance and storage requirements to hold and process all user mailboxes. Ideally only Maildir without indexes.

### Implementing

The works to implement this changes should happen outside the `master` branch. Inclusion into `master` can only be accepted if:

1. `docker-compose.yml` from setup reflects this changes correctly.
2. Kubernetes documentation is updated.
3. Legacy `docker-compose.yml` is either updated or deleted.
4. A clear data migration guide is written.