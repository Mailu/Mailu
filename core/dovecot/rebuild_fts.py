#!/usr/bin/env python3
"""Complete a pending full-text index rebuild after Dovecot is online."""
import json
import os
import re
import shutil
import time
import subprocess
import urllib.request
import urllib.error

from socrate.system import mailbox_shard

MARKER = "/mail/.fts-rebuild-pending"
INDEX_MARKER = "/mail/.index-rebuild-pending"
FTS_PREPARED_MARKER = "/mail/.fts-rebuild-prepared"
ADMIN_ADDRESS = os.environ.get("ADMIN_ADDRESS", "admin")
REPORT_INTERVAL = 30
STARTED = time.monotonic()


def log(message):
    elapsed = int(time.monotonic() - STARTED)
    print(f"[index-rebuild +{elapsed}s] {message}", flush=True)


def users():
    url = f"http://{ADMIN_ADDRESS}:8080/internal/dovecot/userdb/?with_uid=1"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            log(f"Waiting for Admin userdb at {url} before rebuilding indexes: {error}")
            time.sleep(5)


def wait_for_podop():
    socket_path = "/mail/usr/run/podop/podop.socket"
    while not os.path.exists(socket_path):
        log(f"Waiting for Podop quota dictionary at {socket_path}.")
        time.sleep(2)


