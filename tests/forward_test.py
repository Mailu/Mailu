import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mail_utils import clear_inbox, connect_imap, wait_for_message

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

# check forward target
try:
    imap_server = connect_imap('user@mailu.io', 'password')
except Exception as exc:
    print("Failed with:", exc)
    sys.exit(110)

if wait_for_message(imap_server, "Forward Text"):
    print("Success: Mail is in forwarded inbox")
else:
    print("Failed receiving email in forwarded inbox")
    sys.exit(99)

clear_inbox(imap_server)

# check original user
try:
    imap_server = connect_imap('forwardinguser@mailu.io', 'password')
except Exception as exc:
    print("Failed with:", exc)
    sys.exit(110)

if wait_for_message(imap_server, "Forward Text"):
    print("Success: Mail is in forwarding inbox")
else:
    print("Failed receiving email in forwarding inbox")
    sys.exit(99)

clear_inbox(imap_server)
