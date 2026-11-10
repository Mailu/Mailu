<?php
// Exercise the integration's hooks without needing an IMAP server or database.
namespace RainLoop\Plugins {
    class AbstractPlugin {
        public $manager;
        public function Manager() { return $this->manager; }
    }
}
namespace RainLoop\Model {
    class Account {
        public string $password = 'token-session-1';
        public function Email() { return 'alice@example.org'; }
        public function EmailAscii() { return $this->Email(); }
        public function ImapPass() { return $this->password; }
    }
    class MainAccount extends Account {}
}
namespace RainLoop\Providers\Storage\Enumerations {
    class StorageType { const CONFIG = 'config'; }
}
namespace RainLoop\Providers\AddressBook {
    class PdoAddressBook {
        public $config;
        public $logger;
        public $savedEtag;
        public $storedEtag = 'abcdef123456';
        public function __construct() {}
        public function SetLogger($logger) { $this->logger = $logger; }
        public function logMask($value) {}
        public function setDAVClientConfig(?array $config) { $this->config = $config; }
        public function getDavClient(): ?\SnappyMail\DAV\Client { return null; }
        protected function prepareAndExecute($sql, $params) {
            return new class($this->storedEtag) {
                public function __construct(private $etag) {}
                public function fetchColumn() { return $this->etag; }
            };
        }
        public function ContactSave(\RainLoop\Providers\AddressBook\Classes\Contact $contact): bool {
            $this->savedEtag = $contact->Etag;
            return true;
        }
        public function Sync(): bool {
            $contact = new \RainLoop\Providers\AddressBook\Classes\Contact;
            $contact->Etag = 'imported-server-etag';
            return $this->ContactSave($contact);
        }
    }
}
namespace RainLoop\Providers\AddressBook\Classes {
    class Contact {
        public string $id = '1';
        public string $Etag = '0';
    }
}
namespace SnappyMail\DAV {
    class Client {
        public static array $resources = [];
        public string $urlPath;
        public function __construct(public array $settings) {}
        public function setVerifyPeer(bool $value): void {}
        public function propFind($path, $properties, $depth) { return self::$resources; }
    }
}
namespace {
    function check($condition, $message) {
        if (!$condition) { throw new \RuntimeException($message); }
    }
    class FakeActions {
        public $stored = '';
        public array $settings = [
            'mailu_carddav_url' => 'https://mail.example.org/webdav/',
            'mailu_carddav_internal_url' => 'http://front:8081/webdav/',
        ];
        public function Actions() { return $this; }
        public function Config() { return $this; }
        public function Logger() { return $this; }
        public function StorageProvider() { return $this; }
        public function Get(...$args) {
            return $args[0] === 'custom' ? ($this->settings[$args[1]] ?? $args[2]) : $this->stored;
        }
        public function setContactsSyncData($account, $data) { $this->stored = json_encode($data); }
    }
    $root = $argv[1];
    require $root . '/webmails/snappymail/plugins/mailu-carddav/index.php';
    $plugin = new \MailuCarddavPlugin;
    $actions = $plugin->manager = new FakeActions;
    $account = new \RainLoop\Model\MainAccount;
    $plugin->Login($account);
    $data = json_decode($actions->stored, true);
    check($data['Mode'] === 1 && $data['Mailu'], 'Automatic setup failed');
    check($data['Password'] === $account->password, 'Missing session credentials');
    check($data['Url'] === $actions->settings['mailu_carddav_url'], 'Internal URL exposed in preferences');
    $account->password = 'token-session-2';
    $plugin->Login($account);
    check(json_decode($actions->stored, true)['Password'] === 'token-session-2', 'Stale session token');

    $saved = json_decode($actions->stored, true);
    unset($saved['Mailu']);
    $saved['Mode'] = 2;
    $actions->stored = json_encode($saved);
    $account->password = 'token-session-3';
    $plugin->Login($account);
    $saved = json_decode($actions->stored, true);
    check($saved['Password'] === 'token-session-3' && $saved['Mode'] === 2,
          'Saving Mailu settings lost credential refresh or read-only choice');

