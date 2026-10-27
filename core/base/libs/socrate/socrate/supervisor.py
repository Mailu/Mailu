"""Small helpers for running container processes under supervisord."""

import os
import shlex
import sys
import base64
import secrets


SUPERVISOR_CONFIG = "/etc/supervisord.conf"
SUPERVISOR_RUNTIME_DIR = "/run/mailu-supervisor"
SUPERVISOR_PID = SUPERVISOR_RUNTIME_DIR + "/supervisord.pid"
SUPERVISOR_SOCKET = SUPERVISOR_RUNTIME_DIR + "/supervisor.sock"


def _is_sensitive(name):
    name = name.upper()
    if name.endswith(("_PUBLIC_KEY", "_PUBLIC_KEY_FILE")):
        return False
    return (
        any(marker in name for marker in (
            "SECRET", "PASSWORD", "PASSWD", "DATABASE_URI",
        ))
        or name.endswith((
            "_PASS", "_PASS_FILE", "_PW", "_PW_FILE", "_KEY", "_KEY_FILE",
            "_TOKEN", "_TOKEN_FILE", "_CREDENTIAL", "_CREDENTIALS", "_CREDENTIAL_FILE",
        ))
    )


def _quote_environment(value):
    """Quote a value for supervisord's comma-separated environment syntax."""
    return '"{}"'.format(
        str(value).replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    )


def clean_environment(keep=()):
    """Remove sensitive variables before running startup helper commands."""
    keep = set(keep)
    for name in list(os.environ):
        if name not in keep and _is_sensitive(name):
            os.environ.pop(name, None)


def start(programs, secret_env=None):
    """Exec supervisord, keeping sensitive variables scoped to named programs.

    ``programs`` contains ``name``, ``command`` and optional ``environment``
    values. ``secret_env`` maps program names to the sensitive environment
    entries that program needs. Supervisord itself and all other programs run
    without any sensitive variables inherited from the container environment.
    """
    secret_env = secret_env or {}
    parent_env = dict(os.environ)
    program_directory = os.getcwd()
    control_username = "mailu-supervisorctl"
    control_password = secrets.token_urlsafe(32)
    config = ["[supervisord]"]
    if os.geteuid() == 0:
        config.append("user=root")
    config.extend([
        "pidfile={}".format(SUPERVISOR_PID),
        "nodaemon=true",
        "logfile=/dev/stdout",
        "logfile_maxbytes=0",
        "childlogdir=/tmp",
        "loglevel=info",
        "",
        "[unix_http_server]",
        "file={}".format(SUPERVISOR_SOCKET),
        "chmod=0700",
        "username={}".format(control_username),
        "password={}".format(control_password),
        "",
        "[rpcinterface:supervisor]",
        "supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface",
    ])

    for program in programs:
        name = program["name"]
        environment = dict(program.get("environment", {}))
        environment.update(secret_env.get(name, {}))
        if "LD_PRELOAD" in parent_env:
            environment.setdefault("LD_PRELOAD", parent_env["LD_PRELOAD"])
        command = program["command"]
        if program.get("log_filters"):
            environment["MAILU_LOG_FILTERS"] = ",".join(
                base64.b64encode(pattern).decode("ascii")
                for pattern in program["log_filters"]
            )
            command = [sys.executable, "-m", "socrate.log_filter", "--"] + command
        config.extend([
            "",
            "[program:{}]".format(name),
            "command={}".format(shlex.join(command)),
            "directory={}".format(program.get("directory", program_directory)),
            "priority={}".format(program.get("priority", 999)),
            "autostart=true",
            "autorestart=true",
            "startsecs=1",
            "startretries=3",
            "stopsignal=TERM",
            "stopwaitsecs=30",
            "stopasgroup=true",
            "killasgroup=true",
            "redirect_stderr=true",
            "stdout_logfile=/dev/fd/1",
            "stdout_logfile_maxbytes=0",
        ])
        if program.get("user"):
            config.append("user={}".format(program["user"]))
        if environment:
            config.append("environment={}".format(",".join(
                "{}={}".format(key, _quote_environment(value))
                for key, value in sorted(environment.items())
            )))

    old_umask = os.umask(0o077)
    try:
        os.makedirs(SUPERVISOR_RUNTIME_DIR, exist_ok=True)
        with open(SUPERVISOR_CONFIG, "w") as handle:
            handle.write("\n".join(config) + "\n")
            handle.write((
                "\n[supervisorctl]\n"
                "serverurl=unix://{}\n"
                "username={}\n"
                "password={}\n"
            ).format(SUPERVISOR_SOCKET, control_username, control_password))
        os.chmod(SUPERVISOR_CONFIG, 0o600)
    finally:
        os.umask(old_umask)

    for stale_path in (SUPERVISOR_SOCKET,):
        try:
            os.unlink(stale_path)
        except FileNotFoundError:
            pass

    clean_env = {
        name: value for name, value in parent_env.items()
        if not _is_sensitive(name)
    }
    sys.stdout.flush()
    sys.stderr.flush()
    os.execve(
        "/usr/bin/supervisord",
        ["supervisord", "-n", "-c", SUPERVISOR_CONFIG],
        clean_env,
    )
    sys.exit(1)
