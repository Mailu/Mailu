#!/usr/bin/env python3
"""Complete a pending full-text index rebuild after Dovecot is online."""
import json
import os
import shutil
import time
import subprocess
import urllib.request
import urllib.error

from socrate.system import mailbox_shard

MARKER = "/mail/.fts-rebuild-pending"
INDEX_MARKER = "/mail/.index-rebuild-pending"
ADMIN_ADDRESS = os.environ.get("ADMIN_ADDRESS", "admin")


def users():
    url = f"http://{ADMIN_ADDRESS}:8080/internal/dovecot/userdb/?with_uid=1"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"Waiting for Admin userdb at {url} before rebuilding indexes: {error}", flush=True)
            time.sleep(5)


def wait_for_podop():
    socket_path = "/mail/usr/run/podop/podop.socket"
    while not os.path.exists(socket_path):
        print(f"Waiting for Podop quota dictionary at {socket_path}.", flush=True)
        time.sleep(2)


def read_mailbox_queue(path, all_emails):
    """Read a resumable mailbox queue; old marker contents mean all users."""
    path = os.fspath(path)
    try:
        with open(path, encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return set(all_emails)
    if not isinstance(state, dict) or not isinstance(state.get("mailboxes"), list):
        return set(all_emails)
    return {email for email in state["mailboxes"] if isinstance(email, str)}


def write_mailbox_queue(path, emails):
    path = os.fspath(path)
    if not emails:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        return
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as state_file:
        json.dump({"mailboxes": sorted(emails)}, state_file)
        state_file.write("\n")
    os.replace(temporary, path)


def remove_fts_indexes(email):
    localpart, domain = email.rsplit("@", 1)
    mail_path = f"/mail/{domain}/{mailbox_shard(email)}/{localpart}/mail"
    if not os.path.isdir(mail_path):
        return
    for root, dirs, _files in os.walk(mail_path):
        for directory in list(dirs):
            if directory not in {"fts-flatcurve", "xapian-indexes"}:
                continue
            path = os.path.join(root, directory)
            if os.path.islink(path):
                os.unlink(path)
            else:
                shutil.rmtree(path)
            dirs.remove(directory)


if os.path.exists(MARKER) or os.path.exists(INDEX_MARKER):
    # Supervisord starts this after the Dovecot daemon has initialized.
    time.sleep(2)
    print("Rebuilding mailbox indexes. This can take a long time.", flush=True)
    pending_fts = os.path.exists(MARKER)
    pending_indexes = os.path.exists(INDEX_MARKER)
    mailbox_users = users()
    wait_for_podop()
    all_emails = [user["email"] for user in mailbox_users]
    fts_queue = read_mailbox_queue(MARKER, all_emails) if pending_fts else set()
    index_queue = read_mailbox_queue(INDEX_MARKER, all_emails) if pending_indexes else set()
    known_emails = set(all_emails)
    fts_queue.intersection_update(known_emails)
    index_queue.intersection_update(known_emails)
    if pending_fts:
        write_mailbox_queue(MARKER, fts_queue)
    if pending_indexes:
        write_mailbox_queue(INDEX_MARKER, index_queue)
    work = fts_queue | index_queue
    print(f"Rebuilding indexes for {len(work)} mailbox(es).", flush=True)
    work_users = [user for user in mailbox_users if user["email"] in work]
    for index, user in enumerate(work_users, start=1):
        email = user["email"]
        print(f"Indexing mailbox {index}/{len(work_users)}: {email}", flush=True)
        if email in fts_queue:
            print(f"Removing stale full-text index for {email}.", flush=True)
            remove_fts_indexes(email)
            print(f"Rescanning full-text index for {email}.", flush=True)
            subprocess.run(["doveadm", "fts", "rescan", "-u", email], check=True)
        if email in index_queue or email in fts_queue:
            # Index synchronously so the messages just traversed by migration
            # may still be in the OS cache. This also populates virtual sizes.
            subprocess.run(["doveadm", "index", "-u", email, "*"], check=True)
        if email in index_queue:
            print(f"Indexing virtual message sizes for {email}.", flush=True)
            subprocess.run(
                ["doveadm", "mailbox", "status", "-u", email, "vsize", "*"],
                check=True,
            )
            print(f"Recalculating quota for {email}.", flush=True)
            subprocess.run(["doveadm", "quota", "recalc", "-u", email], check=True)
        fts_queue.discard(email)
        index_queue.discard(email)
        if pending_fts:
            write_mailbox_queue(MARKER, fts_queue)
        if pending_indexes:
            write_mailbox_queue(INDEX_MARKER, index_queue)