    foreach ([['Mode' => 0], ['Mode' => 1, 'Url' => 'https://external.example.org/dav/']] as $custom) {
        $actions->stored = json_encode($custom);
        $plugin->Login($account);
        check(json_decode($actions->stored, true) === $custom, 'User preferences overwritten');
    }
    $actions->stored = '';
    $plugin->Login(new \RainLoop\Model\Account);
    check($actions->stored === '', 'Additional account was configured');

    $book = null;
    $plugin->Fabrica('address-book', $book, $account);
    check($book instanceof \Mailu\AddressBook, 'Address book integration missing');
    check($book->logger === $actions, 'Replacement address book has no logger');
    $data = ['Mode' => 1, 'Url' => $actions->settings['mailu_carddav_url'],
             'User' => $account->Email(), 'Password' => $account->password];
    $book->setDAVClientConfig($data);
    check($book->config['Url'] === $actions->settings['mailu_carddav_internal_url'], 'Internal routing failed');
    check($data['Url'] === $actions->settings['mailu_carddav_url'], 'Caller configuration mutated');
    $type = ['{DAV:}resourcetype' => ['{urn:ietf:params:xml:ns:carddav}addressbook']];
    \SnappyMail\DAV\Client::$resources = [
        '/webdav/alice%40example.org/personal/' => $type,
        '/webdav/alice%40example.org/contacts/' => $type,
        '/webdav/bob%40example.org/contacts/' => $type,
    ];
    check($book->getDavClient()->urlPath === '/webdav/alice%40example.org/contacts/',
          'Default DAV collection was not selected');
    unset(\SnappyMail\DAV\Client::$resources['/webdav/alice%40example.org/contacts/']);
    check($book->getDavClient()->urlPath === '/webdav/alice%40example.org/personal/',
          'Existing address book was not selected');
    $contact = new \RainLoop\Providers\AddressBook\Classes\Contact;
    $book->ContactSave($contact);
    check($book->savedEtag === 'mailu-local-change', 'An alphabetic ETag caused a local edit to be lost');
    $book->Sync();
    check($book->savedEtag === 'imported-server-etag', 'A remote import was marked as a local edit');
    $contact->Etag = '0';
    $book->ContactSave($contact);
    check($book->savedEtag === 'mailu-local-change', 'Local edit tracking did not resume after sync');
    $contact->id = '';
    $contact->Etag = '';
    $book->ContactSave($contact);
    check($book->savedEtag === '', 'A new local contact was marked as previously synced');
    $data['Url'] = 'https://external.example.org/dav/';
    $book->setDAVClientConfig($data);
    check($book->config === $data, 'External account changed');
    $data['Url'] = $actions->settings['mailu_carddav_url'];
    $data['User'] = 'someone-else@example.org';
    $book->setDAVClientConfig($data);
    check($book->config === $data, 'Another user routed internally');
    $book->setDAVClientConfig(null);
    check($book->config === null, 'Disabled sync changed');

    $actions->settings = [];
    $plugin->Login($account);
    check($actions->stored === '', 'Disabled DAV configured');
    $book = null;
    $plugin->Fabrica('address-book', $book, $account);
    check($book === null, 'Disabled DAV changed the provider');
    echo "SnappyMail CardDAV hooks passed\n";

    // Also check acceptance by the actual upstream INI reader in the webmail
    // image. Unknown application sections are silently discarded by it.
    $configFiles = glob('/var/www/snappymail/snappymail/v/*/app/libraries/RainLoop/Config/AbstractConfig.php');
    if ($configFiles && is_file('/data/_data_/_default_/configs/application.ini')) {
        define('APP_PRIVATE_DATA', '/data/_data_/_default_/');
        require $configFiles[0];
        $config = new class('application.ini') extends \RainLoop\Config\AbstractConfig {
            protected function defaultValues(): array { return []; }
        };
        check($config->Load(), 'Generated SnappyMail configuration could not be read');
        check(str_ends_with($config->Get('custom', 'mailu_carddav_url', ''), '/webdav/'),
              'Upstream config reader discarded the public DAV URL');
        check(str_contains($config->Get('custom', 'mailu_carddav_internal_url', ''), 'front:8081/webdav/'),
              'Upstream config reader discarded the internal DAV URL');
        echo "Upstream SnappyMail INI reader accepted the plugin settings\n";
    }
}
