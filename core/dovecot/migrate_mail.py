#!/usr/bin/env python3
"""Move legacy Maildirs into per-user homes and normalize Maildir size fields.

The operation is intentionally idempotent: each filesystem operation can be
repeated after a crash, and the completion marker is written only at the end.
"""
import json
import glob
import logging
import os
import shutil
import time
import urllib.request
import urllib.error

from fts_settings import normalize_languages
from socrate.system import mailbox_shard

LOG = logging.getLogger("mail-migration")
MARKER = "/mail/.mail-layout-v1"
FTS_MARKER = "/mail/.fts-rebuild-pending"
INDEX_MARKER = "/mail/.index-rebuild-pending"
FTS_CONFIG = "/mail/.fts-config"
INDEX_FILES = {
    "dovecot.index", "dovecot.index.log", "dovecot.index.log.2",
    "dovecot.index.cache", "dovecot.index.thread", "dovecot.index.backup",
    "dovecot.index.pvt", "dovecot.index.pvt.log",
}
MAILDIR_CONTROL_FILES = {
    "dovecot-uidlist", "dovecot-keywords", "subscriptions",
}
MAILDIR_STATE_FILES = {"dovecot-uidvalidity", "dovecot.mailbox.log", "maildirfolder"}
FTS_INDEX_DIRS = {"xapian-indexes", "fts-flatcurve"}


def fetch_users():
    address = os.environ.get("ADMIN_ADDRESS", "admin")
    url = f"http://{address}:8080/internal/dovecot/userdb/?with_uid=1"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            print(
                f"Waiting for Admin userdb at {url} before migrating mailboxes: {error}",
                flush=True,
            )
            time.sleep(5)


def normalize_message(path):
    physical = line_feeds = carriage_returns = crlf_pairs = 0
    previous_cr = False
    with open(path, "rb") as message:
        while chunk := message.read(1024 * 1024):
            physical += len(chunk)
            line_feeds += chunk.count(b"\n")
            carriage_returns += chunk.count(b"\r")
            crlf_pairs += chunk.count(b"\r\n")
            if previous_cr and chunk.startswith(b"\n"):
                crlf_pairs += 1
            previous_cr = chunk.endswith(b"\r")
    # A lone CR or LF is stored as CRLF by Dovecot; existing CRLF pairs
    # already occupy the final two bytes.
    virtual = physical + line_feeds + carriage_returns - (2 * crlf_pairs)
    name = os.path.basename(path)
    base, sep, flags = name.partition(":2,")
    if not sep:
        base, flags = name, ""
    import re
    base = re.sub(r",S=[0-9]+", "", base)
    base = re.sub(r",W=[0-9]+", "", base)
    new_name = f"{base},S={physical},W={virtual}:2,{flags}"
    if new_name != name:
        target = os.path.join(os.path.dirname(path), new_name)
        if os.path.exists(target):
            raise RuntimeError(f"Refusing to overwrite existing Maildir file: {target}")
        os.replace(path, target)


def move_entry(source, target):
    if not os.path.lexists(source):
        return
    if os.path.lexists(target):
        raise RuntimeError(f"Both legacy and new paths exist: {source} and {target}")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.replace(source, target)


def has_migratable_legacy_data(legacy):
    """Return whether a legacy mailbox directory contains recognized data."""
    try:
        names = os.listdir(legacy)
    except FileNotFoundError:
        return False
    recognized = (
        MAILDIR_CONTROL_FILES
        | MAILDIR_STATE_FILES
        | FTS_INDEX_DIRS
        | INDEX_FILES
        | {
            "sieve", ".dovecot.sieve", "dovecot-attributes", "maildirsize",
            "dovecot.list.index", "dovecot.list.index.log",
        }
    )
    for name in names:
        path = os.path.join(legacy, name)
        if (
            name in recognized
            or name.startswith((".dovecot.sieve.log", "dovecot-uidvalidity."))
            or name.startswith("dovecot.index.")
            or name.startswith("dovecot.list.index.log.")
            or name in {"cur", "new", "tmp"}
            or (
                os.path.isdir(path)
                and {"cur", "new", "tmp"}.issubset(set(os.listdir(path)))
            )
        ):
            return True
    return False


def staged_legacy_mailboxes(mail_root="/mail"):
    """Find recognized flat-layout mailbox imports without querying Admin."""
    staged = {}
    try:
        entries = os.listdir(mail_root)
    except FileNotFoundError:
        return staged
    for email in entries:
        legacy = os.path.join(mail_root, email)
        if "@" not in email or not os.path.isdir(legacy):
            continue
        if has_migratable_legacy_data(legacy):
            staged[email] = legacy
        else:
            LOG.warning("Leaving unrecognized legacy import files in place: %s", legacy)
    return staged


