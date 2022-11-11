<?php

// Scheme for storing the CardDAV passwords, in order from least to best security.
// Options: plain, base64, des_key, encrypted (default)
$prefs['_GLOBAL']['pwstore_scheme'] = 'des_key';
