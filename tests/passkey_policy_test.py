from types import SimpleNamespace

from mailu.passkeys import aaguid_allowed, clear_password_passkey_nudge, enum_value


def domain(**kwargs):
    values = {
        'passkey_aaguid_mode': 'allow',
        'passkey_aaguids': '',
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_aaguid_policy_defaults_to_allow():
    assert aaguid_allowed(domain(), 'adce0002-35bc-c60a-648b-0b25f1f05503')


def test_aaguid_allow_mode_restricts_to_listed_authenticators():
    policy = domain(passkey_aaguid_mode='allow', passkey_aaguids=(
        'adce0002-35bc-c60a-648b-0b25f1f05503\n'
        'adce0002-35bc-c60a-648b-0b25f1f05504'
    ))
    assert aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05503')
    assert aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05504')
    assert not aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05505')


def test_aaguid_block_mode_rejects_listed_authenticators_case_insensitively():
    policy = domain(
        passkey_aaguid_mode='block',
        passkey_aaguids='ADCE0002-35BC-C60A-648B-0B25F1F05503',
    )
    assert not aaguid_allowed(policy, 'adce0002-35bc-c60a-648b-0b25f1f05503')


def test_enum_value_accepts_strings_and_enum_instances():
    from enum import Enum

    class Kind(Enum):
        SINGLE = 'single_device'

    assert enum_value('single_device') == 'single_device'
    assert enum_value(Kind.SINGLE) == 'single_device'


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
