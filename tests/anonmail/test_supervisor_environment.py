import os

import pytest

from socrate import supervisor


def test_supervisord_forwards_ld_preload_without_leaking_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("LD_PRELOAD", "/usr/lib/libhardened_malloc.so")
    monkeypatch.setenv("RATELIMIT_STORAGE_URL", "redis://redis:6379/2")
    monkeypatch.setenv("SECRET_KEY", "container-secret")
    original_directory = os.getcwd()
    monkeypatch.setattr(supervisor, "SUPERVISOR_CONFIG", str(tmp_path / "supervisord.conf"))
    monkeypatch.setattr(supervisor, "SUPERVISOR_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setattr(supervisor, "SUPERVISOR_PID", str(tmp_path / "run" / "supervisord.pid"))
    monkeypatch.setattr(supervisor, "SUPERVISOR_SOCKET", str(tmp_path / "supervisor.sock"))

    captured = {}

    def capture_execve(_path, argv, environment):
        captured["environment"] = environment
        captured["argv"] = argv
        captured["config"] = (tmp_path / "supervisord.conf").read_text()
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
    assert captured["argv"] == ["supervisord", "-n", "-c", str(tmp_path / "supervisord.conf")]
    assert "pidfile={}/run/supervisord.pid".format(tmp_path) in captured["config"]
    assert "serverurl=unix://{}/supervisor.sock".format(tmp_path) in captured["config"]
    assert "directory={}".format(original_directory) in captured["config"]

    programs = captured["config"].split("[program:")
    needs_secret, no_secret = programs[1:]
    assert 'LD_PRELOAD="/usr/lib/libhardened_malloc.so"' in needs_secret
    assert 'SECRET_KEY="program-secret"' in needs_secret
    assert 'LD_PRELOAD="/usr/lib/libhardened_malloc.so"' in no_secret
    assert "SECRET_KEY" not in no_secret
