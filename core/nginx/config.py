#!/usr/bin/env python3

import os
import logging as log
import subprocess
import sys
from socrate import system, conf

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key
from cryptography.x509.verification import PolicyBuilder, Store, DNSName
from cryptography.x509.oid import NameOID
import hashlib

ISRG_ROOT_X1 = x509.load_pem_x509_certificate(b'''-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
''')
ISRG_ROOT_X2 = x509.load_pem_x509_certificate(b'''-----BEGIN CERTIFICATE-----
MIICGzCCAaGgAwIBAgIQQdKd0XLq7qeAwSxs6S+HUjAKBggqhkjOPQQDAzBPMQsw
CQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJuZXQgU2VjdXJpdHkgUmVzZWFyY2gg
R3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBYMjAeFw0yMDA5MDQwMDAwMDBaFw00
MDA5MTcxNjAwMDBaME8xCzAJBgNVBAYTAlVTMSkwJwYDVQQKEyBJbnRlcm5ldCBT
ZWN1cml0eSBSZXNlYXJjaCBHcm91cDEVMBMGA1UEAxMMSVNSRyBSb290IFgyMHYw
EAYHKoZIzj0CAQYFK4EEACIDYgAEzZvVn4CDCuwJSvMWSj5cz3es3mcFDR0HttwW
+1qLFNvicWDEukWVEYmO6gbf9yoWHKS5xcUy4APgHoIYOIvXRdgKam7mAHf7AlF9
ItgKbppbd9/w+kHsOdx1ymgHDB/qo0IwQDAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0T
AQH/BAUwAwEB/zAdBgNVHQ4EFgQUfEKWrt5LSDv6kviejM9ti6lyN5UwCgYIKoZI
zj0EAwMDaAAwZQIwe3lORlCEwkSHRhtFcP9Ymd70/aTSVaYgLXTWNLxBo1BfASdW
tL4ndQavEi51mI38AjEAi/V3bNTIZargCyzuFJ0nN6T5U6VR5CmD1/iQMVtCnwr1
/q4AaOeMSQ+2b1tbFfLn
-----END CERTIFICATE-----
''')

ISRG_ROOT_YE = x509.load_pem_x509_certificate(b'''-----BEGIN CERTIFICATE-----
MIIB2TCCAWCgAwIBAgIRAKQCa6LvbHwg1AR+XmWmk4AwCgYIKoZIzj0EAwMwLjEL
MAkGA1UEBhMCVVMxDTALBgNVBAoTBElTUkcxEDAOBgNVBAMTB1Jvb3QgWUUwHhcN
MjUwOTAzMDAwMDAwWhcNNDUwOTAyMjM1OTU5WjAuMQswCQYDVQQGEwJVUzENMAsG
A1UEChMESVNSRzEQMA4GA1UEAxMHUm9vdCBZRTB2MBAGByqGSM49AgEGBSuBBAAi
A2IABDwS/6vhrcVqcbBo+wgdI3fwn9x7DNJJOY/lTOti0vkwuRN87RhEhTH17E7X
yFjWsPYhIPt/wzOqxTd2b+4ZJNy9ID04YywF9U5zasDVyGSNErVNtz8uSGh5izW8
7j77GaNCMEAwDgYDVR0PAQH/BAQDAgEGMA8GA1UdEwEB/wQFMAMBAf8wHQYDVR0O
BBYEFKPIJlqOoUzQNWP8myPIOq5W809WMAoGCCqGSM49BAMDA2cAMGQCMHhMr8N9
LdL1VQKs9BdV81r76eXRB6mtjuNjzk6/lBsPNToWLTDzGYgtQKO1jl63uAIwGV7m
onyF377c+MM1oqVNs17sgu7F9YKZwgLmVbeOMDbKAXHtKMDLbiGllCcs8f47
-----END CERTIFICATE-----
''')

