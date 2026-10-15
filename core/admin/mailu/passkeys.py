"""WebAuthn configuration helpers."""

from flask import current_app, request
import uuid
import re


PASSWORD_NUDGE_MARKER = 'data-flash-id="password-passkey-nudge"'


def rp_id():
    return current_app.config.get('PASSKEY_RP_ID') or current_app.config['HOSTNAME']


def origin():
    return request.url_root.rstrip('/')


def aaguids(value):
    values = set()
    for item in re.split(r'[\r\n,]+', value or ''):
        item = item.strip()
        if item:
            try:
                values.add(str(uuid.UUID(item)))
            except ValueError:
                values.add('invalid:' + item.lower())
    return values


def normalize_aaguids(value):
    """Validate and normalize a comma or newline separated AAGUID list."""
    if value is not None and not isinstance(value, str):
        raise ValueError('AAGUID list must be text')
    normalized = []
    for item in re.split(r'[\r\n,]+', value or ''):
        item = item.strip()
        if item:
            normalized.append(str(uuid.UUID(item)))
    return '\n'.join(dict.fromkeys(normalized))


def aaguid_allowed(domain, aaguid):
    try:
        aaguid = str(uuid.UUID(aaguid or ''))
    except ValueError:
        return False
    listed = aaguids(domain.passkey_aaguids)
    if domain.passkey_aaguid_mode == 'block':
        return aaguid not in listed
    return not listed or aaguid in listed


def enum_value(value):
    """Accept both enum instances and the string values emitted by webauthn."""
    return getattr(value, 'value', value)


def clear_password_passkey_nudge(session):
    """Discard a password-authentication nudge before completing passkey auth."""
    flashes = session.get('_flashes', [])
    remaining = [
        (category, message)
        for category, message in flashes
        if PASSWORD_NUDGE_MARKER not in str(message)
    ]
    if len(remaining) != len(flashes):
        if remaining:
            session['_flashes'] = remaining
        else:
            session.pop('_flashes', None)
