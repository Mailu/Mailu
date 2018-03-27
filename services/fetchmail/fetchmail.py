#!/usr/bin/env python

import sqlite3
import time
import os
import tempfile
import shlex
import subprocess
import re


FETCHMAIL = """
fetchmail -N \
    --sslcertck --sslcertpath /etc/ssl/certs \
    -f {}
"""

RC_LINE = """
poll "{host}" proto {protocol}  port {port}
    user "{username}" password "{password}"
    is "{user_email}"
    smtphost "{smtphost}"
    {options}
    sslproto 'AUTO'
"""

def extract_host_port(host_and_port, default_port):
    host, _, port = re.match('^(.*)(:([0-9]*))?$', host_and_port).groups()
    return host, int(port) if port else default_port

def escape_rc_string(arg):
    return arg.replace("\\", "\\\\").replace('"', '\\"')


def fetchmail(fetchmailrc):
    with tempfile.NamedTemporaryFile() as handler:
        handler.write(fetchmailrc.encode("utf8"))
        handler.flush()
        command = FETCHMAIL.format(shlex.quote(handler.name))
        output = subprocess.check_output(command, shell=True)
        return output


def run(connection, cursor, debug):
    cursor.execute("""
        SELECT user_email, protocol, host, port, tls, username, password, keep
        FROM fetch
    """)
    smtphost, smtpport = extract_host_port(os.environ.get("HOST_SMTP", "smtp"), None)
    if smtpport is None:
        smtphostport = smtphost
    else:
        smtphostport = "%s/%d" % (smtphost, smtpport)
    for line in cursor.fetchall():
        fetchmailrc = ""
        user_email, protocol, host, port, tls, username, password, keep = line
        options = "options antispam 501, 504, 550, 553, 554"
        options += " ssl" if tls else ""
        options += " keep" if keep else " fetchall"
        fetchmailrc += RC_LINE.format(
            user_email=escape_rc_string(user_email),
            protocol=protocol,
            host=escape_rc_string(host),
            port=port,
            smtphost=smtphostport,
            username=escape_rc_string(username),
            password=escape_rc_string(password),
            options=options
        )
        if debug:
            print(fetchmailrc)
        try:
            print(fetchmail(fetchmailrc))
            error_message = ""
        except subprocess.CalledProcessError as error:
            error_message = error.output.decode("utf8")
            # No mail is not an error
            if not error_message.startswith("fetchmail: No mail"):
                print(error_message)
            user_info = "for %s at %s" % (user_email, host)
            # Number of messages seen is not a error as well
            if ("messages" in error_message and
                    "(seen " in error_message and
                    user_info in error_message):
                print(error_message)
        finally:
            cursor.execute("""
                UPDATE fetch SET error=?, last_check=datetime('now')
                WHERE user_email=?
            """, (error_message.split("\n")[0], user_email))
            connection.commit()


if __name__ == "__main__":
    debug = os.environ.get("DEBUG", None) == "True"
    db_path = os.environ.get("DB_PATH", "/data/main.db")
    connection = sqlite3.connect(db_path)
    while True:
        cursor = connection.cursor()
        run(connection, cursor, debug)
        cursor.close()
        time.sleep(int(os.environ.get("FETCHMAIL_DELAY", 60)))
