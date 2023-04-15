#!/usr/bin/env python3

import base64
import imaplib
import poplib
import smtplib
import sys
import socket
import ssl

SERVER='localhost'
USERNAME='user@mailu.io'
PASSWORD='password'

def test_imap(server, username, password):
    print(f'Authenticating to imaps://{username}:{password}@{server}:993/')
    with imaplib.IMAP4_SSL(server) as conn:
        conn.login(username, password)
        conn.noop()
    print('OK')
    print(f'Authenticating to imaps://{username}:{password}@{server}:143/')
    with imaplib.IMAP4(server) as conn:
        conn.starttls()
        conn.login(username, password)
        conn.noop()
    print('OK')
    print(f'Authenticating to imap://{username}:{password}@{server}:143/')
    try:
        with imaplib.IMAP4(server) as conn:
            conn.login(username, password)
        print(f'Authenticating to imap://{username}:{password}@{server}:143/ worked without STARTTLS!')
        sys.exit(102)
    except imaplib.IMAP4.error:
        print('NOK - expected')

def test_pop3(server, username, password):
    print(f'Authenticating to pop3s://{username}:{password}@{server}:995/')
    conn = poplib.POP3_SSL(server)
    conn.capa()
    conn.user(username)
    conn.pass_(password)
    conn.close()
    print('OK')
    print(f'Authenticating to pop3s://{username}:{password}@{server}:110/')
    conn = poplib.POP3(server)
    conn.stls()
    conn.capa()
    conn.user(username)
    conn.pass_(password)
    conn.close()
    print('OK')
    print(f'Authenticating to pop3://{username}:{password}@{server}:110/')
    try:
        conn = poplib.POP3(server)
        conn.capa()
        conn.user(username)
        conn.pass_(password)
        conn.close()
        print(f'Authenticating to pop3://{username}:{password}@{server}:110/ worked without STARTTLS!')
        sys.exit(103)
    except poplib.error_proto:
        print('NOK - expected')

def test_SMTP(server, username, password):
    print(f'Authenticating to smtps://{username}:{password}@{server}:465/')
    with smtplib.SMTP_SSL(server) as conn:
        conn.ehlo()
        conn.login(username, password)
        print('OK')
    print(f'Authenticating to smtps://{username}:{password}@{server}:587/')
    with smtplib.SMTP(server, 587) as conn:
        conn.ehlo()
        conn.starttls()
        conn.ehlo()
        conn.login(username, password)
        print('OK')
    try:
        print(f'Authenticating to smtp://{username}:{password}@{server}:587/')
        with smtplib.SMTP(server, 587) as conn:
            conn.ehlo()
            conn.login(username, password)
            print(f'Authenticating to smtp://{username}:{password}@{server}:587/ worked!')
            sys.exit(104)
    except smtplib.SMTPNotSupportedError:
        print('NOK - expected')
    #port 25 should fail
    try:
        print(f'Authenticating to smtps://{username}:{password}@{server}:25/')
        with smtplib.SMTP(server) as conn:
            conn.ehlo()
            conn.starttls()
            conn.ehlo()
            conn.login(username, password)
            print(f'Authenticating to smtps://{username}:{password}@{server}:25/ worked!')
            sys.exit(105)
    except smtplib.SMTPNotSupportedError:
        print('NOK - expected')
    try:
        print(f'Authenticating to smtp://{username}:{password}@{server}:25/')
        with smtplib.SMTP(server) as conn:
            conn.ehlo()
            conn.login(username, password)
            print(f'Authenticating to smtp://{username}:{password}@{server}:25/ worked without STARTTLS!')
            sys.exit(106)
    except smtplib.SMTPNotSupportedError:
        print('NOK - expected')

def test_managesieve(server, username, password):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    print(f'Authenticating to managesieves://{username}:{password}@{server}:4190/')
    with socket.create_connection((server, 4190)) as sock:
        with ctx.wrap_socket(sock) as ssock:
            capa = ssock.read()
            if not capa.endswith(b'OK "Dovecot ready."\r\n'):
                print(f'failed!')
                sys.exit(107)
            auth = str(base64.b64encode(f"\0{username}\0wrongpw".encode('utf-8')), 'utf-8')
            ssock.write(f'AUTHENTICATE "PLAIN" "{auth}"\r\n'.encode('utf-8'))
            r = str(ssock.read(), 'utf-8')
            if not r.startswith('NO '):
                print(f'Authenticating to managesieves://{username}:{password}@{server}:4190/ with wrong creds worked!')
                sys.exit(108)
            auth = str(base64.b64encode(f"\0{username}\0{password}".encode('utf-8')), 'utf-8')
            ssock.write(f'AUTHENTICATE "PLAIN" "{auth}"\r\n'.encode('utf-8'))
            r = str(ssock.read(), 'utf-8')
            if not r.startswith('OK '):
                print(f'Authenticating to managesieves://{username}:{password}@{server}:4190/ failed!')
                sys.exit(109)
            ssock.write(f'LISTSCRIPTS\r\n'.encode('utf-8'))
            r = ssock.read()
            if not r.endswith(b'OK "Listscripts completed."\r\n'):
                print(f'Listing scripts failed!')
                sys.exit(110)
            print('OK')

if __name__ == '__main__':
    test_imap(SERVER, USERNAME, PASSWORD)
    test_pop3(SERVER, USERNAME, PASSWORD)
    test_SMTP(SERVER, USERNAME, PASSWORD)
    test_managesieve(SERVER, USERNAME, PASSWORD)