def read_mailbox_queue(path, all_emails, default_all=True):
    """Read a resumable mailbox queue; old marker contents mean all users."""
    path = os.fspath(path)
    try:
        with open(path, encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return set(all_emails) if default_all else set()
    if not isinstance(state, dict) or not isinstance(state.get("mailboxes"), list):
        return set(all_emails) if default_all else set()
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


def index_mailbox(email, mailbox):
    """Queue one mailbox for Dovecot's indexer workers."""
    command = ["doveadm", "index", "-q", "-u", email, mailbox]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stdout:
            log(result.stdout.strip())
        if result.stderr:
            log(result.stderr.strip())
        raise subprocess.CalledProcessError(result.returncode, command)


def pending_index_requests(emails):
    """Return queued or active indexer requests for the given mailboxes."""
    result = subprocess.run(
        ["doveadm", "-f", "json", "indexer", "list", "*"],
        check=True,
        capture_output=True,
        text=True,
    )
    requests = json.loads(result.stdout or "[]")
    return [request for request in requests if request.get("username") in emails]


def fts_watermark(email, mailbox):
    """Return the indexed UID and message count for one mailbox, if available."""
    fts = subprocess.run(
        ["doveadm", "fts", "flatcurve", "stats", "-u", email, mailbox],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if fts.returncode != 0 or not fts.stdout.strip():
        return None
    line = fts.stdout.strip().splitlines()[-1]
    last_uid = re.search(r"\blast_uid=(\d+)", line)
    messages = re.search(r"\bmessages=(\d+)", line)
    if not last_uid or not messages:
        return None
    return int(last_uid.group(1)), int(messages.group(1)), line


def mailbox_progress(email, mailbox):
    """Return a compact FTS and mailbox watermark for progress reports."""
    fts = fts_watermark(email, mailbox)
    status = subprocess.run(
        ["doveadm", "mailbox", "status", "-u", email, "messages uidnext", mailbox],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    fts_line = fts[2] if fts else "FTS stats unavailable"
    status_line = status.stdout.strip().splitlines()[-1] if status.returncode == 0 and status.stdout.strip() else "mailbox status unavailable"
    return f"{fts_line}; {status_line}"


def mailboxes_for_user(email):
    result = subprocess.run(
        ["doveadm", "mailbox", "list", "-u", email],
        check=True,
        capture_output=True,
        text=True,
    )
    return [name for name in result.stdout.splitlines() if name]


def indexing_progress_snapshot(requests):
    """Capture FTS watermarks for requests, expanding wildcard mailboxes."""
    targets = set()
    for email, mailbox in requests:
        if mailbox == "*":
            targets.update((email, name) for name in mailboxes_for_user(email))
        else:
            targets.add((email, mailbox))
    return {target: fts_watermark(*target) for target in targets}


def indexing_errors(emails):
    """Read recent per-message indexing failures for progress reporting."""
    result = subprocess.run(
        ["doveadm", "log", "errors"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return set()
    return {
        line.strip()
        for line in result.stdout.splitlines()
        if any(email in line for email in emails)
        and ("fts_tika" in line or "Precache for UID=" in line)
    }


def wait_for_indexing(emails, phase, queued_count, seen_errors):
    """Wait for Dovecot's asynchronous index queue and report live progress."""
    started = time.monotonic()
    last_report = started - REPORT_INTERVAL
    seen_errors = set(seen_errors)
    failed_mailboxes = set()
    while True:
        pending = pending_index_requests(emails)
        now = time.monotonic()
        if not pending or now - last_report >= REPORT_INTERVAL:
            new_errors = indexing_errors(emails) - seen_errors
            for error in sorted(new_errors):
                log(f"Dovecot reported a per-message indexing failure: {error}")
                match = re.search(r"Mailbox (.*?): Precache for UID=", error)
                if match:
                    email = next((address for address in emails if address in error), None)
                    if email:
                        failed_mailboxes.add((email, match.group(1)))
            seen_errors.update(new_errors)

        if not pending:
            elapsed = int(time.monotonic() - started)
            log(f"{phase} complete: {queued_count} request(s) drained in {elapsed}s.")
            return failed_mailboxes

        if now - last_report >= REPORT_INTERVAL:
            working = sum("working" in request.get("status", "") for request in pending)
            queued = len(pending) - working
            current = ", ".join(
                f"{request.get('username')}:{request.get('mailbox')} ({request.get('status')}; "
                f"{mailbox_progress(request.get('username'), request.get('mailbox'))})"
                for request in pending[:3]
            )
            if len(pending) > 3:
                current += f", and {len(pending) - 3} more"
            elapsed = int(now - started)
            log(
                f"{phase} progress: {len(pending)} request(s) remain for "
                f"{queued_count} target mailbox(es); "
                f"{working} working, {queued} queued; elapsed {elapsed}s; {current}"
            )
            last_report = now
        time.sleep(5)


def queue_indexing(emails, mailbox, phase):
    """Queue mailbox indexing and retry mailboxes Dovecot reports as failed."""
    pending = {(email, mailbox) for email in emails}
    unresolved = set()
    attempt = 0
    while pending:
        attempt += 1
        log(
            f"{phase}: queuing {len(pending)} mailbox request(s), "
            f"attempt {attempt}."
        )
        before = indexing_progress_snapshot(pending)
        baseline_errors = indexing_errors({email for email, _mailbox_name in pending})
        for email, mailbox_name in sorted(pending):
            index_mailbox(email, mailbox_name)
        failed = wait_for_indexing(
            {email for email, _mailbox_name in pending},
            phase,
            len(pending),
            baseline_errors,
        )
        pending = set()
        for target in sorted(failed):
            old = before.get(target)
            current = fts_watermark(*target)
            progressed = current is not None and (
                old is None or current[:2] != old[:2]
            )
            if progressed:
                old_uid = old[0] if old else 0
                old_messages = old[1] if old else 0
                log(
                    f"Retrying {target[0]}:{target[1]} after FTS progress: "
                    f"UID {old_uid}->{current[0]}, messages {old_messages}->{current[1]}."
                )
                pending.add(target)
            else:
                log(
                    f"No FTS progress for {target[0]}:{target[1]} on this attempt; "
                    "leaving it checkpointed for a later resume."
                )
                unresolved.add(target)
    if unresolved:
        details = ", ".join(f"{email}:{mailbox_name}" for email, mailbox_name in sorted(unresolved))
        log(
            f"Warning: indexing stopped retrying mailboxes with no further FTS progress "
            f"({details}); the checkpoint will remain for a later resume."
        )
    return {email for email, _mailbox_name in unresolved}


def mailbox_message_count(email):
    result = subprocess.run(
        ["doveadm", "mailbox", "status", "-t", "-u", email, "messages", "*"],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip().split("=", 1)[1])


if os.path.exists(MARKER) or os.path.exists(INDEX_MARKER):
    # Supervisord starts this after the Dovecot daemon has initialized.
    time.sleep(2)
    log("Rebuilding mailbox indexes. This can take a long time; progress will be reported while Dovecot works.")
    pending_fts = os.path.exists(MARKER)
    pending_indexes = os.path.exists(INDEX_MARKER)
    mailbox_users = users()
    wait_for_podop()
    all_emails = [user["email"] for user in mailbox_users]
    fts_queue = read_mailbox_queue(MARKER, all_emails) if pending_fts else set()
    index_queue = read_mailbox_queue(INDEX_MARKER, all_emails) if pending_indexes else set()
    fts_prepared = read_mailbox_queue(
        FTS_PREPARED_MARKER, all_emails, default_all=False
    ) if os.path.exists(FTS_PREPARED_MARKER) else set()
    known_emails = set(all_emails)
    fts_queue.intersection_update(known_emails)
    index_queue.intersection_update(known_emails)
    fts_prepared.intersection_update(known_emails)
    if pending_fts:
        write_mailbox_queue(MARKER, fts_queue)
    if pending_indexes:
        write_mailbox_queue(INDEX_MARKER, index_queue)
    if os.path.exists(FTS_PREPARED_MARKER):
        if pending_fts:
            write_mailbox_queue(FTS_PREPARED_MARKER, fts_prepared)
        else:
            os.unlink(FTS_PREPARED_MARKER)
            fts_prepared.clear()
    work = fts_queue | index_queue
    log(f"Rebuilding indexes for {len(work)} mailbox(es). This may take hours for large mailboxes.")
    work_users = [user for user in mailbox_users if user["email"] in work]
    message_counts = {
        user["email"]: mailbox_message_count(user["email"])
        for user in work_users
    }
    work_users.sort(key=lambda user: message_counts[user["email"]])
    for index, user in enumerate(work_users, start=1):
        email = user["email"]
        log(
            f"Indexing mailbox {index}/{len(work_users)}: {email} "
            f"({message_counts[email]} messages)",
        )
        if email in fts_queue and email not in fts_prepared:
            log(f"Removing stale full-text index for {email}; this mailbox will be rescanned.")
            remove_fts_indexes(email)
            fts_prepared.add(email)
            write_mailbox_queue(FTS_PREPARED_MARKER, fts_prepared)
            log(f"Rescanning full-text index for {email}.")
            subprocess.run(["doveadm", "fts", "rescan", "-u", email], check=True)
    index_emails = {user["email"] for user in work_users if user["email"] in index_queue or user["email"] in fts_queue}
    failed_emails = set()
    if index_emails:
        failed_emails.update(
            queue_indexing(index_emails, "INBOX", "INBOX indexing")
        )
        failed_emails.update(
            queue_indexing(index_emails, "*", "Remaining mailbox indexing")
        )

    for index, user in enumerate(work_users, start=1):
        email = user["email"]
        if email in index_queue:
            log(f"Indexing virtual message sizes for {email}.")
            subprocess.run(
                ["doveadm", "mailbox", "status", "-u", email, "vsize", "*"],
                check=True,
            )
            log(f"Recalculating quota for {email}.")
            subprocess.run(["doveadm", "quota", "recalc", "-u", email], check=True)
        if email not in failed_emails:
            fts_queue.discard(email)
            index_queue.discard(email)
        if pending_fts:
            write_mailbox_queue(MARKER, fts_queue)
        if pending_indexes:
            write_mailbox_queue(INDEX_MARKER, index_queue)
        if pending_fts and email not in failed_emails:
            fts_prepared.discard(email)
            write_mailbox_queue(FTS_PREPARED_MARKER, fts_prepared)
        if email in failed_emails:
            log(f"Mailbox {index}/{len(work_users)} remains checkpointed after indexing failures: {email}.")
        else:
            log(f"Completed mailbox {index}/{len(work_users)}: {email}.")
    log(f"Mailbox index rebuild finished in {int(time.monotonic() - STARTED)}s.")
