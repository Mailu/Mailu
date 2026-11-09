"""Parse the webmails enabled by an administrator."""

SUPPORTED = ('roundcube', 'snappymail')


def available(value):
    """Unset means both webmails; ``none`` takes precedence over all names."""
    value = (value or '').strip() or ','.join(SUPPORTED)
    names = [name.strip().lower() for name in value.split(',')]
    if 'none' in names:
        return []
    return list(dict.fromkeys(name for name in names if name in SUPPORTED))
