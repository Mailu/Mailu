# DKIM key management

Mailu stores DKIM private keys in the admin database. Domain administrators can
view DNS records for signing and staged keys, then promote a staged key when its
DNS record has propagated. Promoting a key enables signing with it. Stopping
signing retires that key so it cannot be promoted again; its DNS record remains
available during the verification overlap period. Delete the retired key only
after mail signed with it can no longer be in transit.

Mailu supports RSA and Ed25519 keys. A selector is derived from the public key,
so each generated key has a stable selector independent of the domain name.
Alternative domains use the same key set as their parent domain. Their DNS
records use the alternative's name.

## API

All endpoints below require a Mailu API bearer token.

List keys for a domain:

```http
GET /api/v1/domain/example.org/dkim
```

Each key includes an `active` flag and a `retired` flag. Retired keys can no
longer be promoted.

Generate a staged key. `algorithm` can be `rsa` or `ed25519` and defaults to
`rsa`:

```http
POST /api/v1/domain/example.org/dkim
Content-Type: application/json

{"algorithm": "ed25519"}
```

Promote a staged key by setting `active` to `true`. Set it to `false` to stop
signing and retire it. A retired key cannot be promoted again:

```http
PATCH /api/v1/domain/example.org/dkim/17
Content-Type: application/json

{"active": true}
```

Delete an inactive key, including its DNS record:

```http
DELETE /api/v1/domain/example.org/dkim/17
```

The equivalent endpoints under `/api/v1/alternative/alias.org/dkim` operate on
the alternative's parent-domain keys. Generating or changing a key through an
alternative therefore affects signing for its parent domain and all its
alternatives. The same PATCH and DELETE operations are available under
`/api/v1/alternative/alias.org/dkim/17`.

## Upgrade from filesystem keys

At admin startup, Mailu imports each existing legacy key into the database,
preserving its configured selector. After the database commit, the original
file is renamed by adding `.bak` to its filename. The backup is retained for
recovery and prevents repeat imports on subsequent startups.
