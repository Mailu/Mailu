#!/usr/bin/env python3

import base64
import imaplib
import smtplib
import ssl
import subprocess
import sys
import uuid
from email import policy
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import mail_utils


SERVER = "localhost"
DOMAIN = "mailu.io"
EAI_LOCALPART = "\u6d4b\u8bd52"
EAI_USER = f"{EAI_LOCALPART}@{DOMAIN}"
EAI_PASSWORD = "password"
COMPOSE_FILE = "tests/compose/core/docker-compose.yml"
TLS_CONTEXT = ssl._create_unverified_context()


def create_eai_user():
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "exec",
            "-T",
            "admin",
            "flask",
            "mailu",
            "user",
            EAI_LOCALPART,
            DOMAIN,
            EAI_PASSWORD,
        ],
        check=True,
    )


def connect_smtp(port, expect_smtputf8):
    if port == 465:
        connection = smtplib.SMTP_SSL(
            SERVER, port, timeout=10, context=TLS_CONTEXT
        )
    else:
        connection = smtplib.SMTP(SERVER, port, timeout=10)
        connection.ehlo()
        connection.starttls(context=TLS_CONTEXT)
    connection.ehlo()
    has_smtputf8 = connection.has_extn("smtputf8")
    if has_smtputf8 != expect_smtputf8:
        connection.quit()
        expectation = "advertised" if expect_smtputf8 else "not advertised"
        raise AssertionError(f"SMTPUTF8 should be {expectation} on port {port}")
    return connection


def authenticate_plain(connection, username, password):
    credentials = f"\0{username}\0{password}".encode("utf-8")
    encoded = base64.b64encode(credentials).decode("ascii")
    code, response = connection.docmd("AUTH", f"PLAIN {encoded}")
    if code != 235:
        raise AssertionError(
            f"SMTP authentication failed for {username}: {code} {response!r}"
        )


def connect_imap(username, password):
    connection = imaplib.IMAP4_SSL(SERVER, timeout=10)
    credentials = lambda _: f"\0{username}\0{password}".encode("utf-8")
    connection.authenticate("PLAIN", credentials)
    return connection


def message(sender, recipient, marker):
    email = EmailMessage(policy=policy.SMTPUTF8)
    email["From"] = sender
    email["To"] = recipient
    email["Subject"] = "SMTPUTF8 integration test"
    email.set_content(marker)
    return email


def send(connection, sender, recipient, marker):
    email = message(sender, recipient, marker)
    connection.sendmail(
        sender,
        [recipient],
        email.as_bytes(),
        mail_options=["SMTPUTF8"],
    )


def assert_received(username, password, marker):
    connection = connect_imap(username, password)
    try:
        if not mail_utils.wait_for_message(connection, marker):
            raise AssertionError(f"Message {marker!r} was not delivered to {username}")
        mail_utils.clear_inbox(connection)
    except Exception:
        try:
            connection.logout()
        except Exception:
            pass
        raise


def main():
    create_eai_user()

    with connect_smtp(25, expect_smtputf8=True):
        pass
    for port in (465, 587):
        with connect_smtp(port, expect_smtputf8=False):
            pass

    inbound_marker = f"smtputf8-inbound-{uuid.uuid4()}"
    with connect_smtp(25, expect_smtputf8=True) as connection:
        send(connection, "\u5916\u90e8@example.net", EAI_USER, inbound_marker)
    assert_received(EAI_USER, EAI_PASSWORD, inbound_marker)

    with connect_smtp(587, expect_smtputf8=False) as connection:
        authenticate_plain(connection, EAI_USER, EAI_PASSWORD)

    print("SMTPUTF8 capability, EAI authentication, delivery and retrieval succeeded")


if __name__ == "__main__":
    main()
