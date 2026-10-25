"""Run a child while filtering its stdout and stderr without forwarding threads."""

import base64
import os
import re
import selectors
import subprocess
import sys
import time


def _patterns():
    encoded = os.environ.pop("MAILU_LOG_FILTERS", "")
    return [re.compile(base64.b64decode(item)) for item in encoded.split(",") if item]


def _write(stream, line, patterns):
    if any(pattern.search(line) for pattern in patterns):
        return
    try:
        stream.buffer.write(line)
        stream.buffer.flush()
    except BrokenPipeError:
        # Continue draining the child's pipes so a closed Docker log consumer
        # cannot block the service process on a full pipe.
        pass


def main():
    if "--" not in sys.argv:
        raise SystemExit("usage: python -m socrate.log_filter -- command [args...]")
    command = sys.argv[sys.argv.index("--") + 1:]
    if not command:
        raise SystemExit("log filter requires a command")

    patterns = _patterns()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    selector = selectors.DefaultSelector()
    buffers = {}
    streams = {process.stdout: sys.stdout, process.stderr: sys.stderr}
    for pipe in streams:
        os.set_blocking(pipe.fileno(), False)
        buffers[pipe] = bytearray()
        selector.register(pipe, selectors.EVENT_READ)

    try:
        while selector.get_map() or process.poll() is None:
            if not selector.get_map():
                time.sleep(0.2)
                continue
            for key, _ in selector.select(timeout=1):
                pipe = key.fileobj
                try:
                    chunk = os.read(pipe.fileno(), 65536)
                except InterruptedError:
                    continue
                if not chunk:
                    selector.unregister(pipe)
                    pending = bytes(buffers[pipe])
                    if pending:
                        _write(streams[pipe], pending, patterns)
                    pipe.close()
                    continue
                buffers[pipe].extend(chunk)
                while b"\n" in buffers[pipe]:
                    line, _, rest = buffers[pipe].partition(b"\n")
                    buffers[pipe] = bytearray(rest)
                    _write(streams[pipe], line + b"\n", patterns)
    except BaseException:
        process.terminate()
        raise
    finally:
        selector.close()

    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
