Database
================

Eventhough Mailu is designed to be as simple as possible,
for several reason you may need to use an external DB

MYSQL
----
In order to use it environment variable `DB_TYPE=mysql`
You can use the optional `database` container to start a MariaDB server.
It will automaticaly load file in `/data`:
    - `mailu.sql` file that should contain sql to execute (database backup)
    - `my.cnf` file containing MariaDB config file

Default configuration use in `database` container is :
    DB_HOST = "database"
    DB_PORT = "3306"
    DB_USER = "mailu"
    DB_PASSWORD = "mailu"
    DB_DATABASE = "mailu"
Those can be override by setting your own environment variable.

If using database container you want to map a `/var/lib/mysql` to a volume for persistency
