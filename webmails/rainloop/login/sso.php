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
if (isset($_SERVER['HTTP_X_REMOTE_USER']) && isset($_SERVER['HTTP_X_REMOTE_USER_TOKEN'])) {
	$email = $_SERVER['HTTP_X_REMOTE_USER'];
	$password = $_SERVER['HTTP_X_REMOTE_USER_TOKEN'];
	$ssoHash = \RainLoop\Api::GetUserSsoHash($email, $password);

	// redirect to webmail sso url
	header('Location: index.php?sso&hash='.$ssoHash);
}
else {
	header('HTTP/1.0 403 Forbidden');
}
