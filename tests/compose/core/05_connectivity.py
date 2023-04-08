#!/usr/bin/env python3

import imaplib
import poplib
import smtplib
import os

SERVER='localhost'
USERNAME='test@mailu.io'
PASSWORD='password'

def test_imap(server, username, password):
    with imaplib.IMAP4_SSL(server) as conn:
        conn.login(username, password)
        if conn.status('inbox')[0] != 'OK':
            print(f'Authenticating to imaps://{username}:{password}@{server}:993/ failed!')
            os.exit(101)
    with imaplib.IMAP4(server) as conn:
        conn.starttls()
        conn.login(username, password)
        if conn.status('inbox')[0] != 'OK':
            print(f'Authenticating to imap://{username}:{password}@{server}:143/ failed!')
            os.exit(101)
    try:
        with imaplib.IMAP4(server) as conn:
            conn.login(username, password)
        print(f'Authenticating to imap://{username}:{password}@{server}:143/ worked without STARTTLS!')
        os.exit(102)
    except imaplib.error:
        pass

def test_pop3(server, username, password):
    print(f'Authenticating to pop3s://{username}:{password}@{server}:995/')
    conn = poplib.POP3_SSL(server)
    conn.capa()
    conn.user(username)
    conn.pass_(password)
    conn.close()
    print(f'Authenticating to pop3s://{username}:{password}@{server}:110/')
    conn = poplib.POP3(server)
    conn.stls()
    conn.capa()
    conn.user(username)
    conn.pass_(password)
    conn.close()
    print(f'Authenticating to pop3://{username}:{password}@{server}:110/')
    try:
        conn = poplib.POP3(server)
        conn.capa()
        conn.user(username)
        conn.pass_(password)
        conn.close()
        print(f'Authenticating to pop3://{username}:{password}@{server}:110/ worked without STARTTLS!')
        os.exit(103)
    except poplib.error_proto:
        pass

def test_SMTP(server, username, password):
    with smtplib.SMTP_SSL(server) as conn:
        conn.ehlo()
        conn.login(username, password)
    with smtplib.SMTP(server) as conn:
        conn.ehlo()
        conn.starttls()
        conn.ehlo()
        conn.login(username, password)
    try:
        with smtplib.SMTP(server) as conn:
            conn.ehlo()
            conn.login(username, password)
            print(f'Authenticating to smtp://{username}:{password}@{server}:25/ worked without STARTTLS!')
            os.exit(104)
    except smtplib.SMTPNotSupportedError:
        pass

if __name__ == '__main__':
    test_imap(SERVER, USERNAME, PASSWORD)
    test_pop3(SERVER, USERNAME, PASSWORD)
    test_SMTP(SERVER, USERNAME, PASSWORD)
