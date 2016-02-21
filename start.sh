#!/bin/sh

cat <<< EOF
   __                               _         _
  / _|                             | |       (_)
  | |_ _ __ ___  ___ _ __   ___  ___| |_ ___   _  ___
  |  _| '__/ _ \/ _ \ '_ \ / _ \/ __| __/ _ \ | |/ _ \
  | | | | |  __/  __/ |_) | (_) \__ \ ||  __/_| | (_) |
  |_| |_|  \___|\___| .__/ \___/|___/\__\___(_)_|\___/
                  | |
                  |_|

  For documentation, please visit https://freeposte.io

EOF

# When postfix is installed non-interactively, the file does not get copied to
# the postfix chroot, thus causing smtpd to fail, fix this at runtime
cp /etc/services /var/spool/postfix/etc/

# Create necessary directories
mkdir -p \
 /data/mail \
 /data/webmail/tmp \
 /data/logs \
 /data/ssl

# Create the main database if necessary
if [ ! -f /data/freeposte.db ]
  sqlite3 /data/freeposte.db .databases > /dev/null
fi

# Fixing permissions
chown mail:mail /data/freeposte.db
chown -R mail:mail /data/mail
chown -R www-data:www-data /data/webmail /data/logs/webmail

# Copy the system snakeoil certificate if none is provided
if [ ! -f /data/ssl/cert.pem ]; then
  cat <<< EOF
    No TLS certificate is installed, a snakeoil ceritifcate is thus
    being configured. You MUST NOT run a production server with this
    certificate, as the private key is known publicly.

    You have been warned.
  EOF
  cp /etc/ssl/private/ssl-cert-snakeoil.key /data/ssl/key.pem
  cp /etc/ssl/certs/ssl-cert-snakeoil.pem /data/ssl/cert.pem
fi

# Finally run the server
/usr/bin/supervisord -c /etc/supervisor/supervisord.conf
