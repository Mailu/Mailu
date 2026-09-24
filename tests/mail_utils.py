import imaplib
import time


def connect_imap(username, password):
    server = imaplib.IMAP4_SSL('localhost', timeout=10)
    server.login(username, password)
    return server


def wait_for_message(server, expected, timeout=60):
    deadline = time.monotonic() + timeout
    expected = expected.encode()

    while True:
        status, _ = server.select('inbox')
        if status != 'OK':
            raise imaplib.IMAP4.error('Could not select inbox')

        status, data = server.search(None, 'ALL')
        if status != 'OK':
            raise imaplib.IMAP4.error('Could not search inbox')

        for message_id in reversed(data[0].split()):
            status, message = server.fetch(message_id, '(UID BODY[TEXT])')
            if status == 'OK' and expected in message[0][1]:
                return True

        if time.monotonic() >= deadline:
            return False
        time.sleep(1)


def clear_inbox(server):
    status, data = server.search(None, 'ALL')
    if status != 'OK':
        raise imaplib.IMAP4.error('Could not search inbox')
    for message_id in data[0].split():
        server.store(message_id, '+FLAGS', '\\Deleted')
    server.expunge()
    server.close()
    server.logout()
