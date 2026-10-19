"""WebAuthn configuration and registration helpers."""

from dataclasses import dataclass
import hashlib
import re
import uuid

from flask import current_app, request
from webauthn import generate_registration_options, verify_registration_response
from webauthn.helpers import (
    base64url_to_bytes, parse_authentication_credential_json,
    parse_registration_credential_json, parse_authenticator_data,
    parse_attestation_object,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference, AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor, ResidentKeyRequirement, UserVerificationRequirement,
)


PASSWORD_NUDGE_MARKER = 'data-flash-id="password-passkey-nudge"'


@dataclass
class PasskeyRegistration:
    credential: object
    verification: object
    flags: object
    attestation_format: str


class PasskeyRegistrationError(Exception):
    def __init__(self, message, status=400, reason='verification_failed'):
        super().__init__(message)
        self.status = status
        self.reason = reason


def registration_options(user):
    """Build registration options from the user's domain policy."""
    domain = user.domain
    return generate_registration_options(
        rp_id=rp_id(),
        rp_name=current_app.config['SITENAME'],
        user_id=hashlib.sha256(user.email.encode()).digest(),
        user_name=user.email,
        user_display_name=user.displayed_name or user.email,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=key.credential_id) for key in user.passkeys
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement(domain.passkey_resident_key),
            user_verification=(
                UserVerificationRequirement.REQUIRED if domain.passkey_require_uv
                else UserVerificationRequirement.PREFERRED
            ),
        ),
        attestation=(
            AttestationConveyancePreference.DIRECT
            if domain.passkey_attestation_policy == 'require'
            else AttestationConveyancePreference.NONE
        ),
    )


def register_credential(user, payload, challenge):
    """Verify and stage a credential using the domain's passkey policy.

    Callers control the authorization for the user and commit the database
    transaction after applying any flow-specific account changes.
    """
    domain = user.domain
    try:
        verification = verify_registration_response(
            credential=payload,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=rp_id(),
            expected_origin=origin(),
            require_user_verification=domain.passkey_require_uv,
        )
    except Exception as exc:
        raise PasskeyRegistrationError('Passkey registration could not be verified.') from exc

    attestation_format = enum_value(verification.fmt)
    flags = authenticator_flags(payload, registration=True)
    if not aaguid_allowed(domain, verification.aaguid):
        raise PasskeyRegistrationError(
            'This authenticator is not allowed for this domain.', reason='aaguid_policy',
        )
    if domain.passkey_device_bound and (
        enum_value(verification.credential_device_type) != 'single_device'
        or verification.credential_backed_up
    ):
        raise PasskeyRegistrationError(
            'This domain only allows device-bound passkeys.', reason='device_bound_policy',
        )
    if not authenticator_flags_allowed(domain, flags):
        raise PasskeyRegistrationError(
            'This authenticator does not meet the domain backup requirements.', reason='backup_policy',
        )
    if not attestation_allowed(domain, attestation_format):
        raise PasskeyRegistrationError(
            'Authenticator attestation does not meet the domain policy.', reason='attestation_policy',
        )

    from . import models
    credential_id = verification.credential_id
    if models.db.session.get(models.Passkey, credential_id):
        raise PasskeyRegistrationError(
            'This passkey is already registered.', status=409, reason='duplicate_credential',
        )

    credential = models.Passkey(
        user=user,
        credential_id=credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        aaguid=verification.aaguid,
        device_bound=(
            enum_value(verification.credential_device_type) == 'single_device'
            and not verification.credential_backed_up
        ),
        user_verified=verification.user_verified,
        user_present=flags.up,
        credential_device_type=enum_value(verification.credential_device_type),
        backup_eligible=flags.be,
        backed_up=verification.credential_backed_up,
        attestation_format=attestation_format,
        name=str(payload.get('name') or 'Passkey')[:255],
    )
    models.db.session.add(credential)
    user.passkey_enroll_next_login = False
    return PasskeyRegistration(credential, verification, flags, attestation_format)


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
