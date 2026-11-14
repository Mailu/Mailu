<?php

namespace RainLoop\Providers\Identities;

use RainLoop\Model\Account;
use RainLoop\Model\Identity;
use RainLoop\Providers\Storage;
use RainLoop\Providers\Storage\Enumerations\StorageType;

class MailuAliases implements IIdentities
{
	private Storage $storage;

	public function __construct(Storage $storage)
	{
		$this->storage = $storage;
	}

	public function GetIdentities(Account $account): array
	{
		$aliases = $this->storage->Get($account, StorageType::CONFIG, 'mailu_aliases', '');
		$identities = [new Identity('', $account->Email())];

		foreach (\explode(',', $aliases) as $email) {
			$email = \trim($email);
			if ($email) {
				$identities[] = new Identity($email, $email);
			}
		}

		return $identities;
	}

	public function SetIdentities(Account $account, array $identities): void
	{
	}

	public function SupportsStore(): bool
	{
		return false;
	}

	public function Name(): string
	{
		return 'MailuAliases';
	}
}
