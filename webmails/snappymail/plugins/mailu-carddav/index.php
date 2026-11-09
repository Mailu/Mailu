<?php

class MailuCarddavPlugin extends \RainLoop\Plugins\AbstractPlugin
{
    const NAME = 'Mailu Contacts', VERSION = '1.0', AUTHOR = 'Mailu',
        REQUIRED = '3.0.0', CATEGORY = 'Contacts',
        DESCRIPTION = 'Sets up the Mailu address book using the current webmail session.';

    public function Init(): void
    {
        $this->addHook('login.success', 'Login');
        $this->addHook('filter.fabrica', 'Fabrica');
    }

    public function Login(\RainLoop\Model\Account $account): void
    {
        $actions = $this->Manager()->Actions();
        $url = $actions->Config()->Get('custom', 'mailu_carddav_url', '');
        if (!$url || !($account instanceof \RainLoop\Model\MainAccount)) {
            return;
        }

        $stored = $actions->StorageProvider()->Get(
            $account, \RainLoop\Providers\Storage\Enumerations\StorageType::CONFIG, 'contacts_sync'
        );
        $data = $stored ? json_decode($stored, true) : null;
        // Preserve external accounts and explicit opt-outs. Saving unchanged
        // Mailu settings removes custom fields, so recognize our public URL as
        // well as the marker when refreshing credentials on later logins.
        if ($stored) {
            $sameAccount = ($data['Url'] ?? '') === $url
                && ($data['User'] ?? '') === $account->Email();
            if (empty($data['Mode']) || (empty($data['Mailu']) && !$sameAccount)) {
                return;
            }
        }
        $actions->setContactsSyncData($account, [
            'Mailu' => true,
            'Mode' => $data['Mode'] ?? 1,
            'Url' => $url,
            'User' => $account->Email(),
            'Password' => $account->ImapPass(),
        ]);
    }

    public function Fabrica(string $name, &$result, ?\RainLoop\Model\Account $account): void
    {
        if ($name !== 'address-book' || !($account instanceof \RainLoop\Model\MainAccount)) {
            return;
        }
        $config = $this->Manager()->Actions()->Config();
        $public = $config->Get('custom', 'mailu_carddav_url', '');
        $internal = $config->Get('custom', 'mailu_carddav_internal_url', '');
        if ($public && $internal) {
            require_once __DIR__ . '/AddressBook.php';
            $result = new \Mailu\AddressBook($account->Email(), $public, $internal, $account->EmailAscii());
            // filter.fabrica runs after the normal provider logger setup.
            $result->SetLogger($this->Manager()->Actions()->Logger());
        }
    }
}
