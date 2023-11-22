Changing the database back-end
==============================

By default Mailu uses a SQLite database. It is possible to use an alternative database solutions such as PostgreSQL and MySQL/MariaDB.

The Mailu database contains static data. SQLite is sufficient for any deployment scenario of Mailu. There is no need to use a different database system.
The Mailu development team recommends to use SQLite.


Migrating to a different database back-end
------------------------------------------

From Mailu 1.9, Mailu has a :ref:`cli command (link) <config-export>` for exporting and importing the complete Mailu configuration.
Using this tool it is very easy to switch what database back-end is used for Mailu.
Unfortunately roundcube does not have a tool for exporting/importing its configuration.
This means it is not possible to switch the database back-end used by roundcube using out of box tools.

To switch to a different database back-end:

1. Run config-export to export the configuration. E.g. `docker compose exec admin flask mailu config-export --secrets --output /data/mail-config.yml`
2. Set up your new database server. Refer to the subsequent sections for tips for creating the database.
3. Modify the database settings (SQLAlchemy database URL) in mailu.env. Refer to the :ref:`configuration guide (link) <db_settings>` for the exact settings.
4. Start your Mailu deployment.
5. Run config-import to import the configuration...

  1. Drop into a shell inside the admin container as you'll need to execute multiple commands. E.g. `docker exec -i $(docker compose ps -q admin) bash`

  2. Initialize the new database back-end: `flask mailu db init`

  3. Migrate the new database back-end to the current state: `flask mailu db upgrade`

  4. Import the configuration export: `flask mailu config-import -v < /data/mail-config.yml`


Mailu has now been switched to the new database back-end. The Mailu configuration has also been migrated.


External MySQL/MariaDB
----------------------

It is also possible to use a MySQL/MariaDB database server, hosted elsewhere.
In this case you'll have to take to create an empty database for Mailu, corresponding user,
password and sufficient privileges on the database to ``CREATE TABLE``, ``DROP`` etc.
Usually making the user owner of the database would be the easiest thing to do.

The following commands can serve as an example on how to set up MySQL/MariaDB for Mailu usage.
Adjust this to your own liking.

.. code-block:: sql

  mysql> CREATE DATABASE mailu;
  mysql> CREATE USER `mailu`@`%` IDENTIFIED WITH mysql_native_password BY `my-strong-password-here`;
  mysql> GRANT ALL PRIVILEGES ON mailu.* TO 'mailu'@'%';
  mysql> FLUSH PRIVILEGES;


External PostgreSQL
-------------------

It is also possible to use a PostgreSQL database server, hosted elsewhere.
In this case you'll have to take to create an empty database for Mailu, corresponding user,
password and sufficient privileges on the database to ``CREATE TABLE``, ``DROP`` etc.
Usually making the user owner of the database would be the easiest thing to do.
Don't forget to set ``pg_hba.conf`` accordingly.

The following commands can serve as an example on how to set up PostgreSQL for Mailu usage.
Adjust this to your own liking.

.. code-block:: bash

  $ sudo su - postgres
  $ psql
  psql (10.6)
  Type "help" for help.

  postgres=# create user mailu;
  CREATE ROLE
  postgres=# alter user mailu password 'my_secure_pass';
  ALTER ROLE
  postgres=# create database mailu owner mailu;
  CREATE DATABASE
  postgres=# \c mailu
  You are now connected to database "mailu" as user "postgres".
  mailu=# create extension citext;
  CREATE EXTENSION
  mailu=# \q

In ``pg_hba.conf`` there should be a line like this:

.. code-block:: bash

  host    mailu           mailu           <mailu_host>/32            md5

Note that this example is the bare-minimum to get Mailu working. Additional work needs to be
done by the database admin to setup their own means of backups and TLS encrypted connections.

Nowadays it is recommended to use the official PostgreSQL image from the PostgreSQL community. The repository is located `here <https://hub.docker.com/_/postgres>`_.

.. _migrate_mailu_postgresql:

Mailu PostgreSQL
----------------

