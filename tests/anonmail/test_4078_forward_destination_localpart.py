"""Auto-forward destinations must accept the same localparts as the rest of Mailu (#4078)."""

import re

import pytest

from mailu.ui import forms


ATEXT_SPECIALS = "!#$%&'*+-/=?^_`{|}~"


def validate_destination(app, destination):
    """Run the real UserSettingsForm over a forward destination."""
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_request_context(
        method='POST',
        data={'forward_destination': destination, 'submit': 'Save settings'},
    ):
        form = forms.UserSettingsForm()
        form.validate()
        return not form.forward_destination.errors


class TestForwardDestinationLocalpart:

    def test_tilde_localpart_is_accepted(self, app):
        """#4078: `~@domain.com` is a valid address and must be forwardable to."""
        assert validate_destination(app, '~@example.com')

    @pytest.mark.parametrize('char', list(ATEXT_SPECIALS))
    def test_every_localpart_character_mailu_allows_is_accepted(self, app, char):
        """Whatever a localpart may contain must also be usable as a destination.

        LOCALPART_REGEX is what UserForm/AliasForm accept when *creating* an
        address, so a destination validator that rejects a subset of it makes
        addresses Mailu itself hands out unreachable.
        """
        localpart = f'a{char}b'
        assert re.match(forms.LOCALPART_REGEX, localpart), 'test bug: not a Mailu localpart'

        assert validate_destination(app, f'{localpart}@example.com')

    @pytest.mark.parametrize('destination', [
        'user@example.com',
        'first.last@example.com',
        'user+tag@example.com',
        'user_name@sub.example.com',
        'User@Example.COM',
        'one@example.com,two@example.org',
        'one@example.com, two@example.org',
    ])
    def test_previously_accepted_destinations_still_pass(self, app, destination):
        assert validate_destination(app, destination)

    @pytest.mark.parametrize('destination', [
        'notanemail',
        'user@',
        '@example.com',
        'user@@example.com',
        'one@example.com,,two@example.org',
        'one@example.com,notanemail',
    ])
    def test_invalid_destinations_are_still_rejected(self, app, destination):
        assert not validate_destination(app, destination)
