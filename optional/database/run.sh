#!/bin/sh

MYSQL_DATABASE=mailu
MYSQL_USER=mailu
MYSQL_PASSWORD=mailu
# Import my.cnf if available
if [ -d "/data/my.cnf" ]; then
	echo "[i] my.cnf exist, using non default configuration"
	cp /data/my.cnf /etc/mysql/my.cnf
fi

if [ -d "/run/mysqld" ]; then
	echo "[i] mysqld already present, skipping creation"
	chown -R mysql:mysql /run/mysqld
else
	echo "[i] mysqld not found, creating...."
	mkdir -p /run/mysqld
	chown -R mysql:mysql /run/mysqld
fi

if [ -d /var/lib/mysql/mysql ]; then
	echo "[i] MySQL directory already present, skipping creation"
	chown -R mysql:mysql /var/lib/mysql
else
	echo "[i] MySQL data directory not found, creating initial DBs"

	chown -R mysql:mysql /var/lib/mysql

	mysql_install_db --user=mysql > /dev/null

	if [ "$MYSQL_ROOT_PASSWORD" = "" ]; then
		MYSQL_ROOT_PASSWORD=`pwgen 16 1`
		echo "[i] MySQL root Password: $MYSQL_ROOT_PASSWORD"
	fi

	MYSQL_DATABASE=${MYSQL_DATABASE:-""}
	MYSQL_USER=${MYSQL_USER:-""}
	MYSQL_PASSWORD=${MYSQL_PASSWORD:-""}

	tfile=`mktemp`
	if [ ! -f "$tfile" ]; then
	    return 1
	fi

	cat << EOF > $tfile
USE mysql;
FLUSH PRIVILEGES;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' identified by '$MYSQL_ROOT_PASSWORD' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' identified by '$MYSQL_ROOT_PASSWORD' WITH GRANT OPTION;
UPDATE user SET password=PASSWORD("") WHERE user='root' AND host='localhost';
EOF

	if [ "$MYSQL_DATABASE" != "" ]; then
	    echo "[i] Creating database: $MYSQL_DATABASE"
	    echo "CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\` CHARACTER SET utf8 COLLATE utf8_general_ci;" >> $tfile

	    if [ "$MYSQL_USER" != "" ]; then
		echo "[i] Creating user: $MYSQL_USER with password $MYSQL_PASSWORD"
		echo "GRANT ALL ON \`$MYSQL_DATABASE\`.* to '$MYSQL_USER'@'%' IDENTIFIED BY '$MYSQL_PASSWORD';" >> $tfile
	    fi
	fi

    #Import SQL Dump if available
    if [ -e "/data/mailu.sql" ]; then
	    echo "[i] Previous Mailu installation exist, importing it"
	    echo "USE mailu;" >> $tfile
	    cat /data/mailu.sql >> $tfile
    fi

	/usr/bin/mysqld --user=mysql --bootstrap --verbose=0 < $tfile
	rm -f $tfile

fi

exec /usr/bin/mysqld --user=mysql --console
