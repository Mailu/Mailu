"""Prepare the small runtime file set needed by chrooted Postfix services."""

import os
import shutil
import tempfile


CHROOT_FILES = (
    "/etc/group",
    "/etc/host.conf",
    "/etc/hosts",
    "/etc/localtime",
    "/etc/nsswitch.conf",
    "/etc/passwd",
    "/etc/resolv.conf",
    "/etc/services",
)


def _copy_into_queue(source, queue_root):
    if not os.path.isfile(source):
        return

    relative_path = source.lstrip("/")
    destination_dir = os.path.join(queue_root, os.path.dirname(relative_path))
    os.makedirs(destination_dir, mode=0o755, exist_ok=True)
    if os.path.commonpath((queue_root, os.path.realpath(destination_dir))) != queue_root:
        raise RuntimeError("Postfix chroot path escapes the queue directory")

    source_stat = os.stat(source)
    fd, temporary_path = tempfile.mkstemp(dir=destination_dir)
    try:
        with os.fdopen(fd, "wb") as destination, open(source, "rb") as source_file:
            shutil.copyfileobj(source_file, destination)
        os.chmod(temporary_path, source_stat.st_mode & 0o777)
        os.chown(temporary_path, source_stat.st_uid, source_stat.st_gid)
        os.replace(temporary_path, os.path.join(queue_root, relative_path))
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def prepare_postfix_chroot():
    """Copy resolver and account files for Postfix daemons chrooted in /queue."""
    queue_root = os.path.realpath("/queue")
    for source in CHROOT_FILES:
        _copy_into_queue(source, queue_root)
