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


def test_stop_command_is_scoped_to_programs_that_configure_it(monkeypatch, tmp_path):
    monkeypatch.setenv("MAILU_STOP_COMMAND", "/bin/false")
    config_path = tmp_path / "supervisord.conf"
    monkeypatch.setattr(supervisor, "SUPERVISOR_CONFIG", str(config_path))
    monkeypatch.setattr(supervisor, "SUPERVISOR_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setattr(supervisor, "SUPERVISOR_SOCKET", str(tmp_path / "supervisor.sock"))

    def capture_execve(_path, _argv, environment):
        assert "MAILU_STOP_COMMAND" not in environment
        raise RuntimeError("captured supervisord exec")

    monkeypatch.setattr(supervisor.os, "execve", capture_execve)
    with pytest.raises(RuntimeError, match="captured supervisord exec"):
        supervisor.start([
            {"name": "filtered", "command": ["/bin/true"], "log_filters": [b"ignored"]},
            {
                "name": "explicit",
                "command": ["postfix", "start-fg"],
                "environment": {"MAILU_STOP_COMMAND": "/bin/false"},
                "stop_command": ["postfix", "stop"],
            },
            {
                "name": "filtered-with-environment",
                "command": ["/bin/true"],
                "log_filters": [b"ignored"],
                "environment": {"MAILU_STOP_COMMAND": "/bin/false"},
            },
        ])

    _, filtered, explicit, filtered_with_environment = config_path.read_text().split("[program:")
    for program in (filtered, filtered_with_environment):
        assert "socrate.log_filter" in program
        assert "MAILU_STOP_COMMAND" not in program
    assert 'MAILU_STOP_COMMAND="postfix stop"' in explicit
    assert "/bin/false" not in explicit
