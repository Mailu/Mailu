"""Run a child with bounded, nonblocking stdout and stderr filtering."""

import base64
import errno
import os
import queue
import re
import select
import selectors
import shlex
import signal
import subprocess
import sys
import threading
import time


READ_SIZE = 65536
MAX_LINE_SIZE = 65536
MAX_QUEUED_LINES = 64
STOP_TIMEOUT = 3
STOP_COMMAND_TIMEOUT = 6
SHUTDOWN_DRAIN_TIMEOUT = 0.25


def _patterns():
    encoded = os.environ.pop("MAILU_LOG_FILTERS", "")
    return [re.compile(base64.b64decode(item)) for item in encoded.split(",") if item]


def _emit(output_queue, output_fd, line, patterns, dropped, disabled):
    if any(pattern.search(line) for pattern in patterns):
        return
    if output_fd in disabled:
        dropped[output_fd] += 1
        return

    if dropped[output_fd]:
        notice = "[mailu log filter] dropped {} log lines (backpressure or oversized line)\n".format(
            dropped[output_fd]
        ).encode()
        try:
            output_queue.put_nowait((output_fd, notice))
        except queue.Full:
            pass
        else:
            dropped[output_fd] = 0

    try:
        output_queue.put_nowait((output_fd, line))
    except queue.Full:
        dropped[output_fd] += 1


def _forward_output(output_queue, disabled, write=os.write):
    """Forward queued bytes; a blocked sink never blocks the pipe reader."""
    while True:
        item = output_queue.get()
        if item is None:
            return
        output_fd, data = item
        if output_fd in disabled:
            continue
        remaining = memoryview(data)
        while remaining:
            try:
                written = write(output_fd, remaining)
            except OSError as error:
                if error.errno == errno.EINTR:
                    continue
                if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    try:
                        select.select([], [output_fd], [], 0.1)
                    except (OSError, ValueError):
                        disabled.add(output_fd)
                        break
                    continue
                disabled.add(output_fd)
                break
            except BaseException:
                disabled.add(output_fd)
                break
            if written <= 0:
                disabled.add(output_fd)
                break
            remaining = remaining[written:]


def _signal_process_group(process, signum):
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def _process_group_exists(process):
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    return True


