#!/bin/sh

# Fix some permissions
chown -R www-data:www-data /data

# There is no cleaner way to setup the default SMTP/IMAP server or to
# override the configuration
rm -f /data/_data_/_default_/domains/*
cp /default.ini /data/_data_/_default_/domains/
cp /config.ini /data/_data_/_default_/configs/

# Run apache
exec apache2-foreground
