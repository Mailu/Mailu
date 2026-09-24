import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mail_utils import clear_inbox, connect_imap, wait_for_message

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

for user in ['user@mailu.io', 'admin@mailu.io', 'user/with/slash@mailu.io']:
    try:
        imap_server = connect_imap(user, 'password')
    except Exception as exc:
        print("Failed with:", exc)
        sys.exit(110)

    if wait_for_message(imap_server, "Alias Text"):
        print("Success: Mail is in aliassed inbox", user)
    else:
        print("Failed receiving email in aliassed inbox", user)
        sys.exit(99)

    clear_inbox(imap_server)