Mailu optionally came with a pre-configured PostgreSQL image which was deprecated in Mailu 1.8.
Since Mailu 1.9 it is removed from Mailu. The following section describes how to move to a different
PostgreSQL image for novice administrators. The official PostgreSQL image (Postgres) will be used.

A Mailu deployment with the Mailu PostgreSQL image, will only use PostgreSQL for the Admin container
(Web administration interface). Roundcube uses SQLite as database back-end.
Mailu uses the following configuration for connecting to the database:

- Database host: 'database'
- Database name: 'mailu'
- Database user: 'mailu'
- Database password: See DB_PW in mailu.env.

.. note::

   The following instructions assume that
     - project mailu is used. (-p mailu). If a different project (prefix) is used, then a different project can be specified.
     - the data folder is /mailu. Change this to a different value in case Mailu makes use of a different data folder.
     - All commands must be executed as root. On Debian/Ubuntu the sudo command is used to execute commands as root.

Prepare the environment. Mailu must not be in use. Only the database container.

1. Open a terminal.
2. `cd /mailu`
3. `docker compose -p mailu down`
4. `docker compose -p mailu up -d database`

Create the dump SQL file for recreating the database.

1. `docker compose -p mailu exec database /bin/bash`
2. `pg_dump -h database -p 5432 -U mailu > /backup/backup_db.sql`
3. Enter the password. See the value of DB_PW in mailu.env.
4. `exit`
5. The dump is saved to /mailu/data/psql_backup/backup_db.sql.
6. `docker compose -p mailu down`

Prepare the new PostgreSQL deployment.

1. `mkdir -p /mailu/data/external_psql/pgdata`
2. Create the file docker compose-postgresql.yml with the following contents:

.. code-block:: docker

   version: '3.1'
   services:
     database:
       image: postgres:13
       restart: always
       environment:
         - POSTGRES_USER=mailu
         - POSTGRES_PASSWORD=DB_PW from mailu.env file
         - PGDATA=/var/lib/postgresql/data/pgdata
       volumes:
         - "/mailu/data/external_psql/pgdata:/var/lib/postgresql/data/pgdata"
         - "/mailu/data/psql_backup:/dump"


3. `docker compose -f docker compose-postgresql.yml up -d`
4. `docker compose -f docker compose-postgresql.yml exec database /bin/bash`
5. `cat /dump/backup_db.sql | psql -h localhost -p 5432 -U mailu`
6. `exit`
7. `docker compose -f docker compose-postgresql.yml down`
8. Remove the file docker compose-postgresql.yml.

The new PostgreSQL deployment has the dump loaded now. Now it is time to modify Mailu to use the official PostgreSQL docker image.

1. Edit docker-compose.yml and change:

.. code-block:: docker

     database:
       image: ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}postgresql:${MAILU_VERSION:-master}
       restart: always
       env_file: mailu.env
       volumes:
         - "/mailu_db/data/psql_db:/data"
         - "/mailu_db/data/psql_backup:/backup"

to

.. code-block:: docker

     database:
       image: postgres:13
       restart: always
       environment:
         - PGDATA=/var/lib/postgresql/data/pgdata
       volumes:
         - "/mailu/data/external_psql/pgdata:/var/lib/postgresql/data/pgdata"


2. Edit mailu.env and append the following after the block

.. code-block:: docker

   ###################################
   # Database settings
   ###################################


.. code-block:: docker

   SQLALCHEMY_DATABASE_URI=postgresql://mailu:mailu@database/mailu

Mailu is now configured to use the official PostgreSQL docker image. Bring your new deployment online

1. `docker compose -p mailu up -d`

Optionally you can remove left-over files which were used by the old database:

- /mailu/data/psql_backup (old database backup files
- /mailu/data/psql_db (old database files)

.. note::
   Roundcube does not offer a migration tool for moving from SQLite to PostgreSQL.
   In case roundcube is used, the Mailu setup utility can be used to specify SQLite for the roundcube database back-end.
