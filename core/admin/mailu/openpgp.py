"""OpenPGP public-key validation and WKD export helpers."""

from email.utils import parseaddr
import tempfile

import gnupg
import idna


GPG_BINARY = '/usr/bin/gpg'
MAX_KEY_SIZE = 65536


def _decode_gpg_text(value):
    """Undo python-gnupg's byte-wise escape decoding for UTF-8 UIDs."""
    try:
        return value.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def _normalize_email(email):
    localpart, domain = email.rsplit('@', 1)
    return f'{localpart.lower()}@{idna.decode(idna.encode(domain.lower())).lower()}'


def _key_uids(key):
    return {
        _normalize_email(email_address): email_address
        for email_address in (_decode_gpg_text(parseaddr(uid)[1]) for uid in key.get('uids', []))
        if email_address and '@' in email_address
    }


def _export_binary_key(gpg, fingerprint, email):
    previous_options = gpg.options
    gpg.options = [*(previous_options or []), '--export-filter', f'keep-uid=mbox = {email}']
    try:
        return gpg.export_keys(fingerprint, armor=False) or None
    finally:
        gpg.options = previous_options


def parse_public_key(key_data, required_email, authorize_addresses=None):
    """Validate a key, then return public armor and UID-filtered binary exports."""
    if (not key_data or len(key_data) > MAX_KEY_SIZE
            or not key_data.startswith('-----BEGIN PGP PUBLIC KEY BLOCK-----')):
        return None, []
    try:
        with tempfile.TemporaryDirectory(prefix='mailu-openpgp-') as gnupghome:
            gpg = gnupg.GPG(gpgbinary=GPG_BINARY, gnupghome=gnupghome)
            imported = gpg.import_keys(key_data)
            if imported.returncode != 0 or not imported.fingerprints or imported.sec_read:
                return None, []
            keys = [key for key in gpg.list_keys()
                if key.get('fingerprint') in imported.fingerprints]
            target_email = _normalize_email(required_email)
            owned = [key for key in keys if target_email in _key_uids(key)]
            if not owned:
                return None, []

            key_uids = {key['fingerprint']: _key_uids(key) for key in owned}
            addresses = set().union(*(uids.keys() for uids in key_uids.values()))
            if authorize_addresses is not None:
                addresses &= authorize_addresses(addresses)

            fingerprints = [key['fingerprint'] for key in owned]
            public_key = gpg.export_keys(fingerprints, armor=True, minimal=True)
            uid_keys = {}
            for key in owned:
                for normalized_email, uid_email in key_uids[key['fingerprint']].items():
                    if normalized_email not in addresses:
                        continue
                    data = _export_binary_key(gpg, key['fingerprint'], uid_email)
                    if data:
                        uid_keys[(normalized_email, key['fingerprint'])] = data
            if not public_key or not any(email == target_email for email, _ in uid_keys):
                return None, []
            return public_key, [
                (email, fingerprint, data)
                for (email, fingerprint), data in uid_keys.items()
            ]
    except (OSError, ValueError):
        return None, []
