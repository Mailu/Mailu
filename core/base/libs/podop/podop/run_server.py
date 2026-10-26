"""Run a Mailu Podop server as a supervisord-managed process."""

import os
import sys

from socrate import system
from podop import run_server


SERVERS = {
    "dovecot": (
        "mail", "dovecot", "/tmp/podop.socket", "dovecot",
        [("quota", "url", "http://{ADMIN_ADDRESS}:8080/internal/dovecot/§"),
         ("sieve", "url", "http://{ADMIN_ADDRESS}:8080/internal/dovecot/§")],
    ),
    "postfix": (
        "postfix", "postfix", ("/tmp/podop.socket", "/queue/private/podop.socket"), "postfix",
        [(name, "url", "http://{ADMIN_ADDRESS}:8080/internal/postfix/" + path)
         for name, path in (
             ("transport", "transport/§"), ("alias", "alias/§"),
             ("dane", "dane/§"), ("domain", "domain/§"),
             ("mailbox", "mailbox/§"), ("recipientmap", "recipient/map/§"),
             ("sendermap", "sender/map/§"), ("senderlogin", "sender/login/§"),
             ("senderrate", "sender/rate/§"),
         )],
    ),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SERVERS:
        raise SystemExit("usage: python -m podop.run_server {dovecot|postfix}")
    username, name, socket_path, privilege, endpoints = SERVERS[sys.argv[1]]
    system.drop_privs_to(username)
    if privilege == "postfix":
        os.makedirs("/dev/shm/postfix", mode=0o700, exist_ok=True)
    socket_paths = socket_path if isinstance(socket_path, (tuple, list)) else (socket_path,)
    for path in socket_paths:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    admin = os.environ["ADMIN_ADDRESS"]
    run_server(0, name, socket_path, [
        (key, kind, url.format(ADMIN_ADDRESS=admin)) for key, kind, url in endpoints
    ])


if __name__ == "__main__":
    main()
