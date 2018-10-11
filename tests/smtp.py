import smtplib
import sys
from email import mime

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

msg = mime.multipart.MIMEMultipart()
msg['Subject'] = 'Test email'
msg['From'] = sys.argv[1]
msg['To'] = sys.argv[2]
msg.preamble = 'Test email'

s = smtplib.SMTP('localhost')
s.set_debuglevel(1)
s.send_message(msg)
s.quit()
