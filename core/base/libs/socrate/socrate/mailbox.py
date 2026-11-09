"""Safely create isolated Dovecot mailbox homes."""
import os
import pwd
import stat

MIN_UID = 100000
MAX_UID = 2000000000


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
    if uid != gid or not MIN_UID <= uid <= MAX_UID:
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
