import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mail_utils import clear_inbox, connect_imap, wait_for_message

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

# check original target
try:
    imap_server = connect_imap('replyuser@mailu.io', 'password')
except Exception as exc:
    print("Failed with:", exc)
    sys.exit(110)

if wait_for_message(imap_server, "Reply Text"):
    print("Success: Mail is in target inbox")
else:
    print("Failed receiving email in target inbox")
    sys.exit(99)

clear_inbox(imap_server)

# check original/replied user
try:
    imap_server = connect_imap('admin@mailu.io', 'password')
except Exception as exc:
    print("Failed with:", exc)
    sys.exit(110)

if wait_for_message(imap_server, "Cause this is just a test"):
    print("Success: Reply is in original inbox")
else:
    print("Failed receiving reply in original inbox")
    sys.exit(99)

clear_inbox(imap_server)
