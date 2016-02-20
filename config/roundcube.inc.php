<?php

$config = array();

$config['db_dsnw'] = 'sqlite:////data/webmail/roundcube.db';
$config['default_host'] = 'localhost';
$config['smtp_server'] = 'localhost';
$config['smtp_port'] = 25;
$config['des_key'] = 'rcmail-!24ByteDESkey*Str';

// List of active plugins (in plugins/ directory)
$config['plugins'] = array(
    'archive',
    'zipdownload',
);

// skin name: folder from skins/
$config['skin'] = 'larry';
