import smtplib
import imaplib
import time
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ntpath
from email.mime.base import MIMEBase
from email import encoders

msg = MIMEMultipart()
msg['From'] = "admin@mailu.io"
msg['To'] = "user@mailu.io"
msg['Subject'] = "File Test"
msg.attach(MIMEText(sys.argv[1], 'plain'))

if len(sys.argv) == 3:
    part = MIMEBase('application', 'octet-stream')
    part.set_payload((open(sys.argv[2], "rb")).read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', "attachment; filename=%s" % ntpath.basename(sys.argv[2]))
    msg.attach(part)

try:
    smtp_server = smtplib.SMTP('localhost')
    smtp_server.set_debuglevel(1)
    smtp_server.connect('localhost', 587)
    smtp_server.ehlo()
    smtp_server.starttls()
    smtp_server.ehlo()
    smtp_server.login("admin@mailu.io", "password")
    
    smtp_server.sendmail("admin@mailu.io", "user@mailu.io", msg.as_string())
    smtp_server.quit()
except:
    sys.exit(25)

time.sleep(30)

try:
    imap_server = imaplib.IMAP4_SSL('localhost')
    imap_server.login('user@mailu.io', 'password')
except:
    sys.exit(110)

stat, count = imap_server.select('inbox')
try:
    stat, data = imap_server.fetch(count[0], '(UID BODY[TEXT])')
except :
    sys.exit(99)
        
if sys.argv[1] in str(data[0][1]):
    print("Success sending and receiving email!")
else:
    print("Failed receiving email with message %s" % sys.argv[1])
    sys.exit(99)
    
imap_server.close()
imap_server.logout()
