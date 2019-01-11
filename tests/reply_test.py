import smtplib
import imaplib
import time
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

msg = MIMEMultipart()
msg['From'] = "admin@mailu.io"
msg['To'] = "replyusea@mailu.io"
msg['Subject'] = "Reply Test"
msg.attach(MIMEText("Reply Text", 'plain'))

try:
    smtp_server = smtplib.SMTP('localhost')
    smtp_server.set_debuglevel(1)
    smtp_server.connect('localhost', 587)
    smtp_server.ehlo()
    smtp_server.starttls()
    smtp_server.ehlo()
    smtp_server.login("admin@mailu.io", "password")

    smtp_server.sendmail("admin@mailu.io", "replyuser@mailu.io", msg.as_string())
    smtp_server.quit()
except:
    sys.exit(25)

time.sleep(30)

# check original target
try:
    imap_server = imaplib.IMAP4_SSL('localhost')
    imap_server.login('replyuser@mailu.io', 'password')
except Exception as exc:
    print("Failed with:", exc)
    sys.exit(110)

stat, count = imap_server.select('inbox')
try:
    stat, data = imap_server.fetch(count[0], '(UID BODY[TEXT])')
except :
    sys.exit(99)

if "Reply Text" in str(data[0][1]):
    print("Success: Mail is in target inbox")
else:
    print("Failed receiving email in target inbox")
    sys.exit(99)

typ, data = imap_server.search(None, 'ALL')
for num in data[0].split():
    imap_server.store(num, '+FLAGS', '\\Deleted')
imap_server.expunge()

imap_server.close()
imap_server.logout()

# check original/replied user
try:
    imap_server = imaplib.IMAP4_SSL('localhost')
    imap_server.login('admin@mailu.io', 'password')
except Exception as exc:
    print("Failed with:", exc)
    sys.exit(110)

stat, count = imap_server.select('inbox')
try:
    stat, data = imap_server.fetch(count[0], '(UID BODY[TEXT])')
except :
    sys.exit(99)

if "Cause this is just a test" in str(data[0][1]):
    print("Success: Reply is in original inbox")
else:
    print("Failed receiving reply in original inbox")
    sys.exit(99)

typ, data = imap_server.search(None, 'ALL')
for num in data[0].split():
    imap_server.store(num, '+FLAGS', '\\Deleted')
imap_server.expunge()

imap_server.close()
imap_server.logout()
