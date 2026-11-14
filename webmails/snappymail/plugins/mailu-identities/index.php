<?php

use RainLoop\Plugins\AbstractPlugin;

class MailuIdentitiesPlugin extends AbstractPlugin
{
	const
		NAME = 'Mailu Aliases',
		VERSION = '1.3',
		AUTHOR = 'Mailu',
		REQUIRED = '2.20.0',
		CATEGORY = 'Accounts',
		DESCRIPTION = 'Adds Mailu aliases as sender identities.';

	public function __construct()
	{
		include_once __DIR__ . '/MailuAliases.php';
		parent::__construct();
	}

	public function Init(): void
	{
		$this->addHook('main.fabrica', 'MainFabrica');
		$this->addJs('mailu.js');
	}

	public function FilterAppDataPluginSection(bool $admin, bool $auth, array &$config): void
	{
		if (!$admin && $auth) {
			$config['accountSettingsUrl'] = $this->Manager()->Actions()->Config()->Get(
				'mailu', 'account_settings_url', ''
			);
		}
	}

	public function MainFabrica(string $name, &$result): void
	{
		if ($name === 'identities') {
			$result[] = new \RainLoop\Providers\Identities\MailuAliases(
				$this->Manager()->Actions()->LocalStorageProvider()
			);
		}
	}
}
