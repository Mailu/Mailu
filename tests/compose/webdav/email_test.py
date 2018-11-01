import string
import random
import smtplib
import imaplib
import time

def secret(length=16):
    charset = string.ascii_uppercase + string.digits
    return ''.join(
        random.SystemRandom().choice(charset)
        for _ in range(length)
    )
  
#Generating secret message    
secret_message = secret(16)

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
    
    if secret_message in str(data[0][1]):
        print("Success!")
    else:
        print("Failed! Something went wrong")    
    server.close()
    server.logout()

    
send_email(secret_message)
print("Sleeping for 1m")
time.sleep(60)
read_email()
