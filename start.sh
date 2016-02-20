#!/bin/sh

# When postfix is installed non-interactively, the file does not get copied to
# the postfix chroot, thus causing smtpd to fail, fix this at runtime
cp /etc/services /var/spool/postfix/etc/

# Fix permissions inside data and create necessary directories if not already
# present
mkdir -p \
 /data/mail \
 /data/webmail/tmp \
 /data/logs \
 /data/ssl

chown -R mail:mail /data/mail
chown -R www-data:www-data /data/webmail /data/logs/webmail

# Copy the system snakeoil certificate if none is provided
if [ ! -f /data/ssl/cert.pem ]; then
  cp /etc/ssl/private/ssl-cert-snakeoil.key /data/ssl/key.pem
  cp /etc/ssl/certs/ssl-cert-snakeoil.pem /data/ssl/cert.pem
fi

# Finally run the server
/usr/bin/supervisord -c /etc/supervisor/supervisord.conf
