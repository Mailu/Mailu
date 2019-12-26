<?php

$config = array();

// Generals
$config['db_dsnw'] = 'sqlite:////data/roundcube.db';
$config['temp_dir'] = '/tmp/';
$config['des_key'] = getenv('SECRET_KEY');
$config['cipher_method'] = 'AES-256-CBC';
$config['identities_level'] = 0;
$config['reply_all_mode'] = 1;

// List of active plugins (in plugins/ directory)
$config['plugins'] = array(
    'archive',
    'zipdownload',
    'markasjunk',
    'managesieve',
    'enigma',
    'carddav'
);

$front = getenv('FRONT_ADDRESS') ? getenv('FRONT_ADDRESS') : 'front';
$imap  = getenv('IMAP_ADDRESS')  ? getenv('IMAP_ADDRESS')  : 'imap';

// Mail servers
$config['default_host'] = $front;
$config['default_port'] = 10143;
$config['smtp_server'] = $front;
$config['smtp_port'] = 10025;
$config['smtp_user'] = '%u';
$config['smtp_pass'] = '%p';

// Sieve script management
$config['managesieve_host'] = $imap;
$config['managesieve_usetls'] = false;

// Customization settings
$config['support_url'] = getenv('WEB_ADMIN') ? '../..' . getenv('WEB_ADMIN') : '';
$config['product_name'] = 'Mailu Webmail';

// We access the IMAP and SMTP servers locally with internal names, SSL
// will obviously fail but this sounds better than allowing insecure login
// from the outter world
$ssl_no_check = array(
 'ssl' => array(
     'verify_peer' => false,
     'verify_peer_name' => false,
  ),
);
$config['imap_conn_options'] = $ssl_no_check;
$config['smtp_conn_options'] = $ssl_no_check;
$config['managesieve_conn_options'] = $ssl_no_check;

// skin name: folder from skins/
$config['skin'] = 'elastic';

// Enigma gpg plugin
$config['enigma_pgp_homedir'] = '/data/gpg';
