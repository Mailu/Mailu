<?php

$_ENV['RAINLOOP_INCLUDE_AS_API'] = true;
if (!defined('APP_VERSION')) {
	$version = file_get_contents('/data/VERSION');
	if ($version) {
		define('APP_VERSION', $version);
		define('APP_INDEX_ROOT_FILE', __FILE__);
		define('APP_INDEX_ROOT_PATH', str_replace('\\', '/', rtrim(dirname(__FILE__), '\\/').'/'));
	}
}

if (file_exists(APP_INDEX_ROOT_PATH.'rainloop/v/'.APP_VERSION.'/include.php')) {
	include APP_INDEX_ROOT_PATH.'rainloop/v/'.APP_VERSION.'/include.php';
} else {
	echo '[105] Missing version directory';
	exit(105);
}

// Retrieve email and password
if (array_key_exists('X-Remote-User', $_SERVER) && array_key_exists('X-Remote-User-Token', $_SERVER)) {
        $email = $_SERVER['X-Remote-User'];
        $password = $_SERVER['X-Remote-User-Token'];
	$ssoHash = \RainLoop\Api::GetUserSsoHash($email, $password);

	// redirect to webmail sso url
	header('Location: index.php?sso&hash='.$ssoHash);
}
else {
	print_r('This is a bug in Mailu; please report it');
}
