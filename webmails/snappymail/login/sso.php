<?php

$_ENV['SNAPPYMAIL_INCLUDE_AS_API'] = true;
require 'index.php';
// Retrieve email and password
if (isset($_SERVER['HTTP_X_REMOTE_USER']) && isset($_SERVER['HTTP_X_REMOTE_USER_TOKEN'])) {
	$email = $_SERVER['HTTP_X_REMOTE_USER'];
	$password = $_SERVER['HTTP_X_REMOTE_USER_TOKEN'];
	$ssoHash = \RainLoop\Api::CreateUserSsoHash($email, $password);

	// redirect to webmail sso url
	header('Location: index.php?sso&hash='.$ssoHash, 302);
}
else {
	header('HTTP/1.0 403 Forbidden', 403);
}
?>
