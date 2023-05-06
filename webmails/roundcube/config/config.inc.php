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
$config['spellcheck_languages'] = array('en'=>'English (US)', 'uk'=>'English (UK)', 'de'=>'Deutsch', 'fr'=>'French', 'ru'=>'Russian');
$config['session_lifetime'] = {{ (((PERMANENT_SESSION_LIFETIME | default(10800)) | int)/3600) | int }};
$config['request_path'] = '{{ WEB_WEBMAIL or "none" }}';
$config['trusted_host_patterns'] = [ {{ HOSTNAMES.split(",") | map("tojson") | join(',') }}];

// Mail servers
$config['imap_host'] = '{{ FRONT_ADDRESS or "front" }}:10143';
$config['smtp_host'] = '{{ FRONT_ADDRESS or "front" }}:10025';
$config['smtp_user'] = '%u';
$config['smtp_pass'] = '%p';

// Sieve script management
$config['managesieve_host'] = '{{ FRONT_ADDRESS or "front" }}:14190';
$config['managesieve_mbox_encoding'] = 'UTF8';

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

// zero quota is unlimited
$config['quota_zero_as_unlimited'] = true;

// includes
{%- for inc in INCLUDES %}
include('/overrides/{{ inc }}');
{%- endfor %}

