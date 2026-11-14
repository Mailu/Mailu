from types import SimpleNamespace

from mailu.passkeys import (
    aaguid_allowed, authenticator_flags_allowed, attestation_allowed,
    clear_password_passkey_nudge, enum_value, sign_count_allowed,
)


def domain(**kwargs):
    values = {
        'passkey_enforce_aaguid': False,
        'passkey_aaguid_mode': 'allow',
        'passkey_aaguids': '',
        'passkey_backup_eligible_policy': 'optional',
        'passkey_backup_state_policy': 'optional',
        'passkey_attestation_policy': 'optional',
        'passkey_require_sign_count_increase': False,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_aaguid_policy_defaults_to_allow():
    assert aaguid_allowed(domain(), 'adce0002-35bc-c60a-648b-0b25f1f05503')


def test_aaguid_allow_mode_restricts_to_listed_authenticators():
    policy = domain(passkey_enforce_aaguid=True, passkey_aaguid_mode='allow', passkey_aaguids=(
        'adce0002-35bc-c60a-648b-0b25f1f05503\n'
        'adce0002-35bc-c60a-648b-0b25f1f05504'
    ))
    assert aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05503')
    assert aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05504')
    assert not aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05505')


def test_aaguid_block_mode_rejects_listed_authenticators_case_insensitively():
    policy = domain(
        passkey_enforce_aaguid=True,
        passkey_aaguid_mode='block',
        passkey_aaguids='ADCE0002-35BC-C60A-648B-0B25F1F05503',
    )
    assert not aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05503')


def test_aaguid_list_is_ignored_when_enforcement_is_disabled():
    policy = domain(
        passkey_aaguid_mode='block',
        passkey_aaguids='adce0002-35bc-c60a-648b-0b25f1f05503',
    )
    assert aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05503')


def test_enum_value_accepts_strings_and_enum_instances():
    from enum import Enum

    class Kind(Enum):
        SINGLE = 'single_device'

    assert enum_value('single_device') == 'single_device'
    assert enum_value(Kind.SINGLE) == 'single_device'


def test_authenticator_flag_policies_support_optional_require_and_deny():
    flags = SimpleNamespace(be=True, bs=False)
    assert authenticator_flags_allowed(domain(), flags)
    assert authenticator_flags_allowed(domain(passkey_backup_eligible_policy='require'), flags)
    assert not authenticator_flags_allowed(domain(passkey_backup_eligible_policy='deny'), flags)
    assert not authenticator_flags_allowed(domain(passkey_backup_state_policy='require'), flags)
    assert authenticator_flags_allowed(domain(passkey_backup_state_policy='deny'), flags)


def test_attestation_policy_supports_optional_require_and_deny():
    assert attestation_allowed(domain(), 'none')
    assert attestation_allowed(domain(passkey_attestation_policy='require'), 'packed')
    assert not attestation_allowed(domain(passkey_attestation_policy='require'), 'none')
    assert attestation_allowed(domain(passkey_attestation_policy='deny'), 'none')
    assert not attestation_allowed(domain(passkey_attestation_policy='deny'), 'packed')


def test_signature_counter_enforcement_is_off_by_default():
    assert sign_count_allowed(domain(), 8, 2)
    policy = domain(passkey_require_sign_count_increase=True)
    assert sign_count_allowed(policy, 8, 9)
    assert not sign_count_allowed(policy, 8, 8)
    assert not sign_count_allowed(policy, 8, 0)


def test_successful_passkey_login_removes_only_the_password_nudge():
    from mailu.passkeys import PASSWORD_NUDGE_MARKER

    session = {
        '_flashes': [
            ('info', f'<span {PASSWORD_NUDGE_MARKER}>password nudge</span>'),
            ('error', 'unrelated error'),
        ],
    }

    clear_password_passkey_nudge(session)

    assert session['_flashes'] == [('error', 'unrelated error')]
