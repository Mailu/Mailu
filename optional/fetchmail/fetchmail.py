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
import re
import pathlib


FETCHMAIL = """
fetchmail -N \
    --idfile {}/fetchids --uidl \
    --pidfile {}/fetchmail.pid \
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


def fetchmail(fetchmailrc, fetchmailhome):
    with tempfile.NamedTemporaryFile() as handler:
        handler.write(fetchmailrc.encode("utf8"))
        handler.flush()
        fetchmail_custom_options = os.environ.get("FETCHMAIL_OPTIONS", "")
        print(FETCHMAIL.format(fetchmailhome, fetchmailhome, fetchmail_custom_options, ""))
        command = FETCHMAIL.format(fetchmailhome, fetchmailhome, fetchmail_custom_options, shlex.quote(handler.name))
        output = subprocess.check_output(command, shell=True)
        return output


def worker(debug, fetch, fetchmailhome):
    id_fetchmail = getpwnam('fetchmail')
    print('{} Setting $FETCHMAILHOME to {}'.format(time.strftime("%b %d %H:%M:%S"), fetchmailhome))
    os.environ["FETCHMAILHOME"] = fetchmailhome
    fetchids_path = fetchmailhome + "/fetchids"
    if not os.path.exists(fetchmailhome):
        os.makedirs(fetchmailhome)
    Path(fetchids_path).touch()
    os.chown(fetchids_path, id_fetchmail.pw_uid, id_fetchmail.pw_gid)
    os.chown(fetchmailhome, id_fetchmail.pw_uid, id_fetchmail.pw_gid)
    os.chown("/data/", id_fetchmail.pw_uid, id_fetchmail.pw_gid)
    os.chmod(fetchids_path, 0o700)
    system.drop_privs_to('fetchmail')

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
        print(fetchmail(fetchmailrc, fetchmailhome))
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
        processes = []
        for fetch in fetches:
            # Defining instance name with username and host to trigger an error if same mailbox is fetched for multiple users
            fetch_instance_name = "%s" % (fetch["username"] + "_" + fetch["host"])
            fetchmailhome = "/data/" + re.sub(r'[^a-zA-Z0-9\s]', '', fetch_instance_name)
            # Start worker for fetch if no other worker is already running on this (can recover/restart failed workers in idle mode or avoids conflicts if FETCHMAIL_DELAY is too short and previous non-idle process still runs)
            if not os.path.exists(fetchmailhome + "/fetchmail.pid"):
                print('{} Starting worker for mailbox: {}'.format(time.strftime("%b %d %H:%M:%S"), fetch_instance_name))
                p = Process(target=worker, args=(debug,fetch,fetchmailhome,))
                p.start()
                processes.append(p)

    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    config = system.set_env()
    # Remove any stale lockfiles in /data
    lockfiles = pathlib.Path("/data")
    for item in lockfiles.rglob("fetchmail.pid"):
        os.remove(item)
    # Give other containers some time to start before starting fetchmail
    time.sleep(20)
    while True:

        if not config.get('FETCHMAIL_ENABLED', True):
            print("Fetchmail disabled, skipping...")
            continue

        run(config.get('DEBUG', False))
        sys.stdout.flush()

        delay = int(os.environ.get('FETCHMAIL_DELAY', 60))
        print("Sleeping for {} seconds".format(delay))
        time.sleep(delay)
