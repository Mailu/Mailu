import base64
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

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
