<?php

$config = array();

// Generals
$config['db_dsnw'] = 'sqlite:////data/roundcube.db';
$config['des_key'] = 'rcmail-!24ByteDESkey*Str';
$config['identities_level'] = 3;
$config['reply_all_mode'] = 1;

// List of active plugins (in plugins/ directory)
$config['plugins'] = array(
    'archive',
    'zipdownload',
    'managesieve',
    'markasjunk',
    'password'
);

// Mail servers
$config['default_host'] = 'tls://imap';
$config['default_port'] = 143;
$config['smtp_server'] = 'tls://smtp';
$config['smtp_port'] = 587;
$config['smtp_user'] = '%u';
$config['smtp_pass'] = '%p';

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

// Password management
$config['password_driver'] = 'sql';
$config['password_confirm_current'] = true;
$config['password_minimum_length'] = 6;
$config['password_db_dsn'] = 'sqlite:////data/freeposte.db';
$config['password_query'] = '
  UPDATE user SET password=%D
  WHERE id IN (SELECT user.id FROM user
               INNER JOIN domain ON domain.id=user.domain_id
               WHERE domain.name=%d AND user.name=%l
              )
';
$config['password_dovecotpw'] = 'doveadm pw';
$confog['password_dovecotpw_method'] = 'SHA512-CRYPT';

// skin name: folder from skins/
$config['skin'] = 'larry';
