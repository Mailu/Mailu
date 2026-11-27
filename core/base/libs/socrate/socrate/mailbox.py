"""Safely create isolated Dovecot mailbox homes."""
import os
import pwd
import stat

DEFAULT_MIN_UID = 100000
DEFAULT_MAX_UID = 2000000000
# Below this, IDs belong to system and service accounts (the mailu user is 1000).
LOWEST_MIN_UID = 10000
# Mailbox IDs are stored in a signed 32-bit integer column.
HIGHEST_MAX_UID = 2**31 - 1
# Never given to a mailbox: nobody, and the 16-bit "no ID" value. A range may
# include them (e.g. 10000-65535 for a 65536-ID subuid block); they are skipped.
RESERVED_UIDS = frozenset((65534, 65535))


def uid_range(environ=None):
    """Return the (min, max) per-mailbox UID/GID range.

    Read from MAILBOX_UID_MIN and MAILBOX_UID_MAX. A smaller range is needed
    when containers run in a user namespace (rootless Docker or Podman,
    userns-remap), where only the IDs of the host's subuid/subgid block
    (usually 0-65535) exist.
    """
    environ = os.environ if environ is None else environ
    values = []
    for key, default in (('MAILBOX_UID_MIN', DEFAULT_MIN_UID), ('MAILBOX_UID_MAX', DEFAULT_MAX_UID)):
        raw = str(environ.get(key, '') or '').strip()
        try:
            values.append(int(raw) if raw else default)
        except ValueError:
            raise ValueError(f'{key} must be an integer, got {raw!r}') from None
    low, high = values
    if low < LOWEST_MIN_UID:
        raise ValueError(f'MAILBOX_UID_MIN must be at least {LOWEST_MIN_UID}, got {low}')
    if high > HIGHEST_MAX_UID:
        raise ValueError(f'MAILBOX_UID_MAX must be at most {HIGHEST_MAX_UID}, got {high}')
    if low >= high:
        raise ValueError(f'MAILBOX_UID_MIN ({low}) must be lower than MAILBOX_UID_MAX ({high})')
    return low, high


def valid_uid(uid, low, high):
    """Whether uid may be used for a mailbox in the range low..high."""
    return low <= uid <= high and uid not in RESERVED_UIDS


MIN_UID, MAX_UID = uid_range()


def _home_parts(home):
    prefix = '/mail/./'
    if not isinstance(home, str) or not home.startswith(prefix):
        raise ValueError('Invalid mailbox home')
    parts = home[len(prefix):].split('/')
    if len(parts) < 3 or any(part in ('', '.', '..') or '\x00' in part for part in parts):
        raise ValueError('Invalid mailbox home components')
    return parts


def harden_parents(homes, root='/mail'):
    """Remove directory-listing access while retaining traversal for mail UIDs."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(root, flags)
    try:
        info = os.fstat(root_fd)
        try:
            mail_uid = pwd.getpwnam('mail').pw_uid
        except KeyError:
            mail_uid = 0
        if info.st_uid not in (0, os.geteuid(), mail_uid):
            raise PermissionError('Mailbox root has unexpected ownership')
        os.fchmod(root_fd, 0o711)
        for home in homes:
            parent = os.dup(root_fd)
            try:
                for component in _home_parts(home)[:-1]:
                    try:
                        child = os.open(component, flags, dir_fd=parent)
                    except FileNotFoundError:
                        break
                    try:
                        if os.fstat(child).st_uid != os.geteuid():
                            raise PermissionError('Mailbox parent has unexpected ownership')
                        os.fchmod(child, 0o711)
                    except BaseException:
                        os.close(child)
                        raise
                    os.close(parent)
                    parent = child
            finally:
                os.close(parent)
    finally:
        os.close(root_fd)


def harden_parents_once(fetch_homes, root='/mail'):
    """Protect existing parents once, retrying on the next start after failure."""
    marker = os.path.join(root, '.mail-parents-protected-v1')
    if os.path.exists(marker):
        return
    harden_parents(fetch_homes(), root)
    with open(marker + '.tmp', 'w', encoding='ascii') as output:
        output.write('complete\n')
    os.replace(marker + '.tmp', marker)


def provision(fields, root='/mail'):
    home = fields['home']
    uid, gid = int(fields['uid']), int(fields['gid'])
    if uid != gid or not valid_uid(uid, MIN_UID, MAX_UID):
        raise ValueError('Invalid mailbox identity')
    parts = _home_parts(home)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open(root, flags)
    try:
        root_info = os.fstat(parent)
        try:
            mail_uid = pwd.getpwnam('mail').pw_uid
        except KeyError:
            mail_uid = 0
        if (root_info.st_uid not in (0, os.geteuid(), mail_uid)
                or root_info.st_mode & 0o066 or not root_info.st_mode & 0o001):
            raise PermissionError('Mailbox root has unsafe ownership or permissions')
        for i, component in enumerate(parts):
            is_home = i == len(parts) - 1
            created = False
            try:
                os.mkdir(component, 0o700 if is_home else 0o711, dir_fd=parent)
                created = True
            except FileExistsError:
                pass
            child = os.open(component, flags, dir_fd=parent)
            try:
                info = os.fstat(child)
                if is_home:
                    if created:
                        os.fchown(child, uid, gid)
                        os.fchmod(child, 0o700)
                    elif (info.st_uid != uid or info.st_gid != gid
                          or stat.S_IMODE(info.st_mode) != 0o700):
                        raise PermissionError('Existing mailbox home has unexpected owner or permissions')
                elif created:
                    os.fchmod(child, 0o711)
                elif info.st_uid != os.geteuid() or info.st_mode & 0o066 or not info.st_mode & 0o001:
                    raise PermissionError('Mailbox parent has unsafe ownership or permissions')
            except BaseException:
                os.close(child)
                raise
            os.close(parent)
            parent = child
    finally:
        os.close(parent)
