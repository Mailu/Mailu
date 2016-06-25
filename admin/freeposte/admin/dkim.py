""" No crypto operation is done on keys.
They are thus represented as ASCII armored PEM.
"""

from OpenSSL import crypto


def gen_key(key_type=crypto.TYPE_RSA, bits=1024):
    """ Generate and return a new RSA key.
    """
    key = crypto.PKey()
    key.generate_key(key_type, bits)
    return crypto.dump_privatekey(crypto.FILETYPE_PEM, key)


def strip_key(pem):
    """ Return only the b64 part of the ASCII armored PEM.
    """
    key = crypto.load_privatekey(crypto.FILETYPE_PEM, pem)
    public_pem = crypto.dump_publickey(crypto.FILETYPE_PEM, key)
    return public_pem.replace(b"\n", b"").split(b"-----")[2]
