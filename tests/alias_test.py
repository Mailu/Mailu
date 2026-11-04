import smtplib
import sys
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import policy
from email.parser import BytesParser
from mail_utils import clear_inbox, connect_imap, wait_for_message

alias = "alltheusers@mailu.io"
marker = f"Alias Text {uuid.uuid4()}"

msg = MIMEMultipart()
msg['From'] = "sender@outside.invalid"
msg['To'] = alias
msg['Subject'] = f"Alias Test {marker}"
msg['X-Original-To'] = "forged@evil.invalid"
msg['Received'] = (
    "from attacker1.invalid by localhost (Postfix) with ESMTP id FORGED1 "
    "for <forged1@evil.invalid>; Tue, 4 Nov 2026 12:00:00 +0000"
)
msg['Received'] = (
    "from attacker2.invalid by localhost (Postfix) with ESMTP id FORGED2 "
    "for <forged2@evil.invalid>; Tue, 4 Nov 2026 12:00:01 +0000"
)
msg.attach(MIMEText(marker, 'plain'))

try:
    smtp_server = smtplib.SMTP('localhost', 25)
    smtp_server.set_debuglevel(1)
    smtp_server.sendmail("sender@outside.invalid", alias, msg.as_string())
    smtp_server.quit()
except:
    sys.exit(25)

for user in ['user@mailu.io', 'admin@mailu.io', 'user/with/slash@mailu.io']:
    try:
        imap_server = connect_imap(user, 'password')
    except Exception as exc:
        print("Failed with:", exc)
        sys.exit(110)

    if wait_for_message(imap_server, marker):
        print("Success: Mail is in aliassed inbox", user)
    else:
        print("Failed receiving email in aliassed inbox", user)
        sys.exit(99)

    status, message_ids = imap_server.search(None, 'ALL')
    if status != 'OK':
        raise AssertionError(f"Could not search inbox for {user}")
    delivered = None
    for message_id in reversed(message_ids[0].split()):
        status, response = imap_server.fetch(message_id, '(BODY.PEEK[])')
        if status == 'OK':
            raw_message = next(
                (item[1] for item in response if isinstance(item, tuple)), None
            )
            if raw_message is not None:
                candidate = BytesParser(policy=policy.default).parsebytes(raw_message)
                if candidate['Subject'] == f"Alias Test {marker}":
                    delivered = candidate
                    break
    if delivered is None:
        raise AssertionError(f"Could not find test message in {user}'s inbox")

    delivered_to = delivered.get_all('Delivered-To', [])
    if delivered_to != [f"<{alias}>"]:
        raise AssertionError(f"Expected Delivered-To <{alias}> in {user}, got {delivered_to}")

    original_to = delivered.get_all('X-Original-To', [])
    if original_to != [alias, "forged@evil.invalid"]:
        raise AssertionError(
            f"Expected trusted X-Original-To first in {user}, got {original_to}"
        )

    received = delivered.get_all('Received', [])
    if len(received) != 3:
        raise AssertionError(
            f"Expected one local and two sender-supplied Received headers in {user}, "
            f"got {len(received)}"
        )
    local_received = [
        value for value in received
        if "by localhost (Postfix) with ESMTP id" in value
        and f"for <{alias}>" in value
    ]
    if len(local_received) != 1:
        raise AssertionError(f"Expected one Postfix Received for {alias}, got {local_received}")
    for marker_id, attacker, recipient in (
        ("FORGED1", "attacker1", "forged1"),
        ("FORGED2", "attacker2", "forged2"),
    ):
        expected = (
            f"from {attacker}.invalid by localhost (Postfix) with ESMTP id {marker_id} "
            f"for <{recipient}@evil.invalid>"
        )
        if not any(value.startswith(expected) for value in received):
            raise AssertionError(
                f"Sender-supplied Received {marker_id} was changed or lost in {user}"
            )

    clear_inbox(imap_server)
