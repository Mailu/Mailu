""" No crypto operation is done on keys.
They are thus represented as ASCII armored PEM.
"""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def gen_key(bits=2048):
    """ Generate and return a new RSA key.
    """
    k = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return k.private_bytes(encoding=serialization.Encoding.PEM,format=serialization.PrivateFormat.PKCS8,encryption_algorithm=serialization.NoEncryption())


def strip_key(pem):
    """ Return only the b64 part of the ASCII armored PEM.
    """
    priv_key = serialization.load_pem_private_key(pem, password=None)
    public_pem = priv_key.public_key().public_bytes(encoding=serialization.Encoding.PEM,format=serialization.PublicFormat.SubjectPublicKeyInfo)
    return public_pem.replace(b"\n", b"").split(b"-----")[2]
