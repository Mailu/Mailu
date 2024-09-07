#!/usr/bin/env python3

import base64
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

def imaputf7encode(s):
    """"Encode a string into RFC2060 aka IMAP UTF7"""
    s=s.replace('&','&-')
    iters=iter(s)
    unipart=out=''
    for c in s:
        if 0x20<=ord(c)<=0x7f :
            if unipart!='' :
                out+='&'+base64.b64encode(unipart.encode('utf-16-be')).decode('ascii').rstrip('=')+'-'
                unipart=''
            out+=c
        else : unipart+=c
    if unipart!='' :
        out+='&'+base64.b64encode(unipart.encode('utf-16-be')).decode('ascii').rstrip('=')+'-'
    return out

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
        fetches = requests.get(f"http://{os.environ['ADMIN_ADDRESS']}:8080/internal/fetch").json()
        for fetch in fetches:
            fetchmailrc = ""
            options = "options antispam 501, 504, 550, 553, 554"
            options += " ssl" if fetch["tls"] else ""
            options += " keep" if fetch["keep"] else " fetchall"
            folders = "folders %s" % ((','.join('"' + imaputf7encode(item) + '"' for item in fetch['folders'])) if fetch['folders'] else '"INBOX"')
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
                requests.post("http://{}:8080/internal/fetch/{}".format(os.environ['ADMIN_ADDRESS'],fetch['id']),
                    json=error_message.split('\n')[0]
                )
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    id_fetchmail = getpwnam('fetchmail')
    Path('/data/fetchids').touch()
    os.chown("/data/fetchids", id_fetchmail.pw_uid, id_fetchmail.pw_gid)
    os.chown("/data/", id_fetchmail.pw_uid, id_fetchmail.pw_gid)
    os.chmod("/data/fetchids", 0o700)
    system.drop_privs_to('fetchmail')
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
