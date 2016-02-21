<?php

$config = array();

// Generals
$config['db_dsnw'] = 'sqlite:////data/webmail/roundcube.db';
$config['des_key'] = 'rcmail-!24ByteDESkey*Str';
$config['identities_level'] = 3;
$config['reply_all_mode'] = 1;

// Mail servers
$config['default_host'] = 'localhost';
$config['default_port'] = 143;
$config['smtp_server'] = 'localhost';
$config['smtp_port'] = 25;

// List of active plugins (in plugins/ directory)
$config['plugins'] = array(
    'archive',
    'zipdownload',
    'managesieve',
    'markasjunk'
);

// skin name: folder from skins/
$config['skin'] = 'larry';
