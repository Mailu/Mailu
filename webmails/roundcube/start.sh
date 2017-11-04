#!/bin/sh

# Fix some permissions
chown -R www-data:www-data /data

# Run apache
exec apache2-foreground
