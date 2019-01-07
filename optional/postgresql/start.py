#!/usr/bin/python3

import anosql
import psycopg2
import jinja2
import glob
import os
import subprocess

def setup():
    conn =  psycopg2.connect(user='postgres')
    queries = anosql.load_queries('postgres', '/conf/queries.sql')
    # Mailu user
    queries.create_mailu_user(conn)
    queries.update_pw(conn, pw=os.environ.get("DB_PW"))
    # Healthcheck user
    queries.create_health_user(conn)
    queries.grant_health(conn)
    conn.commit()
    # create db cannot be atomic. But this script is the only active connection, this is kinda safe.
    if not queries.check_db(conn):
        conn.set_isolation_level(0)
        queries.create_db(conn)
        conn.set_isolation_level(1)
    conn.close()

# Check if /data is empty
if not os.listdir("/data"):
    os.system("chown -R postgres:postgres /data")
    os.system("chmod 0700 /data")
    base_backups=sorted(glob.glob("/backup/base-*"))
    if base_backups:
        # Restore the latest backup
        subprocess.call(["tar", "--same-owner", "-zpxf", base_backups[-1] + "/base.tar.gz" , "-C", "/data"])
        if os.listdir("/backup/wal_archive"):
            with open("/data/recovery.conf", "w") as rec:
                rec.write("restore_command = 'gunzip < /backup/wal_archive/%f > %p'\n")
                rec.write("standby_mode = off\n")
            os.system("chown postgres:postgres /data/recovery.conf")
            #os.system("sudo -u postgres pg_ctl start -D /data -o '-h \"''\" '")
    else:
        # Bootstrap the database
        os.system("sudo -u postgres initdb -D /data")

# Create backup directory structure, if it does not yet exist
os.system("mkdir -p /backup/wal_archive")
os.system("chown -R postgres:postgres /backup")

# Render config files
convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))
for pg_file in glob.glob("/conf/*.conf"):
    convert(pg_file, os.path.join("/data", os.path.basename(pg_file)))

# (Re)start postgresql locally for DB and user creation
os.system("sudo -u postgres pg_ctl start -D /data -o '-h \"''\" '")
while os.path.isfile("recovery.conf"):
    pass
os.system("sudo -u postgres pg_ctl -D /data promote")
setup()
os.system("sudo -u postgres pg_ctl stop -m smart -w -D /data")

out=open("/proc/1/fd/1", "w")
err=open("/proc/1/fd/2", "w")
# Run the cron deamon
subprocess.Popen(["crond", "-f"], stdout=out, stderr=err)
# Run postgresql service
os.system("sudo -u postgres postgres -D /data -h \*")
