import smtplib
import imaplib
import time
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

msg = MIMEMultipart()
msg['From'] = "admin@mailu.io"
msg['To'] = "forwardinguser@mailu.io"
msg['Subject'] = "Forward Test"
msg.attach(MIMEText("Forward Text", 'plain'))

try:
    smtp_server = smtplib.SMTP('localhost')
    smtp_server.set_debuglevel(1)
    smtp_server.connect('localhost', 587)
    smtp_server.ehlo()
    smtp_server.starttls()
    smtp_server.ehlo()
    smtp_server.login("admin@mailu.io", "password")

    smtp_server.sendmail("admin@mailu.io", "forwardinguser@mailu.io", msg.as_string())
    smtp_server.quit()
except:
    sys.exit(25)

time.sleep(30)

# check forward target
try:
    imap_server = imaplib.IMAP4_SSL('localhost')
    imap_server.login('user@mailu.io', 'password')
except Exception as exc:
    print("Failed with:", exc)
    sys.exit(110)

stat, count = imap_server.select('inbox')
try:
    stat, data = imap_server.fetch(count[0], '(UID BODY[TEXT])')
except :
    sys.exit(99)

if "Forward Text" in str(data[0][1]):
    print("Success: Mail is in forwarded inbox")
else:
    print("Failed receiving email in forwarded inbox")
    sys.exit(99)

typ, data = imap_server.search(None, 'ALL')
for num in data[0].split():
    imap_server.store(num, '+FLAGS', '\\Deleted')
imap_server.expunge()

imap_server.close()
imap_server.logout()

# check original user
try:
    imap_server = imaplib.IMAP4_SSL('localhost')
    imap_server.login('forwardinguser@mailu.io', 'password')
except Exception as exc:
    print("Failed with:", exc)
    sys.exit(110)

stat, count = imap_server.select('inbox')
try:
    stat, data = imap_server.fetch(count[0], '(UID BODY[TEXT])')
except :
    sys.exit(99)

if "Forward Text" in str(data[0][1]):
    print("Success: Mail is in forwarding inbox")
else:
    print("Failed receiving email in forwarding inbox")
    sys.exit(99)

typ, data = imap_server.search(None, 'ALL')
for num in data[0].split():
    imap_server.store(num, '+FLAGS', '\\Deleted')
imap_server.expunge()

imap_server.close()
imap_server.logout()
