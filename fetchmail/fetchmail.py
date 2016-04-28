#!/usr/bin/env python

import sqlite3
import time
import os
import tempfile


RC_LINE = """
poll {host} proto {protocol} port {port}
    user "{username}" password "{password}"
    smtphost "smtp"
    smtpname {user_address}
    {options}
"""


def fetchmail(fetchmailrc):
    print(fetchmailrc)
    with tempfile.NamedTemporaryFile() as handler:
        handler.write(fetchmailrc.encode("utf8"))
        handler.flush()
        os.system("fetchmail -N -f '{}'".format(handler.name))


def run(cursor):
    cursor.execute("""
        SELECT user_address, protocol, host, port, tls, username, password
        FROM fetch
    """)
    fetchmailrc = ""
    for line in cursor.fetchall():
        user_address, protocol, host, port, tls, username, password = line
        options = "options ssl" if tls else ""
        fetchmailrc += RC_LINE.format(
            user_address=user_address,
            protocol=protocol,
            host=host,
            port=port,
            username=username,
            password=password,
            options=options
        )
    fetchmail(fetchmailrc)


if __name__ == "__main__":
    db_path = os.environ.get("DB_PATH", "/data/freeposte.db")
    connection = sqlite3.connect(db_path)
    while True:
        time.sleep(int(os.environ.get("FETCHMAIL_DELAY", 10)))
        cursor = connection.cursor()
        run(cursor)
        cursor.close()
