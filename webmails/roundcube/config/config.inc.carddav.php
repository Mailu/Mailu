<?php

// Scheme for storing the CardDAV passwords, in order from least to best security.
// Options: plain, base64, des_key, encrypted (default)
$prefs['_GLOBAL']['pwstore_scheme'] = 'des_key';

{% if DAV_ENABLED %}
// %p remains a placeholder in the database; it resolves to the current SSO
// session token, which is accepted only on the internal webmail listener.
$prefs['Mailu'] = [
    'accountname' => 'Mailu',
    'username' => '%u',
    'password' => '%p',
    'discovery_url' => {{ DAV_INTERNAL_URL | tojson }},
    'ssl_noverify' => true,
    'active' => true,
    'refresh_time' => '00:01:00',
    'rediscover_time' => '00:01:00',
    'fixed' => ['discovery_url', 'username', 'password'],
    'hide' => true,
];
// Use the shared book by default, while respecting a user's saved choice.
if (!array_key_exists('default_addressbook', rcube::get_instance()->user->get_prefs())) {
    $prefs['_GLOBAL']['default_addressbook'] = ['preset' => 'Mailu'];
}
{% endif %}

// Plugin settings have their own scope ($prefs), separate from Roundcube's
// $config. This optional file can add external DAV presets or change defaults.
if (is_file({{ (OVERRIDE_DIRECTORY ~ '/carddav.php') | tojson }})) {
    include {{ (OVERRIDE_DIRECTORY ~ '/carddav.php') | tojson }};
}
