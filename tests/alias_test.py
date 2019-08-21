import smtplib
import imaplib
import time
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

msg = MIMEMultipart()
msg['From'] = "admin@mailu.io"
msg['To'] = "forwardinguser@mailu.io"
msg['Subject'] = "Alias Test"
msg.attach(MIMEText("Alias Text", 'plain'))

try:
    smtp_server = smtplib.SMTP('localhost')
    smtp_server.set_debuglevel(1)
    smtp_server.connect('localhost', 587)
    smtp_server.ehlo()
    smtp_server.starttls()
    smtp_server.ehlo()
    smtp_server.login("admin@mailu.io", "password")

    smtp_server.sendmail("admin@mailu.io", "alltheusers@mailu.io", msg.as_string())
    smtp_server.quit()
except:
    sys.exit(25)

time.sleep(30)

for user in ['user@mailu.io', 'admin@mailu.io', 'user/with/slash@mailu.io']:
    try:
        imap_server = imaplib.IMAP4_SSL('localhost')
        imap_server.login(user, 'password')
    except Exception as exc:
        print("Failed with:", exc)
        sys.exit(110)

    stat, count = imap_server.select('inbox')
    try:
        stat, data = imap_server.fetch(count[0], '(UID BODY[TEXT])')
    except :
        sys.exit(99)

    if "Alias Text" in str(data[0][1]):
        print("Success: Mail is in aliassed inbox", user)
    else:
        print("Failed receiving email in aliassed inbox", user)
        sys.exit(99)

    typ, data = imap_server.search(None, 'ALL')
    for num in data[0].split():
        imap_server.store(num, '+FLAGS', '\\Deleted')
    imap_server.expunge()

    imap_server.close()
    imap_server.logout()