ISRG_ROOT_YR = x509.load_pem_x509_certificate(b'''-----BEGIN CERTIFICATE-----
MIIFKTCCAxGgAwIBAgIRAOxGNJNgz0sP+KmC2Tqpyj0wDQYJKoZIhvcNAQELBQAw
LjELMAkGA1UEBhMCVVMxDTALBgNVBAoTBElTUkcxEDAOBgNVBAMTB1Jvb3QgWVIw
HhcNMjUwOTAzMDAwMDAwWhcNNDUwOTAyMjM1OTU5WjAuMQswCQYDVQQGEwJVUzEN
MAsGA1UEChMESVNSRzEQMA4GA1UEAxMHUm9vdCBZUjCCAiIwDQYJKoZIhvcNAQEB
BQADggIPADCCAgoCggIBANvGJnN78CTJdWL3+eGfsLN5TrNBJs+VH9hRXqRbwxu9
sGNiB0BD1fcOxbSUQCJIM1xE13Db+5Cw1w0s0EBYsvuIP/6joF0w8cuImbgR1OGg
YbSQ4OpzI+DG8SGuTlcE873OCS+kh3srlo6vl43M5OJg4Aeo1sfHp6kTJDoIiFBN
JAY+OKfX/FUvYKuhjT+no49lmqmupSBI5PkBQiqrEGtWU5uxU/cQWHGu8jSjFBzn
ZqvbNPLMXMLFxCb3WTfrJBXXjqvWG+v4bjzxjjeAtOlU7qarRDvNOyAuQYLln904
M+faKx8hnLCpJ15ZqaEgcNlY+9MMWcC5yvL2A2j3l9+2buggZX+dOE91zYmIdawT
vSZuVvlbRrAlLxIB6pwMBjneXCjYQ8+3BCCjssbSNpZU3hTcBDdhfAlEDlYr6pEa
tnMdmDT5BqnKC92bd0EhM1fbLHioLccLCuievT8ZkPhZrq7Mii7gNXAcUEAR8+lz
Yal+9zTg7C5DALyVOeG/CqfRAMn1KSHCR0NSA6P8tn/mGRlnCct5rtVCLnVySVpU
6H1qGg3DgTOuskf8eahTMiYbI5ezPJmO5ertalskQ1utp74+eDy92PI4ftHKTbq9
IWhH4YZKh3WnJEIt+oQvlYZbY8tpEroKrFB6PFGzrJIDRyts4HqvuH52RFj2zv/B
AgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNVHRMBAf8EBTADAQH/MB0GA1Ud
DgQWBBTe51tg0CJtQCh9Pw0B/qS1UrRRlDANBgkqhkiG9w0BAQsFAAOCAgEAWHnf
713Bdkq7t5yN2dNIgQakUb94X9WuyhMEHHkgx4oDpSUlnG0w4g94MoqaEUE31ZjR
LU7L5LD1g9ujFHTQu8AD215AHMVQFbm6j8hQxdXHAzDajFNQnOlDJrLjzIx176oy
AjvUtejZx2NNmdb5fd0WGVGsCdoAJ3N8ozo7ajE8t6vfxStZb4BQ9WYJGHUDrv2N
i5tJF6CNiPnlzs3BUfECRbE4JSk+jvy8+VoGiFE8qsH/j78x2fjgQhAQFV7P7Zxy
dBTZ1wEkNpZNW2qnaK1SKBLa+xf6E06YRIq5uaI+HWH8SY1y5VbRgzq40EKg3yxP
06fz+uYAUIFJoLNfhwRCc3Q6pQVuMX3yAjHAes4gk4moGcLQ5p7HAh39yeylZc1J
41sx/jKwLIkPE6Rr1Nf4pxdsxf9SA4yOEiAkDgq04DVxn8hgYFdUtBCuiuVC2heA
EiqVEa+8QZjuw8Gj0EbHXcRd1nInvGqRS1o9Is7YBdQN57X1AYveGBNNqjICSb7c
awuw1EawTDrs13VUlJVEsbQ0/O/1aaV73mCdOQ8azqL2KTv1Ewu1xbquE2S+kdQU
To9TUwat3wUA6cwXh1EfpS/3fJ0aGah5hdpRyoCLDlsSn8tkrjMfFFX0viC+GxHc
sI1ANRYvqSFC2X1VRZfDg+wD6E21BccmifG4yWc=
-----END CERTIFICATE-----
''')

args = system.set_env(cleanup_pids=False)
log.basicConfig(stream=sys.stderr, level=args.get("LOG_LEVEL", "WARNING"))
bootstrap = "--bootstrap" in sys.argv

args['TLS_PERMISSIVE'] = str(args.get('TLS_PERMISSIVE')).lower() not in ('false', 'no')

# Get the first DNS server
with open("/etc/resolv.conf") as handle:
    content = handle.read().split()
    resolver = content[content.index("nameserver") + 1]
    args["RESOLVER"] = f"[{resolver}]" if ":" in resolver else resolver

# TLS configuration
cert_name = args.get("TLS_CERT_FILENAME", "cert.pem")
keypair_name = args.get("TLS_KEYPAIR_FILENAME", "key.pem")
args["TLS"] = {
    "cert": ("/certs/%s" % cert_name, "/certs/%s" % keypair_name),
    "letsencrypt": ("/certs/letsencrypt/live/mailu/fullchain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem", "/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem", "/certs/letsencrypt/live/mailu-ecdsa/privkey.pem"),
    "mail": ("/certs/%s" % cert_name, "/certs/%s" % keypair_name),
    "mail-letsencrypt": ("/certs/letsencrypt/live/mailu/fullchain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem", "/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem", "/certs/letsencrypt/live/mailu-ecdsa/privkey.pem"),
    "notls": None
}[args["TLS_FLAVOR"]]

def validate_keypair(fullchain, private_key):
    if not os.path.exists(fullchain) or not os.path.exists(private_key):
        return
    with open(fullchain, 'rb') as chain_file:
        certificate = x509.load_pem_x509_certificates(chain_file.read())[0]
    with open(private_key, 'rb') as key_file:
        key = load_pem_private_key(key_file.read(), password=None)
    certificate_key = certificate.public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    )
    private_public_key = key.public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    )
    if certificate_key != private_public_key:
        raise ValueError(f'Private key does not match {fullchain}')


