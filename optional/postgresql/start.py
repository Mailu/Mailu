#!/usr/bin/python3

import anosql
import psycopg2
import jinja2
import glob
import os

def setup():
    conn =  psycopg2.connect(user = 'postgres')
    queries = anosql.load_queries('postgres', '/conf/queries.sql')
    # Mailu user
    queries.create_mailu_user(conn)
    queries.update_pw(conn, pw=os.environ.get("SECRET_KEY"))
    # Healthcheck user
    queries.create_health_user(conn)
    conn.commit()
    # create db cannot be atomic. But this script is the only active connection, this is kinda safe.
    if not queries.check_db(conn):
        conn.set_isolation_level(0)
        queries.create_db(conn)
        conn.set_isolation_level(1)
    conn.close()
    conn = psycopg2.connect(user = 'postgres', database= 'mailu')
    queries.create_citext(conn)
    conn.commit()
    conn.close()

# Bootstrap the database if postgresql is running for the first time
if not os.path.exists('/data/pg_wal'):
    os.system("chown -R postgres:postgres /data")
    os.system("su - postgres -c 'initdb -D /data'")

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))
for pg_file in glob.glob("/conf/*.conf"):
    convert(pg_file, os.path.join("/data", os.path.basename(pg_file)))

# Run postgresql locally for DB and user creation
os.system("su - postgres -c 'pg_ctl start -D /data -o \"-h localhost\"'")
setup()
os.system("su - postgres -c 'pg_ctl stop -m smart -w -D /data'")

# Run postgresql service
os.system("su - postgres -c 'postgres -D /data -h \*'")
