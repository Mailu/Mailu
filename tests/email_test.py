import smtplib
import imaplib
import time
import sys

email_msg = sys.argv[1]

#Login to smt server and sending email with secret message    
def send_email(msg):
    print("Sending email ...")
    server = smtplib.SMTP('localhost')
    server.set_debuglevel(1)
    server.connect('localhost', 587)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login("admin@mailu.io", "password")
    
    server.sendmail("admin@mailu.io", "user@mailu.io", msg)
    server.quit()

    print("email sent with message " + msg)

#Login to imap server, read latest email and check for secret message    
def read_email():
    print("Receiving email ...")
    server = imaplib.IMAP4_SSL('localhost')
    server.login('user@mailu.io', 'password')
    
    stat, count = server.select('inbox')
    stat, data = server.fetch(count[0], '(UID BODY[TEXT])')
    
    print("email received with message " + str(data[0][1])) 
    
    if email_msg in str(data[0][1]):
        print("Success!")
    else:
        print("Failed receiving email with message %s" % email_msg)
        sys.exit(1)
    server.close()
    server.logout()

    
send_email(email_msg)
print("Sleeping for 1m")
time.sleep(60)
read_email()
