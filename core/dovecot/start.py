#!/usr/bin/env python3

import os
import glob
import grp
import pwd
import shutil
import stat
import subprocess
import time
import urllib.request

from socrate import system, conf, supervisor
from fts_settings import normalize_languages

log_filters = [
    rb'Error\: SSL context initialization failed, disabling SSL\: Couldn\'t initialize SSL server context\: Can\'t load SSL certificate \(ssl_server_cert_file setting\)\: The certificate is empty$',
]
env = system.set_env()

# Actual startup script
fts_languages = normalize_languages(env.get("FULL_TEXT_SEARCH", "en"))
context = dict(
    os.environ,
    FULL_TEXT_SEARCH=fts_languages,
    FULL_TEXT_SEARCH_ENABLED=fts_languages != "off",
    FULL_TEXT_SEARCH_ATTACHMENTS=system.parse_bool(env.get("FULL_TEXT_SEARCH_ATTACHMENTS"), False),
)
def wait_for_tika():
    if not context["FULL_TEXT_SEARCH_ENABLED"] or not context["FULL_TEXT_SEARCH_ATTACHMENTS"]:
        return
    address = context.get("FTS_ATTACHMENTS_ADDRESS", "fts_attachments")
    url = f"http://{address}:9998/tika"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=3):
                return
        except Exception as error:
            print(f"Waiting for Tika at {url} before mailbox migration/indexing: {error}", flush=True)
            time.sleep(5)


for dovecot_file in glob.glob("/conf/*.conf"):
    conf.jinja(dovecot_file, context, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))
conf.jinja("/conf/login.lua", context, "/etc/dovecot/login.lua")

os.makedirs("/conf/bin", exist_ok=True)
for script_file in glob.glob("/conf/*.script"):
    out_file = os.path.join("/conf/bin/", os.path.basename(script_file).replace('.script',''))
    conf.jinja(script_file, context, out_file)
    os.chmod(out_file, 0o555)
for sieve_file in glob.glob("/conf/report-*.sieve"):
    subprocess.run(["sievec", sieve_file], check=True)

supervisor.clean_environment()

# Run Podop, then postfix
os.system("chown mail:mail /mail")
os.system("chown -R mail:mail /var/lib/dovecot /conf")

# Keep chroot runtime dependencies in one ephemeral mount at the standard
# /usr path. The mailbox chroot can then use native /usr/... paths without
# links back into the persistent mailbox volume.
runtime_root = "/mail/usr"
if not os.path.ismount(runtime_root):
    raise RuntimeError(
        f"{runtime_root} must be mounted as tmpfs by the Compose configuration"
    )
os.chown(runtime_root, 0, 0)
os.chmod(runtime_root, 0o755)
for runtime_name in (
    "share/mailu/sieve",
    "lib/dovecot/sieve",
    "run/dovecot",
    "run/podop",
):
    runtime_path = os.path.join(runtime_root, runtime_name)
    os.makedirs(runtime_path, mode=0o755, exist_ok=True)
    os.chown(runtime_path, 0, 0)
    os.chmod(runtime_path, 0o755)

runtime_private_dir = os.path.join(runtime_root, "run/podop")
os.makedirs(runtime_private_dir, mode=0o710, exist_ok=True)
os.chown(
    runtime_private_dir,
    pwd.getpwnam("mail").pw_uid,
    grp.getgrnam("dovecot-proxy").gr_gid,
)
os.chmod(runtime_private_dir, 0o710)

# libc always reads /etc/resolv.conf relative to the chroot root. Keep these
# small generated files in place directly; they cannot be redirected through
# Dovecot's configurable paths.
resolver_dir = "/mail/etc"
os.makedirs(resolver_dir, mode=0o755, exist_ok=True)
os.chown(resolver_dir, 0, 0)
os.chmod(resolver_dir, 0o755)
chroot_groups = {"root", "mail", "dovecot", "dovecot-proxy"}
with open("/etc/group", encoding="utf-8") as source, open(
    os.path.join(resolver_dir, "group"), "w", encoding="utf-8"
) as target:
    target.writelines(
        line for line in source if line.split(":", 1)[0] in chroot_groups
    )
os.chown(os.path.join(resolver_dir, "group"), 0, 0)
os.chmod(os.path.join(resolver_dir, "group"), 0o644)
resolver_config = os.path.join(resolver_dir, "resolv.conf")
shutil.copy2("/etc/resolv.conf", resolver_config)
os.chown(resolver_config, 0, 0)
os.chmod(resolver_config, 0o644)


