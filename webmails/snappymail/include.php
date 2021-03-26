<?php

// Name this file as "include.php" to enable it.

//header('Strict-Transport-Security: max-age=31536000');

// Uncomment to use gzip encoded output
//define('USE_GZIP', 1);

// Uncomment to enable multiple domain installation.
//define('MULTIDOMAIN', 1);

/**
 * Custom 'data' folder path
 * @return string
 */
function __get_custom_data_full_path()
{
	return '/data/'; // custom data folder path
}

/**
 * Additional configuration file name
 * @return string
 */
function __get_additional_configuration_name()
{
	return 'application.ini';
}
