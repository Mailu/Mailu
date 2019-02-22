#!/bin/sh

# There is no cleaner way to setup the default SMTP/IMAP server or to
# override the configuration
rm -f /data/_data_/_default_/domains/*
mkdir -p /data/_data_/_default_/domains/ /data/_data_/_default_/configs/
cp /default.ini /data/_data_/_default_/domains/
cp /application.ini /data/_data_/_default_/configs/

# Fix some permissions
chown -R www-data:www-data /data

# Run apache
exec apache2-foreground