def migrate_active_sieve(source, legacy, home):
    """Move the active-script pointer into the personal Sieve directory."""
    if not os.path.lexists(source):
        return
    sieve = os.path.join(home, "sieve")
    active = os.path.join(sieve, ".active")
    os.makedirs(sieve, mode=0o700, exist_ok=True)
    if os.path.lexists(active):
        raise RuntimeError(f"Both legacy and new active Sieve pointers exist: {source} and {active}")

    if not os.path.islink(source):
        # Some old deployments used ~/.dovecot.sieve as a regular script file.
        script = os.path.join(sieve, "active.sieve")
        move_entry(source, script)
        os.symlink(os.path.basename(script), active)
        return

    target = os.readlink(source)
    legacy_sieve = os.path.join(legacy, "sieve")
    if target.startswith("sieve/"):
        target = target[len("sieve/"):]
    elif os.path.isabs(target) and target.startswith(legacy_sieve + os.sep):
        target = os.path.relpath(target, legacy_sieve)
    elif not os.path.isabs(target):
        old_target = os.path.normpath(os.path.join(legacy, target))
        try:
            target = os.path.relpath(old_target, legacy_sieve)
            if target == ".." or target.startswith(".." + os.sep):
                raise ValueError
        except ValueError:
            # A relative link outside the legacy Sieve directory is unusual;
            # preserve its resolved target if it still exists.
            if not os.path.exists(old_target):
                raise RuntimeError(f"Cannot resolve legacy active Sieve target: {source} -> {target}")
            target = old_target

    new_target = target if os.path.isabs(target) else os.path.join(sieve, target)
    if not os.path.exists(new_target):
        raise RuntimeError(f"Active Sieve script is missing after migration: {source} -> {new_target}")
    link_target = target if os.path.isabs(target) else os.path.relpath(new_target, sieve)
    os.symlink(link_target, active)
    os.unlink(source)


def migrate_user(user):
    email = user["email"]
    local, domain = email.rsplit("@", 1)
    uid = int(user["uid"])
    gid = uid
    legacy = os.path.join("/mail", email)
    home = os.path.join("/mail", domain, mailbox_shard(email), local)
    mail = os.path.join(home, "mail")
    indexes = os.path.join(home, "indexes")
    metadata = os.path.join(home, "metadata")
    LOG.info("Migrating %s: %s -> %s (uid/gid %d)", email, legacy, home, uid)
    if os.path.isdir(legacy):
        names = os.listdir(legacy)
        # Move script storage first so the active pointer can be rewritten
        # relative to its new location.
        if "sieve" in names:
            move_entry(os.path.join(legacy, "sieve"), os.path.join(home, "sieve"))
        for name in names:
            src = os.path.join(legacy, name)
            if name == "sieve":
                continue
            if name == ".dovecot.sieve":
                migrate_active_sieve(src, legacy, home)
            elif name.startswith(".dovecot.sieve.log"):
                move_entry(src, os.path.join(home, "sieve", name))
            elif name == "dovecot-attributes":
                move_entry(src, os.path.join(metadata, name))
            elif name == "maildirsize":
                LOG.info("Discarding obsolete Maildir++ quota cache %s; count quota will be recalculated", src)
                os.unlink(src)
            elif name in MAILDIR_CONTROL_FILES:
                move_entry(src, os.path.join(mail, name))
            elif name in MAILDIR_STATE_FILES or name.startswith("dovecot-uidvalidity."):
                # Keep UIDVALIDITY's authoritative suffix file with its cached
                # value, and keep the mailbox changelog in the Maildir root.
                move_entry(src, os.path.join(mail, name))
            elif name in {"dovecot.list.index", "dovecot.list.index.log"} or name.startswith(
                "dovecot.list.index.log."
            ):
                LOG.info("Discarding rebuildable mailbox-list index %s", src)
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.rmtree(src)
                else:
                    os.unlink(src)
            elif name in FTS_INDEX_DIRS:
                LOG.info("Discarding obsolete full-text index %s", src)
                if os.path.islink(src):
                    os.unlink(src)
                else:
                    shutil.rmtree(src)
            elif name in INDEX_FILES or name.startswith("dovecot.index."):
                LOG.info("Discarding rebuildable index %s", src)
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.rmtree(src)
                else:
                    os.unlink(src)
            elif name in {"cur", "new", "tmp"} or (
                os.path.isdir(src) and {"cur", "new", "tmp"}.issubset(set(os.listdir(src)))
            ):
                move_entry(src, os.path.join(mail, name))
            else:
                LOG.warning("Leaving unrecognized legacy file in place: %s", src)
        try:
            os.rmdir(legacy)
        except OSError:
            pass

    os.makedirs(home, mode=0o700, exist_ok=True)
    os.makedirs(mail, mode=0o700, exist_ok=True)
    os.makedirs(indexes, mode=0o700, exist_ok=True)
    os.makedirs(metadata, mode=0o700, exist_ok=True)

    # Index and FTS artifacts can also live inside mailbox directories.
    for root, dirs, files in os.walk(mail):
        for directory in list(dirs):
            if directory in FTS_INDEX_DIRS:
                path = os.path.join(root, directory)
                LOG.info("Removing rebuildable search index %s", path)
                shutil.rmtree(path)
                dirs.remove(directory)
        for filename in files:
            path = os.path.join(root, filename)
            if filename.startswith("dovecot.index"):
                os.unlink(path)
            elif root.endswith(("/cur", "/new")):
                normalize_message(path)
    sieve = os.path.join(home, "sieve")
    if os.path.isdir(sieve):
        for root, _dirs, files in os.walk(sieve):
            for filename in files:
                if filename.endswith(".svbin"):
                    path = os.path.join(root, filename)
                    LOG.info("Discarding compiled Sieve artifact %s", path)
                    os.unlink(path)
    for root, dirs, files in os.walk(home):
        os.chown(root, uid, gid)
        os.chmod(root, 0o700)
        for filename in files:
            path = os.path.join(root, filename)
            if not os.path.islink(path):
                os.chown(path, uid, gid)
                os.chmod(path, 0o600)
    LOG.info("Completed %s", email)


