<?php

$config = array();

// Generals
$config['db_dsnw'] = '{{ DB_DSNW }}';
$config['temp_dir'] = '/dev/shm/';
$config['des_key'] = '{{ ROUNDCUBE_KEY }}';
$config['cipher_method'] = 'AES-256-CBC';
$config['identities_level'] = 0;
$config['reply_all_mode'] = 1;
$config['log_driver'] = 'stdout';
$config['zipdownload_selection'] = true;
$config['enable_spellcheck'] = true;
$config['spellcheck_engine'] = 'pspell';
$config['session_lifetime'] = {{ SESSION_TIMEOUT_MINUTES | int }};

// Mail servers
$config['imap_host'] = '{{ FRONT_ADDRESS or "front" }}:10143';
$config['smtp_host'] = '{{ FRONT_ADDRESS or "front" }}:10025';
$config['smtp_user'] = '%u';
$config['smtp_pass'] = '%p';

#old deprecated settings will be replaced from roundcube 1.6.
$config['smtp_server']  = '{{ FRONT_ADDRESS or "front" }}';
$config['smtp_port'] = '10025';
$config['default_host']  = '{{ FRONT_ADDRESS or "front" }}';
$config['default_port'] = '10143';

// Sieve script management
$config['managesieve_host'] = '{{ IMAP_ADDRESS or "imap" }}';

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

// roundcube customization
$config['product_name'] = 'Mailu Webmail';
{%- if ADMIN and WEB_ADMIN %}
$config['support_url'] = '../..{{ WEB_ADMIN }}';
{%- endif %}
$config['plugins'] = array({{ PLUGINS }});

// skin name: folder from skins/
$config['skin'] = 'elastic';

// configure mailu sso plugin
$config['sso_logout_url'] = '/sso/logout';

// configure enigma gpg plugin
$config['enigma_pgp_homedir'] = '/data/gpg';

// configure mailu button
$config['show_mailu_button'] = {{ 'true' if ADMIN and WEB_ADMIN else 'false' }};

// set From header for DKIM signed message delivery reports
$config['mdn_use_from'] = true;

// includes
{%- for inc in INCLUDES %}
include('/overrides/{{ inc }}');
{%- endfor %}

