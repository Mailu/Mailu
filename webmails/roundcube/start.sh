#!/bin/sh

# Fix some permissions
mkdir -p /data/gpg
chown -R www-data:www-data /data

# Run apache
exec apache2-foreground