def remove_fts_indexes(mail_path):
    if not os.path.isdir(mail_path):
        return
    for root, dirs, _files in os.walk(mail_path):
        for directory in list(dirs):
            if directory not in FTS_INDEX_DIRS:
                continue
            path = os.path.join(root, directory)
            LOG.info("Removing stale full-text index %s", path)
            if os.path.islink(path):
                os.unlink(path)
            else:
                shutil.rmtree(path)
            dirs.remove(directory)


def write_mailbox_queue(path, emails):
    emails = sorted(set(emails))
    if not emails:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        return
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as state_file:
        json.dump({"mailboxes": emails}, state_file)
        state_file.write("\n")
    os.replace(temporary, path)


def enqueue_mailboxes(path, emails):
    pending = set(emails)
    try:
        with open(path, encoding="utf-8") as state_file:
            state = json.load(state_file)
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        # An older plain marker means a full rebuild. Keep it full without
        # making Admin availability a prerequisite for Dovecot startup.
        return
    else:
        if not isinstance(state, dict) or not isinstance(state.get("mailboxes"), list):
            return
        pending.update(email for email in state["mailboxes"] if isinstance(email, str))
    write_mailbox_queue(path, pending)


def update_fts_indexes(force_rebuild=False, mailbox_emails=None):
    config = normalize_languages(os.environ.get("FULL_TEXT_SEARCH", "en"))
    try:
        with open(FTS_CONFIG, encoding="utf-8") as state_file:
            previous = state_file.read().strip()
    except FileNotFoundError:
        previous = None

    if config == "off":
        if previous != "off":
            LOG.info("Full-text search is disabled; removing stored FTS indexes. This may take a long time.")
            for mail_path in glob.glob("/mail/*/*/*/mail"):
                remove_fts_indexes(mail_path)
        try:
            os.unlink(FTS_MARKER)
        except FileNotFoundError:
            pass
    elif previous != config:
        LOG.warning(
            "Full-text search configuration changed (%s -> %s). Rebuilding indexes mailbox by mailbox; "
            "this can take a long time.", previous or "unset", config,
        )
        with open(FTS_MARKER, "w", encoding="ascii") as marker:
            marker.write("pending\n")
    elif force_rebuild:
        emails = mailbox_emails or [user["email"] for user in fetch_users()]
        LOG.warning(
            "Rebuilding full-text indexes for %d migrated mailbox(es); this can take a long time.",
            len(emails),
        )
        enqueue_mailboxes(FTS_MARKER, emails)
    elif os.path.exists(FTS_MARKER):
        LOG.warning("Resuming the pending mailbox-by-mailbox full-text index rebuild.")

    temporary = FTS_CONFIG + ".tmp"
    with open(temporary, "w", encoding="utf-8") as state_file:
        state_file.write(config + "\n")
    os.replace(temporary, FTS_CONFIG)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    layout_migrated = not os.path.exists(MARKER)
    if layout_migrated:
        users = fetch_users()
        LOG.warning("Migrating mailbox storage and rebuilding indexes; this can take a long time.")
        for user in users:
            migrate_user(user)
        os.makedirs(os.path.dirname(MARKER), exist_ok=True)
        write_mailbox_queue(INDEX_MARKER, [user["email"] for user in users])
        update_fts_indexes(force_rebuild=True, mailbox_emails=[user["email"] for user in users])
        with open(MARKER, "w", encoding="ascii") as marker:
            marker.write("complete\n")
        LOG.info("Mail storage migration complete")
    else:
        staged_paths = staged_legacy_mailboxes()
        staged = []
        if staged_paths:
            users_by_email = {user["email"]: user for user in fetch_users()}
            for email in staged_paths:
                user = users_by_email.get(email)
                if user is None:
                    LOG.warning("No mailbox account exists for staged import %s; leaving it in place", email)
                else:
                    staged.append(user)
        if staged:
            LOG.warning(
                "Migrating %d externally staged mailbox(es) and rebuilding indexes; "
                "this can take a long time.",
                len(staged),
            )
            enqueue_mailboxes(INDEX_MARKER, [user["email"] for user in staged])
            # Record pending FTS work before moving data so a restart can
            # resume indexing even if migration is interrupted after the
            # legacy source has been emptied.
            update_fts_indexes(force_rebuild=True, mailbox_emails=[user["email"] for user in staged])
            for user in staged:
                migrate_user(user)
            LOG.info("External mailbox import complete")
        else:
            update_fts_indexes()


if __name__ == "__main__":
    main()
