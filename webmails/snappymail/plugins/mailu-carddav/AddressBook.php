<?php

namespace Mailu;

class AddressBook extends \RainLoop\Providers\AddressBook\PdoAddressBook
{
    private ?array $mailuConfig = null;
    private bool $syncing = false;

    public function __construct(
        private string $email, private string $publicUrl, private string $internalUrl,
        private string $storageEmail
    ) {
        parent::__construct();
    }

    public function setDAVClientConfig(?array $config)
    {
        $this->mailuConfig = null;
        // Keep the public URL in user preferences. Only requests for this
        // account's Mailu service travel through the internal listener.
        if ($config && ($config['Url'] ?? '') === $this->publicUrl
            && ($config['User'] ?? '') === $this->email) {
            $config['Url'] = $this->internalUrl;
            $this->mailuConfig = $config;
        }
        parent::setDAVClientConfig($config);
    }

    public function getDavClient(): ?\SnappyMail\DAV\Client
    {
        if ($this->mailuConfig === null) {
            return parent::getDavClient();
        }
        if (empty($this->mailuConfig['Mode'])) {
            return null;
        }
        $this->logMask($this->mailuConfig['Password']);
        $client = new \SnappyMail\DAV\Client([
            'baseUri' => $this->internalUrl,
            'userName' => $this->email,
            'password' => $this->mailuConfig['Password'],
        ]);
        $client->setVerifyPeer(false);
        $principal = rtrim(parse_url($this->internalUrl, PHP_URL_PATH), '/')
            . '/' . rawurlencode($this->storageEmail) . '/';
        // SnappyMail's generic discovery treats a home containing an address
        // book as the book itself. Select an actual collection for Mailu.
        $resources = $client->propFind($principal, ['{DAV:}resourcetype'], 1);
        $books = [];
        foreach ($resources as $path => $properties) {
            if (str_starts_with($path, $principal)
                && in_array('{urn:ietf:params:xml:ns:carddav}addressbook',
                            $properties['{DAV:}resourcetype'] ?? [], true)) {
                $books[] = $path;
            }
        }
        if (!$books) {
            throw new \RuntimeException('No Mailu address book is available');
        }
        $default = $principal . 'contacts/';
        $client->urlPath = in_array($default, $books, true) ? $default : $books[0];
        return $client;
    }

    public function Sync(): bool
    {
        $this->syncing = true;
        try {
            return parent::Sync();
        } finally {
            $this->syncing = false;
        }
    }

    public function ContactSave(\RainLoop\Providers\AddressBook\Classes\Contact $contact): bool
    {
        if ($this->mailuConfig !== null && !$this->syncing && $contact->id !== '') {
            // Upstream casts loaded ETags to integers. Hashes beginning with
            // a letter become zero, so its sync engine misses local edits.
            // Mark edits to previously synced records with a nonempty dirty
            // ETag; imports keep the ETag returned by the DAV server.
            $statement = $this->prepareAndExecute(
                'SELECT etag FROM rainloop_ab_contacts WHERE id_contact = :id',
                [':id' => [$contact->id, \PDO::PARAM_INT]]
            );
            $etag = $statement ? $statement->fetchColumn() : '';
            $contact->Etag = $etag !== false && $etag !== '' ? 'mailu-local-change' : '';
        }
        return parent::ContactSave($contact);
    }

    protected function davClientRequest(\SnappyMail\DAV\Client $client, string $method,
        string $url, mixed $data = null): ?\SnappyMail\HTTP\Response
    {
        if ($this->mailuConfig !== null && $method === 'PUT') {
            // SnappyMail uses the resource's filename as its local UID. DAV
            // permits arbitrary filenames, and Radicale correctly rejects
            // changes to an existing vCard's UID. Preserve it on updates.
            try {
                $existing = $client->request('GET', $url);
                $original = \Sabre\VObject\Reader::read($existing->body);
                $card = \Sabre\VObject\Reader::read($data);
                $card->UID = (string) $original->UID;
                $data = $card->serialize();
            } catch (\SnappyMail\HTTP\Exception $error) {
                if ($error->getCode() !== 404) {
                    throw $error;
                }
            }
        }
        return parent::davClientRequest($client, $method, $url, $data);
    }
}
