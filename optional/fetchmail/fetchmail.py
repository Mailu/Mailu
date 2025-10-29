#!/usr/bin/env python3

import binascii
import time
import os
from pathlib import Path
from pwd import getpwnam
import tempfile
import shlex
import subprocess
import requests
from socrate import system
import sys
import traceback
from multiprocessing import Process


FETCHMAIL = """
fetchmail -N \
    --idfile /data/fetchids{} --uidl \
    --pidfile /dev/shm/fetchmail{}.pid \
    --sslcertck --sslcertpath /etc/ssl/certs \
    {} -f {}
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

def imaputf7encode(s):
    """Encode a string into RFC2060 aka IMAP UTF7"""
    out = ''
    enc = ''
    for c in s.replace('&','&-') + 'X':
        if '\x20' <= c <= '\x7f':
            if enc:
                out += f'&{binascii.b2a_base64(enc.encode("utf-16-be")).rstrip(b"\n=").replace(b"/", b",").decode("ascii")}-'
                enc = ''
            out += c
        else:
            enc += c
    return out[:-1]

def escape_rc_string(arg):
    return "".join("\\x%2x" % ord(char) for char in arg)


def fetchmail(fetchmailrc, fetch_instance_name):
    with tempfile.NamedTemporaryFile() as handler:
        handler.write(fetchmailrc.encode("utf8"))
        handler.flush()
        fetchmail_custom_options = os.environ.get("FETCHMAIL_OPTIONS", "")
        print(FETCHMAIL.format(fetch_instance_name, fetch_instance_name, fetchmail_custom_options, ""))
        command = FETCHMAIL.format(fetch_instance_name, fetch_instance_name, fetchmail_custom_options, shlex.quote(handler.name))
        output = subprocess.check_output(command, shell=True)
        return output


def worker(debug, fetch, fetch_instance_name):
    fetchmailrc = ""
    options = "options antispam 501, 504, 550, 553, 554"
    if "FETCHMAIL_POLL_OPTIONS" in os.environ: options += f' {os.environ["FETCHMAIL_POLL_OPTIONS"]}'
    options += " ssl" if fetch["tls"] else " sslproto \'\'"
    options += " keep" if fetch["keep"] else " fetchall"
    folders = f"folders {",".join(f'"{imaputf7encode(item).replace('"',r"\34")}"' for item in fetch["folders"]) or '"INBOX"'}"
    fetchmailrc += RC_LINE.format(
        user_email=escape_rc_string(fetch["user_email"]),
        protocol=fetch["protocol"],
        host=escape_rc_string(fetch["host"]),
        port=fetch["port"],
        smtphost=f'{os.environ["HOSTNAMES"].split(",")[0]}' if fetch['scan'] and os.environ.get('PROXY_PROTOCOL_25', False) else f'{os.environ["FRONT_ADDRESS"]}' if fetch['scan'] else f'{os.environ["FRONT_ADDRESS"]}/2525',
        username=escape_rc_string(fetch["username"]),
        password=escape_rc_string(fetch["password"]),
        options=options,
        folders='' if fetch['protocol'] == 'pop3' else folders,
        lmtp='' if fetch['scan'] else 'lmtp',
    )
    if debug:
        print(fetchmailrc)
    try:
        print(fetchmail(fetchmailrc, fetch_instance_name))
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
        requests.post("http://{}:8080/internal/fetch/{}".format(os.environ['ADMIN_ADDRESS'],fetch['id']),
            json=error_message.split('\n')[0]
        )


def run(debug):
    try:
        fetches = requests.get(f"http://{os.environ['ADMIN_ADDRESS']}:8080/internal/fetch").json()
        for fetch in fetches:
            id_fetchmail = getpwnam('fetchmail')
            fetch_instance_name = "%s" % (fetch["user_email"])
            fetchids_path = "/data/fetchids" + fetch_instance_name
            Path(fetchids_path).touch()
            os.chown(fetchids_path, id_fetchmail.pw_uid, id_fetchmail.pw_gid)
            os.chown("/data/", id_fetchmail.pw_uid, id_fetchmail.pw_gid)
            os.chmod(fetchids_path, 0o700)
            # system.drop_privs_to('fetchmail') not sure why this does not work: "no permission"
            # instead:
            pwnam = getpwnam('fetchmail')
            os.setgroups([])
            os.setgid(pwnam.pw_gid)
            os.setuid(pwnam.pw_uid)
            os.environ['HOME'] = pwnam.pw_dir

            print("Starting worker for user: ")
            print(fetch_instance_name)
            p = Process(target=worker, args=(debug,fetch,fetch_instance_name,))
            p.start()

    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    config = system.set_env()
    while True:
        delay = int(os.environ.get('FETCHMAIL_DELAY', 60))
        print("Sleeping for {} seconds".format(delay))
        time.sleep(delay)

        if not config.get('FETCHMAIL_ENABLED', True):
            print("Fetchmail disabled, skipping...")
            continue

        run(config.get('DEBUG', False))
        sys.stdout.flush()
