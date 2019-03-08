<?php

// Rename this file to "include.php" to enable it.

/**
 * @return string
 */
function __get_custom_data_full_path()
{
	return '/data/'; // custom data folder path
}

/**
 * @return string
 */
function __get_additional_configuration_name()
{
	return 'application.ini';
}
