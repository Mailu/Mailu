"""Run inside the test front container, with its disposable certificates."""

import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.request


PID_FILES = (Path("/run/nginx.pid"), Path("/run/dovecot/master.pid"))
original_pids = {path: path.read_text() for path in PID_FILES}
cert_path = Path("/certs") / os.environ.get("TLS_CERT_FILENAME", "cert.pem")
key_path = Path("/certs") / os.environ.get("TLS_KEYPAIR_FILENAME", "key.pem")

# This test uses self-signed certificates and connects only over loopback.
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
tls.check_hostname = False
tls.verify_mode = ssl.CERT_NONE


def check_health():
    for path, pid in original_pids.items():
        assert path.read_text() == pid, f"PID file changed: {path}"
        os.kill(int(pid), 0)
    with urllib.request.urlopen("http://127.0.0.1:10204/health", timeout=3) as response:
        assert response.status == 204


def peer_certificate(port):
    with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
        with tls.wrap_socket(connection, server_hostname="localhost") as secured:
            certificate = secured.getpeercert(binary_form=True)
            if port == 993:
                with secured.makefile("rb") as stream:
                    greeting = stream.readline(4096)
                if not greeting.startswith(b"* OK"):
                    raise OSError(f"Unexpected IMAP greeting: {greeting!r}")
            return certificate


def wait_for_certificate(pem):
    expected = ssl.PEM_cert_to_DER_cert(pem.decode())
    deadline = time.monotonic() + 20
    last_error = "previous certificate still served"
    while time.monotonic() < deadline:
        check_health()
        try:
            if all(peer_certificate(port) == expected for port in (443, 993)):
                return
        except (OSError, ssl.SSLError) as error:
            last_error = str(error)
        time.sleep(0.2)
    raise AssertionError(f"nginx and Dovecot did not both load the new certificate: {last_error}")


check_health()
original_certificate = cert_path.read_bytes()
wait_for_certificate(original_certificate)
for _ in range(3):
    subprocess.run(["/config.py"], check=True, timeout=15)
    wait_for_certificate(original_certificate)
print("PASS: repeated configuration reloads preserve both live PID files", flush=True)

with tempfile.TemporaryDirectory(dir=cert_path.parent) as directory:
    replacement = Path(directory) / "replacement.pem"
    try:
        for serial, atomic in enumerate((True, False, True, False), start=2001):
            subprocess.run([
                "openssl", "req", "-new", "-x509", "-key", str(key_path),
                "-subj", "/CN=localhost", "-days", "1", "-set_serial", str(serial),
                "-out", str(replacement),
            ], check=True, timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            pem = replacement.read_bytes()
            if atomic:
                shutil.copymode(cert_path, replacement)
                os.replace(replacement, cert_path)
            else:
                # Exercise FileModifiedEvent after the reconfiguration path.
                cert_path.write_bytes(pem)
            wait_for_certificate(pem)
            operation = "atomic replacement" if atomic else "in-place modification"
            print(f"PASS: {operation} {serial}, HTTPS/IMAPS and PID files", flush=True)
    finally:
        replacement.write_bytes(original_certificate)
        shutil.copymode(cert_path, replacement)
        os.replace(replacement, cert_path)
        wait_for_certificate(original_certificate)
print("PASS: original certificate restored and health check passes", flush=True)
