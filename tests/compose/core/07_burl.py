#!/usr/bin/env python3

import imaplib
import re
import smtplib
import ssl
import sys
import uuid
from urllib.parse import quote
from email.message import EmailMessage
from email import policy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mail_utils import connect_imap, wait_for_message


SERVER = 'localhost'
SENDER = 'user@mailu.io'
RECIPIENT = 'admin@mailu.io'
PASSWORD = 'password'
TLS_CONTEXT = ssl._create_unverified_context()


def test_imap_metadata_is_available_and_generates_a_urlauth_url():
    with imaplib.IMAP4_SSL(SERVER, timeout=10, ssl_context=TLS_CONTEXT) as imap:
        imap.login(SENDER, PASSWORD)
        status, capabilities = imap.capability()
        assert status == 'OK'
        advertised = set(capabilities[0].decode('ascii').upper().split())
        assert 'METADATA' in advertised
        assert 'URLAUTH' in advertised, advertised

        token = uuid.uuid4().hex
        message = EmailMessage(policy=policy.SMTP)
        message['From'] = SENDER
        message['To'] = RECIPIENT
        message['Subject'] = f'BURL integration test {token}'
        message.set_content(f'BURL body {token}')
        status, _ = imap.append('INBOX', None, None, message.as_bytes())
        assert status == 'OK'
        status, _ = imap.select('INBOX')
        assert status == 'OK'

        status, data = imap.uid('SEARCH', None, 'ALL')
        assert status == 'OK'
        uid = data[0].split()[-1].decode('ascii')
        encoded_user = quote(SENDER, safe='')
        imap_url = (
            f'imap://{encoded_user}@{SERVER}/INBOX/;UID={uid}'
            f';URLAUTH=submit+{encoded_user}'
        )
        imaplib.Commands['GENURLAUTH'] = ('AUTH', 'SELECTED')
        status, data = imap._simple_command('GENURLAUTH', imap_url, 'INTERNAL')
        assert status == 'OK', data
        _, data = imap._untagged_response(status, data, 'GENURLAUTH')
        response = b' '.join(item if isinstance(item, bytes) else str(item).encode() for item in data)
        match = re.search(rb'imap://[^\s")]+;URLAUTH=submit\+[^:]+:INTERNAL:[0-9a-f]+', response, re.IGNORECASE)
        assert match, response
        return token, match.group(0).decode('ascii')


def test_submission_burl_delivers_the_imap_message():
    token, burl_url = test_imap_metadata_is_available_and_generates_a_urlauth_url()

    with smtplib.SMTP(SERVER, 587, timeout=10) as smtp:
        smtp.ehlo()
        smtp.starttls(context=TLS_CONTEXT)
        smtp.ehlo()
        smtp.login(SENDER, PASSWORD)
        smtp.ehlo()
        assert 'burl' in smtp.esmtp_features
        code, response = smtp.mail(SENDER)
        assert code == 250, response
        code, response = smtp.rcpt(RECIPIENT)
        assert code == 250, response
        code, response = smtp.docmd('BURL', f'{burl_url} LAST')
        assert code == 250, response

    with connect_imap(RECIPIENT, PASSWORD) as imap:
        assert wait_for_message(imap, f'BURL body {token}')


if __name__ == '__main__':
    test_submission_burl_delivers_the_imap_message()
