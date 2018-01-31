#!/bin/sh

template(){
  sed \
    -e "s/%FRONT_ADDRESS%/$FRONT_ADDRESS/g" \
    -e "s/%IMAP_ADDRESS%/$IMAP_ADDRESS/g"
}

# There is no cleaner way to setup the default SMTP/IMAP server or to
# override the configuration
rm -f /data/_data_/_default_/domains/*
mkdir -p /data/_data_/_default_/domains/ /data/_data_/_default_/configs/
template </default.ini >/data/_data_/_default_/domains/default.ini
template </config.ini  >/data/_data_/_default_/configs/config.ini

# Fix some permissions
chown -R www-data:www-data /data

# Run apache
exec apache2-foreground
