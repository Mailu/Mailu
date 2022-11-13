#!/usr/bin/env python3

import time
import os
from pathlib import Path
from pwd import getpwnam
import tempfile
import shlex
import subprocess
import re
import requests
from socrate import system
import sys
import traceback


FETCHMAIL = """
fetchmail -N \
    --idfile /data/fetchids --uidl \
    --pidfile /dev/shm/fetchmail.pid \
    --sslcertck --sslcertpath /etc/ssl/certs \
    -f {}
"""


RC_LINE = """
poll "{host}" proto {protocol}  port {port}
    user "{username}" password "{password}"
    is "{user_email}"
    smtphost "{smtphost}"
    {folders}
    {options}
    {lmtp}
"""


def extract_host_port(host_and_port, default_port):
    host, _, port = re.match('^(.*?)(:([0-9]*))?$', host_and_port).groups()
    return host, int(port) if port else default_port


def escape_rc_string(arg):
    return "".join("\\x%2x" % ord(char) for char in arg)


def fetchmail(fetchmailrc):
    with tempfile.NamedTemporaryFile() as handler:
        handler.write(fetchmailrc.encode("utf8"))
        handler.flush()
        command = FETCHMAIL.format(shlex.quote(handler.name))
        output = subprocess.check_output(command, shell=True)
        return output


def run(debug):
    try:
        os.environ["SMTP_ADDRESS"] = system.get_host_address_from_environment("SMTP", "smtp")
        os.environ["ADMIN_ADDRESS"] = system.get_host_address_from_environment("ADMIN", "admin")
        fetches = requests.get(f"http://{os.environ['ADMIN_ADDRESS']}/internal/fetch").json()
        smtphost, smtpport = extract_host_port(os.environ["SMTP_ADDRESS"], None)
        if smtpport is None:
            smtphostport = smtphost
        else:
            smtphostport = "%s/%d" % (smtphost, smtpport)
        os.environ["LMTP_ADDRESS"] = system.get_host_address_from_environment("LMTP", "imap:2525")
        lmtphost, lmtpport = extract_host_port(os.environ["LMTP_ADDRESS"], None)
        if lmtpport is None:
            lmtphostport = lmtphost
        else:
            lmtphostport = "%s/%d" % (lmtphost, lmtpport)
        for fetch in fetches:
            fetchmailrc = ""
            options = "options antispam 501, 504, 550, 553, 554"
            options += " ssl" if fetch["tls"] else ""
            options += " keep" if fetch["keep"] else " fetchall"
            folders = "folders %s" % ((','.join('"' + item + '"' for item in fetch['folders'])) if fetch['folders'] else '"INBOX"')
            fetchmailrc += RC_LINE.format(
                user_email=escape_rc_string(fetch["user_email"]),
                protocol=fetch["protocol"],
                host=escape_rc_string(fetch["host"]),
                port=fetch["port"],
                smtphost=smtphostport if fetch['scan'] else lmtphostport,
                username=escape_rc_string(fetch["username"]),
                password=escape_rc_string(fetch["password"]),
                options=options,
                folders=folders,
                lmtp='' if fetch['scan'] else 'lmtp',
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
                user_info = "for %s at %s" % (fetch["user_email"], fetch["host"])
                # Number of messages seen is not a error as well
                if ("messages" in error_message and
                        "(seen " in error_message and
                        user_info in error_message):
                    print(error_message)
            finally:
                requests.post("http://" + os.environ["ADMIN_ADDRESS"] + "/internal/fetch/{}".format(fetch["id"]),
                    json=error_message.split("\n")[0]
                )
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    id_fetchmail = getpwnam('fetchmail')
    Path('/data/fetchids').touch()
    os.chown("/data/fetchids", id_fetchmail.pw_uid, id_fetchmail.pw_gid)
    os.chown("/data/", id_fetchmail.pw_uid, id_fetchmail.pw_gid)
    os.chmod("/data/fetchids", 0o700)
    os.setgid(id_fetchmail.pw_gid)
    os.setuid(id_fetchmail.pw_uid)
    while True:
        time.sleep(int(os.environ.get("FETCHMAIL_DELAY", 60)))
        run(os.environ.get("DEBUG", None) == "True")
        sys.stdout.flush()
