""" No crypto operation is done on keys.
They are thus represented as ASCII armored PEM.
"""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64
import hashlib


def gen_key(bits=2048):
    """ Generate and return a new RSA key.
    """
    k = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return k.private_bytes(encoding=serialization.Encoding.PEM,format=serialization.PrivateFormat.PKCS8,encryption_algorithm=serialization.NoEncryption())


def gen_ed25519_key():
    """Generate a DKIM Ed25519 private key in PKCS8 PEM format."""
    key = Ed25519PrivateKey.generate()
    return key.private_bytes(encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption())


def strip_key(pem):
    """ Return only the b64 part of the ASCII armored PEM.
    """
    priv_key = serialization.load_pem_private_key(pem, password=None)
    public_pem = priv_key.public_key().public_bytes(encoding=serialization.Encoding.PEM,format=serialization.PublicFormat.SubjectPublicKeyInfo)
    return public_pem.replace(b"\n", b"").split(b"-----")[2]


def public_key(pem, algorithm):
    """Return the public key material used by a DKIM DNS record."""
    key = serialization.load_pem_private_key(pem, password=None).public_key()
    if algorithm == 'ed25519':
        raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return base64.b64encode(raw).decode('ascii')
    return strip_key(pem).decode('ascii')


def selector(pem, algorithm):
    """A short, stable selector derived from the public key fingerprint."""
    public = public_key(pem, algorithm).encode('ascii')
    return hashlib.sha256(public).hexdigest()[:12]
