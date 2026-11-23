import base64
import os
import queue
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from socrate import log_filter


def test_log_filter_preserves_bytes_and_filters_matching_lines():
    environment = dict(os.environ)
    environment["MAILU_LOG_FILTERS"] = base64.b64encode(b"drop this").decode("ascii")
    script = (
        "import os; "
        "os.write(1, b'keep\\xff\\n'); "
        "os.write(1, b'drop this\\n'); "
        "os.write(2, b'error\\xfe\\n')"
    )

    result = subprocess.run(
        [sys.executable, "-m", "socrate.log_filter", "--", sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == b"keep\xff\n"
    assert result.stderr == b"error\xfe\n"


def test_log_filter_drops_lines_instead_of_blocking_on_slow_sink():
    output_queue = queue.Queue(maxsize=1)
    writer_blocked = threading.Event()
    release_writer = threading.Event()
    read_fd, write_fd = os.pipe()
    dropped = {write_fd: 0}

    def blocked_write(fd, data):
        writer_blocked.set()
        release_writer.wait(timeout=3)
        return os.write(fd, data)

    writer = threading.Thread(
        target=log_filter._forward_output,
        args=(output_queue, set(), blocked_write),
        daemon=True,
    )
    writer.start()
    output_queue.put_nowait((write_fd, b"first\n"))
    assert writer_blocked.wait(timeout=1)

    start = time.monotonic()
    log_filter._emit(output_queue, write_fd, b"second\n", [], dropped, set())
    log_filter._emit(output_queue, write_fd, b"third\n", [], dropped, set())

    assert time.monotonic() - start < 0.1
    assert output_queue.get_nowait() == (write_fd, b"second\n")
    assert dropped[write_fd] == 1

    release_writer.set()
    output_queue.put_nowait(None)
    writer.join(timeout=1)
    os.close(read_fd)
    os.close(write_fd)
    assert not writer.is_alive()


def test_log_filter_stops_descendants_when_child_exits(tmp_path):
    pid_file = tmp_path / "descendant.pid"
    child = (
        "import subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "open(sys.argv[1], 'w').write(str(child.pid)); "
        "raise SystemExit(7)"
    )
    result = subprocess.run(
        [sys.executable, "-m", "socrate.log_filter", "--", sys.executable, "-c", child, str(pid_file)],
        env=dict(os.environ),
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 7
    child_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            state = Path(f"/proc/{child_pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except FileNotFoundError:
            break
        if state == "Z":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("log filter left a descendant running")


def test_log_filter_forwards_sigterm_and_kills_child_that_ignores_it(tmp_path):
    pid_file = tmp_path / "child.pid"
    child = (
        "import os, signal, sys, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "open(sys.argv[1], 'w').write(str(os.getpid())); "
        "time.sleep(30)"
    )
    wrapper = subprocess.Popen(
        [sys.executable, "-m", "socrate.log_filter", "--", sys.executable, "-c", child, str(pid_file)],
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 3
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert pid_file.exists()

    wrapper.send_signal(signal.SIGTERM)
    wrapper.communicate(timeout=8)
    assert wrapper.returncode == 128 + signal.SIGTERM

    child_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            state = Path(f"/proc/{child_pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except FileNotFoundError:
            break
        if state == "Z":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("log filter left a child running after SIGTERM")


def test_log_filter_forwards_sighup_without_stopping_child(tmp_path):
    pid_file = tmp_path / "child.pid"
    hup_file = tmp_path / "child.hup"
    child = (
        "import os, signal, sys, time; "
        "signal.signal(signal.SIGHUP, lambda *_: open(sys.argv[2], 'w').write('reloaded')); "
        "open(sys.argv[1], 'w').write(str(os.getpid())); "
        "time.sleep(30)"
    )
    wrapper = subprocess.Popen(
        [sys.executable, "-m", "socrate.log_filter", "--", sys.executable, "-c", child, str(pid_file), str(hup_file)],
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 3
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert pid_file.exists()

    wrapper.send_signal(signal.SIGHUP)
    deadline = time.monotonic() + 3
    while not hup_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert hup_file.read_text() == "reloaded"
    assert wrapper.poll() is None

    wrapper.send_signal(signal.SIGTERM)
    wrapper.communicate(timeout=8)
    assert wrapper.returncode == 128 + signal.SIGTERM


@pytest.mark.parametrize("shutdown_lines", [0, 1024])
def test_log_filter_uses_stop_command_for_detached_daemon(tmp_path, shutdown_lines):
    pid_file = tmp_path / "daemon.pid"
    term_file = tmp_path / "daemon.term"
    daemon = (
        "import os, signal, sys; "
        "from pathlib import Path; "
        "line = b'x' * 1023 + b'\\n'; "
        "signal.signal(signal.SIGTERM, lambda *_: "
        "([os.write(1, line) for _ in range(int(sys.argv[3]))], "
        "[os.write(2, line) for _ in range(int(sys.argv[3]))], "
        "Path(sys.argv[2]).touch(), sys.exit(0))); "
        "Path(sys.argv[1]).write_text(str(os.getpid())); signal.pause()"
    )
    foreground = (
        "import subprocess, sys; "
        "process = subprocess.Popen("
        "[sys.executable, '-c', sys.argv[1], *sys.argv[2:]], start_new_session=True); "
        "print('drop this', flush=True); print('keep this', flush=True); "
        "raise SystemExit(process.wait())"
    )
    stop_command = [
        sys.executable, "-c",
        "import os, signal, sys; "
        "from pathlib import Path; "
        "os.kill(int(Path(sys.argv[1]).read_text()), signal.SIGTERM)",
        str(pid_file),
    ]
    environment = dict(os.environ, MAILU_STOP_COMMAND=shlex.join(stop_command))
    environment["MAILU_LOG_FILTERS"] = base64.b64encode(b"drop this").decode("ascii")
    with (tmp_path / "stdout").open("w+b") as stdout, (tmp_path / "stderr").open("w+b") as stderr:
        wrapper = subprocess.Popen(
            [sys.executable, "-m", "socrate.log_filter", "--", sys.executable, "-c",
             foreground, daemon, str(pid_file), str(term_file), str(shutdown_lines)],
            env=environment,
            stdout=subprocess.DEVNULL if shutdown_lines else stdout,
            stderr=subprocess.DEVNULL if shutdown_lines else stderr,
        )
    try:
        deadline = time.monotonic() + 3
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert pid_file.exists()
        wrapper.terminate()
        wrapper.wait(timeout=12)
        assert term_file.exists()
        assert wrapper.returncode == 128 + signal.SIGTERM
        if not shutdown_lines:
            output = (tmp_path / "stdout").read_bytes()
            assert b"keep this" in output
            assert b"drop this" not in output
            assert b"stop command failed" not in (tmp_path / "stderr").read_bytes()
    finally:
        if pid_file.exists() and not term_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
        if wrapper.poll() is None:
            wrapper.kill()
            wrapper.wait()



@pytest.mark.parametrize("result", ["failure", "timeout"])
def test_log_filter_reaps_failed_stop_command_and_foreground(tmp_path, result):
    ready = tmp_path / "foreground.pid"
    stopped = tmp_path / "foreground.term"
    helper_pid = tmp_path / "helper.pid"
    foreground = (
        "import os, signal, sys; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, lambda *_: "
        "(os.write(1, b'x' * 1048576), Path(sys.argv[2]).touch(), sys.exit(0))); "
        "Path(sys.argv[1]).write_text(str(os.getpid())); signal.pause()"
    )
    helper = (
        "import os, sys, time; from pathlib import Path; "
        "Path(sys.argv[1]).write_text(str(os.getpid())); "
        "time.sleep(30) if sys.argv[2] == 'timeout' else sys.exit(75)"
    )
    environment = dict(os.environ, MAILU_STOP_COMMAND=shlex.join(
        [sys.executable, "-c", helper, str(helper_pid), result]))
    launcher = """
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from socrate import log_filter

# Advance to the timeout only after the helper has started and recorded its PID.
if sys.argv[2] == "timeout":
    helper_pid = Path(sys.argv[1])
    log_filter.time = SimpleNamespace(
        monotonic=lambda: time.monotonic() + (
            log_filter.STOP_COMMAND_TIMEOUT if helper_pid.exists() else 0
        ),
        sleep=time.sleep,
    )
raise SystemExit(log_filter.main())
"""
    with subprocess.Popen(
        [sys.executable, "-c", launcher, str(helper_pid), result,
         "--", sys.executable, "-c", foreground, str(ready), str(stopped)],
        env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    ) as wrapper:
        try:
            deadline = time.monotonic() + 3
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert ready.exists()
            wrapper.terminate()
            _, errors = wrapper.communicate(timeout=8)
            assert wrapper.returncode == 1
            assert (b"exit status 75" if result == "failure" else b"timed out") in errors
            assert stopped.exists()
            for path in (ready, helper_pid):
                with pytest.raises(ProcessLookupError):
                    os.kill(int(path.read_text()), 0)
        finally:
            if wrapper.poll() is None:
                wrapper.kill()
                wrapper.wait()


def test_log_filter_reports_forced_cleanup_after_successful_stop(tmp_path):
    foreground_pid = tmp_path / "foreground.pid"
    descendant_pid = tmp_path / "descendant.pid"
    descendant = (
        "import os, signal, sys; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path(sys.argv[1]).write_text(str(os.getpid())); signal.pause()"
    )
    foreground = (
        "import os, signal, subprocess, sys; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]]); "
        "Path(sys.argv[3]).write_text(str(os.getpid())); signal.pause()"
    )
    stop = [
        sys.executable, "-c",
        "import os, signal, sys; from pathlib import Path; "
        "os.kill(int(Path(sys.argv[1]).read_text()), signal.SIGTERM)",
        str(foreground_pid),
    ]
    with subprocess.Popen(
        [sys.executable, "-c", "from socrate import log_filter; "
         "log_filter.STOP_TIMEOUT = 0.25; raise SystemExit(log_filter.main())",
         "--", sys.executable, "-c", foreground, descendant, str(descendant_pid),
         str(foreground_pid)],
        env=dict(os.environ, MAILU_STOP_COMMAND=shlex.join(stop)),
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    ) as wrapper:
        try:
            deadline = time.monotonic() + 5
            while not (foreground_pid.exists() and descendant_pid.exists()) and time.monotonic() < deadline:
                time.sleep(0.05)
            assert foreground_pid.exists() and descendant_pid.exists()
            pid = int(descendant_pid.read_text())
            wrapper.terminate()
            _, errors = wrapper.communicate(timeout=8)
            state = Path(f"/proc/{pid}/stat")
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    if state.read_text().rsplit(")", 1)[1].split()[0] == "Z":
                        break
                except FileNotFoundError:
                    break
                time.sleep(0.05)
            else:
                pytest.fail("TERM-resistant descendant survived forced cleanup")
            assert wrapper.returncode == 1
            assert b"SIGKILL" in errors
        finally:
            if wrapper.poll() is None:
                wrapper.kill()
                wrapper.wait()
            if descendant_pid.exists():
                try:
                    os.kill(int(descendant_pid.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass


@pytest.mark.parametrize("keep_pipes_open, slow_sink", [
    (False, False), (True, False), (False, True),
])
def test_log_filter_drains_shutdown_tail(tmp_path, keep_pipes_open, slow_sink):
    ready = tmp_path / "foreground.pid"
    detached_pid = tmp_path / "detached.pid"
    foreground = """
import os
from pathlib import Path
import signal
import subprocess
import sys

def finish(*_):
    if sys.argv[4] == "True":
        os.write(1, (b"x" * 1023 + b"\\n") * 1024)
    os.write(1, b"stdout tail")
    os.write(2, b"stderr tail")
    sys.exit(0)

if sys.argv[3] == "True":
    child = subprocess.Popen(["sleep", "30"], start_new_session=True)
    Path(sys.argv[2]).write_text(str(child.pid))
signal.signal(signal.SIGTERM, finish)
Path(sys.argv[1]).write_text(str(os.getpid()))
signal.pause()
"""
    stop = [sys.executable, "-c", "import os, sys; os.kill(int(open(sys.argv[1]).read()), 15)", str(ready)]
    # Make shutdown completion race with the first read of the final output.
    launcher = """
from socrate import log_filter

class FinishedBeforeRead(log_filter._CommandShutdown):
    def __init__(self, *args):
        super().__init__(*args)
        self.command.wait(timeout=5)
        self.process.wait(timeout=5)

log_filter._CommandShutdown = FinishedBeforeRead
raise SystemExit(log_filter.main())
"""
    if slow_sink:
        launcher = "from socrate import log_filter; raise SystemExit(log_filter.main())"
    with subprocess.Popen(
        [sys.executable, "-c", launcher, "--", sys.executable, "-c", foreground,
         str(ready), str(detached_pid), str(keep_pipes_open), str(slow_sink)],
        env=dict(os.environ, MAILU_STOP_COMMAND=shlex.join(stop)),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ) as wrapper:
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert ready.exists()
            wrapper.terminate()
            if slow_sink:
                # Leave the wrapper's output pipe unread until the wrapper exits.
                wrapper.wait(timeout=8)
            stdout, stderr = wrapper.communicate(timeout=8)
            assert wrapper.returncode == 143
            if not keep_pipes_open and not slow_sink:
                assert (stdout, stderr) == (b"stdout tail", b"stderr tail")
        finally:
            if wrapper.poll() is None:
                wrapper.kill()
                wrapper.wait()
            if detached_pid.exists():
                os.kill(int(detached_pid.read_text()), signal.SIGKILL)
