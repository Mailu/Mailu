#!/usr/bin/env python3

import os
import logging as log
import sys
from socrate import system, conf

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
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

args = system.set_env()
log.basicConfig(stream=sys.stderr, level=args.get("LOG_LEVEL", "WARNING"))

args['TLS_PERMISSIVE'] = str(args.get('TLS_PERMISSIVE')).lower() not in ('false', 'no')

# Get the first DNS server
with open("/etc/resolv.conf") as handle:
    content = handle.read().split()
    resolver = content[content.index("nameserver") + 1]
    args["RESOLVER"] = f"[{resolver}]" if ":" in resolver else resolver

# Configure PROXY_PROTOCOL
PROTO_MAIL=['25', '110', '995', '143', '993', '587', '465', '4190']
PROTO_ALL_BUT_HTTP=PROTO_MAIL.copy()
PROTO_ALL_BUT_HTTP.extend(['443'])
PROTO_ALL=PROTO_ALL_BUT_HTTP.copy()
PROTO_ALL.extend(['80'])
for item in args.get('PROXY_PROTOCOL', '').split(','):
    if item.isdigit():
        args[f'PROXY_PROTOCOL_{item}']=True
    elif item == 'mail':
        for p in PROTO_MAIL: args[f'PROXY_PROTOCOL_{p}']=True
    elif item == 'all-but-http':
        for p in PROTO_ALL_BUT_HTTP: args[f'PROXY_PROTOCOL_{p}']=True
    elif item == 'all':
        for p in PROTO_ALL: args[f'PROXY_PROTOCOL_{p}']=True
    else:
        log.error(f'Not sure what to do with {item} in PROXY_PROTOCOL ({args.get("PROXY_PROTOCOL")})')

PORTS_REQUIRING_TLS=['443', '465', '993', '995']
ALL_PORTS='25,80,443,465,587,993,995,4190'
for item in args.get('PORTS', ALL_PORTS).split(','):
    if item in PORTS_REQUIRING_TLS and args['TLS_FLAVOR'] == 'notls':
        continue
    args[f'PORT_{item}']=True

if args['TLS_FLAVOR'] != 'notls':
    for item in args.get('TLS', ALL_PORTS).split(','):
        if item in PORTS_REQUIRING_TLS:
            args[f'TLS_{item}']=True

# TLS configuration
cert_name = args.get("TLS_CERT_FILENAME", "cert.pem")
keypair_name = args.get("TLS_KEYPAIR_FILENAME", "key.pem")
args["TLS"] = {
    "cert": ("/certs/%s" % cert_name, "/certs/%s" % keypair_name),
    "letsencrypt": ("/certs/letsencrypt/live/mailu/nginx-chain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem", "/certs/letsencrypt/live/mailu-ecdsa/nginx-chain.pem", "/certs/letsencrypt/live/mailu-ecdsa/privkey.pem"),
    "mail": ("/certs/%s" % cert_name, "/certs/%s" % keypair_name),
    "mail-letsencrypt": ("/certs/letsencrypt/live/mailu/nginx-chain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem", "/certs/letsencrypt/live/mailu-ecdsa/nginx-chain.pem", "/certs/letsencrypt/live/mailu-ecdsa/privkey.pem"),
    "notls": None
}[args["TLS_FLAVOR"]]

def format_for_nginx(fullchain, output, strip_CA=args.get('LETSENCRYPT_SHORTCHAIN')):
    """ We may want to strip ISRG Root X1 out """
    if not os.path.exists(fullchain):
        return
    chain=[]
    with open(fullchain, 'rb') as f:
        chain = x509.load_pem_x509_certificates(f.read())
    builder = PolicyBuilder().store(Store([ISRG_ROOT_X1, ISRG_ROOT_X2]))
    verifier = builder.build_server_verifier(DNSName(chain[0].subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value))
    try:
        valid_chain = verifier.verify(chain[0], chain[1:])
    except Exception as e:
        log.error(e)
        valid_chain = chain
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
    if not has_found_PIN:
        log.error('Neither ISRG X1 nor ISRG X2 have been found in the certificate chain. Please check your DANE records.')
    with open(output, 'wt') as f:
        for cert in valid_chain:
            if strip_CA and (cert.subject.rfc4514_string() in ['CN=ISRG Root X1,O=Internet Security Research Group,C=US', 'CN=ISRG Root X2,O=Internet Security Research Group,C=US']):
                continue
            f.write(f'{cert.public_bytes(encoding=Encoding.PEM).decode("ascii").strip()}\n')

if args['TLS_FLAVOR'] in ['letsencrypt', 'mail-letsencrypt']:
    format_for_nginx('/certs/letsencrypt/live/mailu/fullchain.pem', '/certs/letsencrypt/live/mailu/nginx-chain.pem')
    format_for_nginx('/certs/letsencrypt/live/mailu/fullchain.pem', '/certs/letsencrypt/live/mailu/DANE-chain.pem', False)
    format_for_nginx('/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem', '/certs/letsencrypt/live/mailu-ecdsa/nginx-chain.pem')
    format_for_nginx('/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem', '/certs/letsencrypt/live/mailu-ecdsa/DANE-chain.pem', False)

if args["TLS"] and not all(os.path.exists(file_path) for file_path in args["TLS"]):
    print("Missing cert or key file, disabling TLS")
    args["TLS_ERROR"] = "yes"

args['TLS_PERMISSIVE'] = str(args.get('TLS_PERMISSIVE')).lower() not in ('false', 'no')

# Build final configuration paths
conf.jinja("/conf/tls.conf", args, "/etc/nginx/tls.conf")
conf.jinja("/conf/proxy.conf", args, "/etc/nginx/proxy.conf")
conf.jinja("/conf/nginx.conf", args, "/etc/nginx/nginx.conf")
conf.jinja("/dovecot_conf/login.lua", args, "/etc/dovecot/login.lua")
conf.jinja("/dovecot_conf/proxy.conf", args, "/etc/dovecot/proxy.conf")
os.system("killall -q -HUP nginx dovecot")
