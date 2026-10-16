"""WebAuthn configuration helpers."""

from flask import current_app, request
import uuid
import re

from webauthn.helpers import (
    parse_authentication_credential_json, parse_registration_credential_json,
    parse_authenticator_data,
    parse_attestation_object,
)


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
    if not domain.passkey_enforce_aaguid:
        return True
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


def authenticator_flags(credential, registration=False):
    """Return verified authenticator flags from a browser credential payload."""
    if registration:
        parsed = parse_registration_credential_json(credential)
        auth_data = parse_attestation_object(parsed.response.attestation_object).auth_data
    else:
        parsed = parse_authentication_credential_json(credential)
        auth_data = parse_authenticator_data(parsed.response.authenticator_data)
    return auth_data.flags


def authenticator_flags_allowed(domain, flags):
    eligibility = domain.passkey_backup_eligible_policy
    backup_state = domain.passkey_backup_state_policy
    if eligibility == 'require' and not flags.be or eligibility == 'deny' and flags.be:
        return False
    if backup_state == 'require' and not flags.bs or backup_state == 'deny' and flags.bs:
        return False
    return True


def attestation_allowed(domain, attestation_format):
    policy = domain.passkey_attestation_policy
    has_statement = attestation_format != 'none'
    return not (policy == 'require' and not has_statement or policy == 'deny' and has_statement)


def sign_count_allowed(domain, current_count, new_count):
    return not domain.passkey_require_sign_count_increase or new_count > current_count


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
