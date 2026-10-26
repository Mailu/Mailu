import os

import pytest

from socrate import supervisor


def test_supervisord_forwards_ld_preload_without_leaking_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("LD_PRELOAD", "/usr/lib/libhardened_malloc.so")
    monkeypatch.setenv("RATELIMIT_STORAGE_URL", "redis://redis:6379/2")
    monkeypatch.setenv("SECRET_KEY", "container-secret")
    monkeypatch.setattr(supervisor, "SUPERVISOR_CTL_CONFIG", str(tmp_path / "ctl.conf"))
    monkeypatch.setattr(supervisor, "SUPERVISOR_PID", str(tmp_path / "supervisord.pid"))
    monkeypatch.setattr(supervisor, "SUPERVISOR_SOCKET", str(tmp_path / "supervisor.sock"))

    captured = {}

    def capture_execve(_path, argv, environment):
        captured["environment"] = environment
        config_fd = int(argv[-1].rsplit("/", 1)[1])
        captured["config"] = os.pread(config_fd, 65536, 0).decode()
        raise RuntimeError("captured supervisord exec")

    monkeypatch.setattr(supervisor.os, "execve", capture_execve)

    with pytest.raises(RuntimeError, match="captured supervisord exec"):
        supervisor.start(
            [
                {"name": "needs-secret", "command": ["/bin/true"]},
                {"name": "no-secret", "command": ["/bin/true"]},
            ],
            secret_env={"needs-secret": {"SECRET_KEY": "program-secret"}},
        )

    assert captured["environment"]["LD_PRELOAD"] == "/usr/lib/libhardened_malloc.so"
    assert captured["environment"]["RATELIMIT_STORAGE_URL"] == "redis://redis:6379/2"
    assert not supervisor._is_sensitive("RATELIMIT_STORAGE_URL")
    assert "SECRET_KEY" not in captured["environment"]

    programs = captured["config"].split("[program:")
    needs_secret, no_secret = programs[1:]
    assert 'LD_PRELOAD="/usr/lib/libhardened_malloc.so"' in needs_secret
    assert 'SECRET_KEY="program-secret"' in needs_secret
    assert 'LD_PRELOAD="/usr/lib/libhardened_malloc.so"' in no_secret
    assert "SECRET_KEY" not in no_secret