# Auth workers use /run/dovecot/dns-client outside their chroot, while chrooted
# mail processes see the same socket at /run/dovecot/dns-client inside /mail.
# This socket directory lives on the mailbox volume, so remove only stale
# sockets from a previous container start.
mail_dns_runtime_dir = "/mail/run/dovecot"
os.makedirs(mail_dns_runtime_dir, mode=0o755, exist_ok=True)
os.chown(mail_dns_runtime_dir, 0, 0)
os.chmod(mail_dns_runtime_dir, 0o755)
mail_dns_socket = os.path.join(mail_dns_runtime_dir, "dns-client")
try:
    if stat.S_ISSOCK(os.lstat(mail_dns_socket).st_mode):
        os.unlink(mail_dns_socket)
    else:
        raise RuntimeError(f"Unexpected non-socket at {mail_dns_socket}")
except FileNotFoundError:
    pass

# Mail processes are chrooted into /mail. Keep the Sieve modules and global
# scripts they need available inside that chroot without exposing the rest of
# the image filesystem.
proxy_gid = grp.getgrnam("dovecot-proxy").gr_gid
for chroot_name, source_pattern in (
    ("lib/dovecot/sieve", "/usr/lib/dovecot/sieve/*.so"),
    ("share/mailu/sieve", "/conf/report-*.sieve"),
):
    chroot_path = os.path.join(runtime_root, chroot_name)
    os.makedirs(chroot_path, mode=0o750, exist_ok=True)
    os.chown(chroot_path, 0, proxy_gid)
    os.chmod(chroot_path, 0o750)
    sources = glob.glob(source_pattern)
    if not sources:
        raise RuntimeError(f"No files found for chroot runtime assets: {source_pattern}")
    for source in sources:
        target = os.path.join(chroot_path, os.path.basename(source))
        shutil.copy2(source, target)
        os.chown(target, 0, proxy_gid)
        os.chmod(target, 0o640)

if context["FULL_TEXT_SEARCH_ENABLED"]:
    # FTS language filters load these files after the mail worker has chrooted
    # into /mail. Keep the ICU data and stopword lists available in tmpfs.
    fts_runtime_assets = glob.glob("/usr/share/icu/*/icudt*.dat") + glob.glob(
        "/usr/share/dovecot/stopwords/*.txt"
    )
    if not any("/icu/" in source for source in fts_runtime_assets):
        raise RuntimeError("FTS is enabled, but the ICU data file is missing")
    if not any("/stopwords/" in source for source in fts_runtime_assets):
        raise RuntimeError("FTS is enabled, but the stopword files are missing")
    print(f"Staging {len(fts_runtime_assets)} FTS language assets into /mail/usr", flush=True)
    for source in fts_runtime_assets:
        relative_path = os.path.relpath(source, "/usr/share")
        target = os.path.join(runtime_root, "share", relative_path)
        os.makedirs(os.path.dirname(target), mode=0o755, exist_ok=True)
        shutil.copy2(source, target)
        os.chown(target, 0, 0)
        os.chmod(target, 0o644)

for source in glob.glob("/conf/report-*.svbin"):
    target = os.path.join(runtime_root, "share/mailu/sieve", os.path.basename(source))
    shutil.copy2(source, target)
    os.chown(target, 0, proxy_gid)
    os.chmod(target, 0o640)

# Keep execute sockets below the mailbox chroot. Dovecot resolves service
# listeners relative to base_dir, while mail processes see these as /usr/run
# after chrooting.
mail_runtime_dir = os.path.join(runtime_root, "run/dovecot")
os.makedirs(mail_runtime_dir, mode=0o755, exist_ok=True)
os.chown(mail_runtime_dir, 0, 0)
os.chmod(mail_runtime_dir, 0o755)
token_login_runtime_dir = os.path.join(mail_runtime_dir, "token-login")
os.makedirs(token_login_runtime_dir, mode=0o750, exist_ok=True)
os.chown(token_login_runtime_dir, 0, proxy_gid)
os.chmod(token_login_runtime_dir, 0o750)
execute_socket_dir = os.path.join(mail_runtime_dir, "sieve-execute")
os.makedirs(execute_socket_dir, mode=0o710, exist_ok=True)
os.chown(execute_socket_dir, 0, proxy_gid)
os.chmod(execute_socket_dir, 0o710)
for name in ("spam", "ham"):
    stale_socket = os.path.join(execute_socket_dir, name)
    try:
        if stat.S_ISSOCK(os.lstat(stale_socket).st_mode):
            os.unlink(stale_socket)
    except FileNotFoundError:
        pass

# Migrate persistent mailbox data before Dovecot starts serving requests.
subprocess.run(["python3", "/migrate_mail.py"], check=True)
if os.path.exists("/mail/.fts-rebuild-pending"):
    wait_for_tika()

programs = [
    {"name": "podop", "command": ["python3", "-m", "podop.run_server", "dovecot"], "priority": 10},
    {"name": "dovecot", "command": ["/usr/sbin/dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"], "log_filters": log_filters, "priority": 20},
]
programs.append({
    "name": "mail-index-rebuild",
    "command": ["python3", "/rebuild_fts.py"],
    "priority": 30,
    "autorestart": False,
    "startsecs": 0,
    "startretries": 0,
})
supervisor.start(programs)
