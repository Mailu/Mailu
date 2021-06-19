Changing the database back-end
==============================

By default Mailu uses a SQLite database. Recently, we have changed the internals of Mailu
to enable the support of alternative database solutions as postgresql and mysql/mariadb.
This functionality should still be considered experimental!

Mailu Postgresql
----------------

Mailu optionally comes with a pre-configured Postgresql image, wich as of 1.8 is deprecated
will be removed in 1.9
This images has the following features:

- Automatic creation of users, db, extensions and password;
- TCP connections are only allowed from the mailu `SUBNET`;
- Automatic minutely *wal archiving* and weekly `pg_basebackup`;
- Automatic cleaning of *wal archives* and *base backups*;
  Two versions always remain available;
- When `/data` is empty and backups are present, the backups are restored automatically;
  Useful in swarm environments, since the /data directory should not be on any network 
  filesystem (performance).

To make use of this functionality, just select `postgresql` as database flavor.
Don't select the usage of an external database. The ``docker-compose.yml`` and ``mailu.env``
will pull in ``mailu/postgresql``. This image and ``mailu/admin`` contain all the scripts
to automatically setup the database.

After bring up the service, it might be useful to check the logs with:

.. code-block:: bash

  docker-compose logs -f admin database

External Postgresql
-------------------

It is also possible to use a Postgresql database server, hosted elsewhere.
In this case you'll have to take to create an empty database for Mailu, corresponding user,
password and sufficient privileges on the database to ``CREATE TABLE``, ``DROP`` etc.
Usually making the user owner of the database would be the easiest thing to do.
Don't forget to set ``pg_hba.conf`` accordingly.

The following commands can serve as an example on how to set up postgresql for Mailu usage.
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

Note that this example is the bare-minimum to get Mailu working. It goes without saying that
the database admin will have to setup his own means of backups and TLS encrypted connections.

External MySQL/Mariadb
----------------------

It is also possible to use a mysql/mariadb database server, hosted elsewhere.
In this case you'll have to take to create an empty database for Mailu, corresponding user,
password and sufficient privileges on the database to ``CREATE TABLE``, ``DROP`` etc.
Usually making the user owner of the database would be the easiest thing to do.

The following commands can serve as an example on how to set up mysql/mariadb for Mailu usage.
Adjust this to your own liking.

.. code-block:: sql

  mysql> CREATE DATABASE mailu;
  mysql> CREATE USER 'mailu'@'%' IDENTIFIED BY 'my-strong-password-here';
  mysql> GRANT ALL PRIVILEGES ON mailu.* TO 'mailu'@'%';
  mysql> FLUSH PRIVILEGES;
  
Note that if you get any errors related to ``caching_sha2_password`` it can be solved by changing the encryption 
of the password to ``mysql_native_password`` instead of the latest authentication plugin ``caching_sha2_password``.

.. code-block:: sql

  mysql> SELECT host, user, plugin FROM mysql.user;
  
  +-----------+-------+-----------------------+
  | host      | user  | plugin                |
  +-----------+-------+-----------------------+
  | %         | mailu | caching_sha2_password |
  +-----------+-------+-----------------------+
  
  mysql> update mysql.user set plugin = 'mysql_native_password' where user = 'mailu';
  mysql> SELECT host, user, plugin FROM mysql.user;
  
  +------+-------+-----------------------+
  | host | user  | plugin                |
  +------+-------+-----------------------+
  | %    | mailu | mysql_native_password |
  +------+-------+-----------------------+
