import hmac
import logging as log
import os
import signal
import sys
import re
from pwd import getpwnam
import socket
import tenacity
import subprocess
import threading

@tenacity.retry(stop=tenacity.stop_after_attempt(100),
                wait=tenacity.wait_random(min=2, max=5))
def resolve_hostname(hostname):
    """ This function uses system DNS to resolve a hostname.
    It is capable of retrying in case the host is not immediately available
    """
    try:
        return sorted(socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE), key=lambda s:s[0])[0][4][0]
    except Exception as e:
        log.warn("Unable to lookup '%s': %s",hostname,e)
        raise e

def _coerce_value(value):
    if isinstance(value, str) and value.lower() in ('true','yes'):
        return True
    elif isinstance(value, str) and value.lower() in ('false', 'no'):
        return False
    return value

class LogFilter(object):
    def __init__(self, stream, re_patterns):
        self.stream = stream
        if isinstance(re_patterns, list):
            self.pattern = re.compile('|'.join([f'(?:{pattern})' for pattern in re_patterns]))
        elif isinstance(re_patterns, str):
            self.pattern = re.compile(re_patterns)
        else:
            self.pattern = re_patterns
        self.found = False

    def __getattr__(self, attr_name):
        return getattr(self.stream, attr_name)

    def write(self, data):
        if data == '\n' and self.found:
            self.found = False
        else:
            if not self.pattern.search(data):
                self.stream.write(data)
                self.stream.flush()
            else:
                # caught bad pattern
                self.found = True

    def flush(self):
        self.stream.flush()

def _is_compatible_with_hardened_malloc():
    with open('/proc/cpuinfo', 'r') as f:
        lines = f.readlines()
        for line in lines:
            # See #2764, we need vmovdqu
            # See #2959, we need vpunpckldq
            if line.startswith('flags') and ' avx2 ' not in line:
                return False
            # See #2541
            if line.startswith('Features') and ' lrcpc ' not in line:
                return False
    return True


def sigterm_handler(_signo, _stack_frame):
    log.critical("Received SIGTERM, terminating.")
    sys.exit(143)

def set_env(required_secrets=[], log_filters=[]):
    if log_filters:
        sys.stdout = LogFilter(sys.stdout, log_filters)
        sys.stderr = LogFilter(sys.stderr, log_filters)
    log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", 'WARNING'))
    signal.signal(signal.SIGTERM, sigterm_handler)

    if not 'LD_PRELOAD' in os.environ and _is_compatible_with_hardened_malloc():
        log.warning('Your CPU has Advanced Vector Extensions available, we recommend you enable hardened-malloc earlier in the boot process by adding LD_PRELOAD=/usr/lib/libhardened_malloc.so to your mailu.env')
        os.environ['LD_PRELOAD'] = '/usr/lib/libhardened_malloc.so'

    """ This will set all the environment variables and retains only the secrets we need """
    if 'SECRET_KEY_FILE' in os.environ:
        try:
            secret_key = open(os.environ.get("SECRET_KEY_FILE"), "r").read().strip()
        except Exception as exc:
            log.error(f"Can't read SECRET_KEY from file: {exc}")
            raise exc
    else:
        secret_key = os.environ.get('SECRET_KEY')
    clean_env()
    # derive the keys we need
    for secret in required_secrets:
        os.environ[f'{secret}_KEY'] = hmac.new(bytearray(secret_key, 'utf-8'), bytearray(secret, 'utf-8'), 'sha256').hexdigest()

    os.system('find /run -xdev -type f -name \*.pid -print -delete')

    return {
            key: _coerce_value(os.environ.get(key, value))
            for key, value in os.environ.items()
           }

def clean_env():
    """ remove all secret keys """
    [os.environ.pop(key, None) for key in os.environ.keys() if key.endswith("_KEY")]

def drop_privs_to(username='mailu'):
    pwnam = getpwnam(username)
    os.setgroups([])
    os.setgid(pwnam.pw_gid)
    os.setuid(pwnam.pw_uid)
    os.environ['HOME'] = pwnam.pw_dir

# forwards text lines from src to dst in an infinite loop
def forward_text_lines(src, dst):
    while True:
        current_line = src.readline()
        dst.write(current_line)


# runs a process and passes its standard/error output to the standard/error output of the current python script
def run_process_and_forward_output(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    stdout_thread = threading.Thread(target=forward_text_lines, args=(process.stdout, sys.stdout))
    stdout_thread.daemon = True
    stdout_thread.start()

    stderr_thread = threading.Thread(target=forward_text_lines, args=(process.stderr, sys.stderr))
    stderr_thread.daemon = True
    stderr_thread.start()

    process.wait()
