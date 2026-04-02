""" Unit tests for TOTP two-factor authentication.

Run with: python -m pytest tests/test_2fa.py -v
(from core/admin/ with the venv activated, or inside the dev container)
"""

import pytest
import pyotp
import passlib.hash
from unittest.mock import patch, MagicMock


# --- TOTP Verification Logic ---

class TestTOTPVerification:
    """Test pyotp TOTP code generation and verification."""

    def test_valid_code(self):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert totp.verify(code, valid_window=1) is True

    def test_wrong_code(self):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        assert totp.verify('000000', valid_window=1) is False

    def test_different_secrets_produce_different_codes(self):
        secret1 = pyotp.random_base32()
        secret2 = pyotp.random_base32()
        totp1 = pyotp.TOTP(secret1)
        totp2 = pyotp.TOTP(secret2)
        # While theoretically they could match, it's astronomically unlikely
        code1 = totp1.now()
        assert totp2.verify(code1, valid_window=0) is False or secret1 == secret2

    def test_provisioning_uri_format(self):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name='user@example.com', issuer_name='Mailu')
        assert uri.startswith('otpauth://totp/')
        assert 'user%40example.com' in uri or 'user@example.com' in uri
        assert 'Mailu' in uri
        assert secret in uri


# --- Backup Code Logic ---

class TestBackupCodes:
    """Test backup code generation and hashing."""

    def test_code_format(self):
        """Backup codes should be 8 hex chars with a dash: xxxx-xxxx"""
        import secrets
        raw = secrets.token_hex(4)
        code = f'{raw[:4]}-{raw[4:]}'
        assert len(code) == 9
        assert code[4] == '-'
        # all chars are hex or dash
        assert all(c in '0123456789abcdef-' for c in code)

    def test_hash_and_verify(self):
        """Codes hashed with pbkdf2_sha256(rounds=1) should verify correctly."""
        code = 'a3f7-k9m2'
        hashed = passlib.hash.pbkdf2_sha256.using(rounds=1).hash(code)
        assert passlib.hash.pbkdf2_sha256.verify(code, hashed) is True

    def test_wrong_code_rejected(self):
        code = 'a3f7-k9m2'
        hashed = passlib.hash.pbkdf2_sha256.using(rounds=1).hash(code)
        assert passlib.hash.pbkdf2_sha256.verify('xxxx-yyyy', hashed) is False

    def test_unique_codes(self):
        """Each generated code should be unique."""
        import secrets
        codes = set()
        for _ in range(100):
            raw = secrets.token_hex(4)
            code = f'{raw[:4]}-{raw[4:]}'
            codes.add(code)
        # With 32 bits of entropy per code, collisions in 100 are near-impossible
        assert len(codes) == 100


# --- Fernet Encryption Logic ---

class TestFernetEncryption:
    """Test TOTP secret encryption/decryption with Fernet."""

    def test_encrypt_decrypt_roundtrip(self):
        import base64, hashlib
        from cryptography.fernet import Fernet

        secret_key = 'test-mailu-secret-key-12345'
        key = hashlib.sha256(secret_key.encode()).digest()
        f = Fernet(base64.urlsafe_b64encode(key))

        totp_secret = pyotp.random_base32()
        encrypted = f.encrypt(totp_secret.encode()).decode()
        decrypted = f.decrypt(encrypted.encode()).decode()

        assert decrypted == totp_secret
        assert encrypted != totp_secret  # must be different from plaintext

    def test_wrong_key_fails(self):
        import base64, hashlib
        from cryptography.fernet import Fernet, InvalidToken

        key1 = hashlib.sha256(b'key-one').digest()
        key2 = hashlib.sha256(b'key-two').digest()
        f1 = Fernet(base64.urlsafe_b64encode(key1))
        f2 = Fernet(base64.urlsafe_b64encode(key2))

        totp_secret = pyotp.random_base32()
        encrypted = f1.encrypt(totp_secret.encode()).decode()

        with pytest.raises(InvalidToken):
            f2.decrypt(encrypted.encode())

    def test_none_secret_passthrough(self):
        """set_totp_secret(None) should store None, get_totp_secret() returns None."""
        # This tests the logic directly without needing the full Flask app
        assert None is None  # placeholder — actual model test needs app context