def _stop_process_group(process, timeout=STOP_TIMEOUT):
    """Stop the child tree, escalate if needed, and always reap the child."""
    _signal_process_group(process, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while _process_group_exists(process) and time.monotonic() < deadline:
        time.sleep(0.05)
    if _process_group_exists(process):
        _signal_process_group(process, signal.SIGKILL)
    try:
        process.wait(timeout=STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        _signal_process_group(process, signal.SIGKILL)
        process.wait()


class _CommandShutdown:
    """Advance shutdown without interrupting reads from the daemon's pipes."""

    def __init__(self, command, process, report_error):
        self.process = process
        self.report_error = report_error
        self.command = None
        self.failed = False
        self.group_deadline = None
        self.group_killed = False
        self.groups = [process]
        self.command_deadline = time.monotonic() + STOP_COMMAND_TIMEOUT
        try:
            self.command = subprocess.Popen(command, start_new_session=True)
            self.groups.append(self.command)
        except OSError as error:
            self._fallback(str(error))

    def _fallback(self, error=None):
        if error is not None:
            self.failed = True
            self.report_error("stop command failed: {}".format(error))
        for child in self.groups:
            _signal_process_group(child, signal.SIGTERM)
        self.group_deadline = time.monotonic() + STOP_TIMEOUT

    def advance(self):
        """Poll and reap both children, escalating the relevant group at its deadline."""
        now = time.monotonic()
        process_exited = self.process.poll() is not None
        command_status = self.command.poll() if self.command is not None else None
        if self.group_deadline is None:
            if command_status not in (None, 0):
                self._fallback("exit status {}".format(command_status))
            elif command_status == 0 and process_exited:
                self._fallback()
            elif now >= self.command_deadline:
                if command_status is None:
                    _signal_process_group(self.command, signal.SIGKILL)
                self._fallback("timed out waiting for the command or foreground process")

        if self.group_deadline is None:
            return False
        live_groups = [child for child in self.groups if _process_group_exists(child)]
        if live_groups and now >= self.group_deadline and not self.group_killed:
            self.group_killed = True
            self.failed = True
            self.report_error("shutdown required SIGKILL for remaining process groups")
            for child in live_groups:
                _signal_process_group(child, signal.SIGKILL)
        return (
            (not live_groups or now >= self.group_deadline)
            and process_exited
            and (self.command is None or command_status is not None)
        )


def _emit_line(pipe, line, outputs, patterns, output_queue, dropped, disabled):
    output_fd = outputs[pipe]
    if len(line) > MAX_LINE_SIZE:
        dropped[output_fd] += 1
        return
    _emit(output_queue, output_fd, line, patterns, dropped, disabled)


def _consume(pipe, chunk, buffers, discarding, outputs, patterns, output_queue, dropped, disabled):
    """Split bytes into lines while bounding memory for unterminated lines."""
    buffer = buffers[pipe]
    while chunk:
        if pipe in discarding:
            newline = chunk.find(b"\n")
            if newline < 0:
                return
            discarding.remove(pipe)
            chunk = chunk[newline + 1:]
            continue

        newline = chunk.find(b"\n")
        if newline < 0:
            if len(buffer) + len(chunk) > MAX_LINE_SIZE:
                buffer.clear()
                discarding.add(pipe)
                dropped[outputs[pipe]] += 1
            else:
                buffer.extend(chunk)
            return

        line = bytes(buffer) + chunk[:newline + 1]
        buffer.clear()
        _emit_line(pipe, line, outputs, patterns, output_queue, dropped, disabled)
        chunk = chunk[newline + 1:]


def _flush_partial(pipe, buffers, discarding, outputs, patterns, output_queue, dropped, disabled):
    if pipe in discarding:
        return
    line = bytes(buffers[pipe])
    buffers[pipe].clear()
    if line:
        _emit_line(pipe, line, outputs, patterns, output_queue, dropped, disabled)


def main():
    if "--" not in sys.argv:
        raise SystemExit("usage: python -m socrate.log_filter -- command [args...]")
    command = sys.argv[sys.argv.index("--") + 1:]
    if not command:
        raise SystemExit("log filter requires a command")

    patterns = _patterns()
    stop_command = shlex.split(os.environ.pop("MAILU_STOP_COMMAND", ""))
    requested_signal = {"value": None}
    requested_child_signal = {"value": None}

    def request_signal(signum, _frame):
        if signum == signal.SIGHUP:
            requested_child_signal["value"] = signum
        else:
            requested_signal["value"] = signum

    original_handlers = {
        signum: signal.signal(signum, request_signal)
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
    }
    process = None
    selector = None
    writer = None
    shutdown = None
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
        selector = selectors.DefaultSelector()
        pipes = (process.stdout, process.stderr)
        outputs = {process.stdout: sys.stdout.fileno(), process.stderr: sys.stderr.fileno()}
        buffers = {pipe: bytearray() for pipe in pipes}
        discarding = set()
        dropped = {fd: 0 for fd in outputs.values()}
        disabled = set()
        output_queue = queue.Queue(maxsize=MAX_QUEUED_LINES)
        writer = threading.Thread(
            target=_forward_output,
            args=(output_queue, disabled),
            name="mailu-log-output",
            daemon=True,
        )
        writer.start()

        for pipe in pipes:
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ)

        def report_stop_error(error):
            message = "[mailu log filter] {}\n".format(error).encode()
            _emit(output_queue, sys.stderr.fileno(), message, (), dropped, disabled)

        group_stopped = False
        drain_deadline = None
        while selector.get_map() or process.poll() is None or shutdown is not None:
            if requested_child_signal["value"] is not None:
                _signal_process_group(process, requested_child_signal["value"])
                requested_child_signal["value"] = None

            if requested_signal["value"] is not None:
                if shutdown is None:
                    if not stop_command:
                        _stop_process_group(process)
                        break
                    shutdown = _CommandShutdown(stop_command, process, report_stop_error)

            timeout = 0.05 if shutdown is not None else 0.25
            if drain_deadline is not None:
                remaining = drain_deadline - time.monotonic()
                if not selector.get_map() or remaining <= 0:
                    break
                timeout = min(timeout, remaining)
            events = selector.select(timeout=timeout)
            for key, _ in events:
                pipe = key.fileobj
                try:
                    chunk = os.read(pipe.fileno(), READ_SIZE)
                except InterruptedError:
                    continue
                if not chunk:
                    selector.unregister(pipe)
                    _flush_partial(
                        pipe, buffers, discarding, outputs, patterns,
                        output_queue, dropped, disabled,
                    )
                    pipe.close()
                    continue
                _consume(
                    pipe, chunk, buffers, discarding, outputs, patterns,
                    output_queue, dropped, disabled,
                )

            if shutdown is not None:
                if drain_deadline is None and shutdown.advance():
                    drain_deadline = time.monotonic() + SHUTDOWN_DRAIN_TIMEOUT
            elif process.poll() is not None and not group_stopped:
                # A service command must remain in the foreground. Clean up
                # any descendants if its leader exits while they hold pipes.
                _stop_process_group(process, timeout=1)
                group_stopped = True

        if requested_signal["value"] is not None:
            return 1 if shutdown is not None and shutdown.failed else 128 + requested_signal["value"]
        if process.poll() is None:
            _stop_process_group(process)
        return process.wait()
    except BaseException:
        if process is not None:
            _stop_process_group(process)
        raise
    finally:
        if shutdown is not None and shutdown.command is not None and shutdown.command.poll() is None:
            _stop_process_group(shutdown.command)
        if selector is not None:
            selector.close()
        if process is not None:
            for pipe in (process.stdout, process.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
            if process.poll() is None:
                _stop_process_group(process)
            else:
                process.wait()
        if writer is not None:
            try:
                output_queue.put_nowait(None)
            except queue.Full:
                pass
            writer.join(timeout=0.25)
        for signum, handler in original_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
