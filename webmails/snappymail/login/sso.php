<?php

$_ENV['SNAPPYMAIL_INCLUDE_AS_API'] = true;
require 'index.php';
// Retrieve email and password
if (isset($_SERVER['HTTP_X_REMOTE_USER']) && isset($_SERVER['HTTP_X_REMOTE_USER_TOKEN'])) {
	$email = $_SERVER['HTTP_X_REMOTE_USER'];
	$password = $_SERVER['HTTP_X_REMOTE_USER_TOKEN'];
	if (($_SERVER['HTTP_X_REMOTE_USER_ALIASES_COMPLETE'] ?? '') === 'true') {
		$aliases = array_filter(array_map('trim', explode(',', $_SERVER['HTTP_X_REMOTE_USER_ALIASES'] ?? '')));
		\RainLoop\Api::Actions()->LocalStorageProvider()->Put(
			$email,
			\RainLoop\Providers\Storage\Enumerations\StorageType::CONFIG,
			'mailu_aliases',
			implode(',', array_unique($aliases))
		);
	}
	$ssoHash = \RainLoop\Api::CreateUserSsoHash($email, $password);

	// redirect to webmail sso url
	header('Location: index.php?sso&hash='.$ssoHash, true, 302);
}
else {
	http_response_code(403);
}
?>