def format_for_dane(fullchain, output):
    """Build a validated chain containing a DNS-published trust anchor."""
    if not os.path.exists(fullchain):
        return
    chain=[]
    with open(fullchain, 'rb') as f:
        chain = x509.load_pem_x509_certificates(f.read())
    builder = PolicyBuilder().store(Store([ISRG_ROOT_X1, ISRG_ROOT_X2, ISRG_ROOT_YE, ISRG_ROOT_YR]))

    verifier = builder.build_server_verifier(DNSName(chain[0].subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value))
    valid_chain = verifier.verify(chain[0], chain[1:])
    log.info(f'The certificate chain looks as follows for {fullchain}:')
    indent = '  '
    has_found_PIN = False
    for cert in valid_chain:
        pubkey_der = cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        digest = hashlib.sha256(pubkey_der).hexdigest()
        log.info(f'{indent}{cert.subject.rfc4514_string()} {digest}')
        indent += '  '
        if digest == '0b9fa5a59eed715c26c1020c711b4f6ec42d58b0015e14337a39dad301c5afc3': # ISRG Root X1
            log.info('ISRG X1 PIN FOUND!')
            has_found_PIN = True
        elif digest == '762195c225586ee6c0237456e2107dc54f1efc21f61a792ebd515913cce68332': # ISRG Root X2
            log.info('ISRG X2 PIN FOUND!')
            has_found_PIN = True
        elif digest == 'b0292ae545978e0fbb98abbd94c861605e5b18bb32ed523f50d5b7b5c71d47bc': # ISRG Root YE
            log.info('ISRG YE PIN FOUND!')
            has_found_PIN = True
        elif digest == '7e4e8838a8add6295de7ae3b047d3aba3488ab95db0a0aa56d897a00d8618bcf': # ISRG Root YR
            log.info('ISRG YR PIN FOUND!')
            has_found_PIN = True
    if not has_found_PIN:
        message = 'No ISRG pin has been found in the certificate chain. Please check your DANE records.'
        log.error(message)
        raise ValueError(message)
    with open(output, 'wt') as f:
        for cert in valid_chain:
            f.write(f'{cert.public_bytes(encoding=Encoding.PEM).decode("ascii").strip()}\n')

if args['TLS_FLAVOR'] in ['letsencrypt', 'mail-letsencrypt']:
    try:
        validate_keypair(
            '/certs/letsencrypt/live/mailu/fullchain.pem',
            '/certs/letsencrypt/live/mailu/privkey.pem',
        )
        validate_keypair(
            '/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem',
            '/certs/letsencrypt/live/mailu-ecdsa/privkey.pem',
        )
        format_for_dane('/certs/letsencrypt/live/mailu/fullchain.pem', '/certs/letsencrypt/live/mailu/DANE-chain.pem')
        format_for_dane('/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem', '/certs/letsencrypt/live/mailu-ecdsa/DANE-chain.pem')
    except Exception:
        if not bootstrap:
            raise
        log.exception('Disabling TLS until valid certificate chains are available')
        args["TLS_ERROR"] = "yes"

if args["TLS"] and not all(os.path.exists(file_path) for file_path in args["TLS"]):
    print("Missing cert or key file, disabling TLS")
    args["TLS_ERROR"] = "yes"
if bootstrap and args.get("TLS_ERROR") and args['TLS_FLAVOR'] in ['letsencrypt', 'mail-letsencrypt']:
    with open("/tmp/mailu-renewal-required", "a"):
        pass
if args.get("TLS_ERROR"):
    args["TLS"] = None

args['TLS_PERMISSIVE'] = str(args.get('TLS_PERMISSIVE')).lower() not in ('false', 'no')

# Build final configuration paths
conf.jinja("/conf/tls.conf", args, "/etc/nginx/tls.conf")
conf.jinja("/conf/proxy.conf", args, "/etc/nginx/proxy.conf")
conf.jinja("/conf/nginx.conf", args, "/etc/nginx/nginx.conf")
conf.jinja("/dovecot_conf/login.lua", args, "/etc/dovecot/login.lua")
conf.jinja("/dovecot_conf/proxy.conf", args, "/etc/dovecot/proxy.conf")
subprocess.run(["nginx", "-t"], check=True)
subprocess.run(
    ["doveconf", "-c", "/etc/dovecot/proxy.conf"],
    check=True,
    stdout=subprocess.DEVNULL,
)
if not bootstrap:
    reload_commands = (
        (["nginx", "-s", "reload"], "/var/run/nginx.pid"),
        (["doveadm", "reload"], "/run/dovecot/master.pid"),
    )
    for _, pid_file in reload_commands:
        if not os.path.exists(pid_file):
            raise RuntimeError(f"Cannot reload service without {pid_file}")
    for command, _ in reload_commands:
        subprocess.run(command, check=True)
