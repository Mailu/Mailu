"""clean_env() parses PROXY_PROTOCOL; an entry it cannot use must be reported.

clean_env() rewrites os.environ in place -- it pops every ``*_KEY`` and adds
PROXY_PROTOCOL_*, PORT_* and TLS_* -- so each test restores the environment it
was given rather than leaking those into the rest of the session.
"""

import logging
import os

import pytest

from socrate import system


@pytest.fixture
def clean_env():
    saved = dict(os.environ)
    def run(**overrides):
        os.environ.update(overrides)
        system.clean_env()
        return dict(os.environ)
    yield run
    os.environ.clear()
    os.environ.update(saved)


def test_unusable_entry_is_logged_and_does_not_raise(clean_env, caplog):
    """A service name where a port number belongs used to raise NameError."""
    with caplog.at_level(logging.ERROR):
        clean_env(PROXY_PROTOCOL='imaps')
    assert 'imaps' in caplog.text


def test_unusable_entry_does_not_stop_the_valid_ones(clean_env, caplog):
    with caplog.at_level(logging.ERROR):
        env = clean_env(PROXY_PROTOCOL='993,imaps,995')
    assert env.get('PROXY_PROTOCOL_993') == 'True'
    assert env.get('PROXY_PROTOCOL_995') == 'True'
    assert 'imaps' in caplog.text


@pytest.mark.parametrize('value,expected', [
    ('993', ['PROXY_PROTOCOL_993']),
    ('mail', ['PROXY_PROTOCOL_25', 'PROXY_PROTOCOL_993', 'PROXY_PROTOCOL_4190']),
    ('all-but-http', ['PROXY_PROTOCOL_443', 'PROXY_PROTOCOL_25']),
    ('all', ['PROXY_PROTOCOL_80', 'PROXY_PROTOCOL_443', 'PROXY_PROTOCOL_25']),
])
def test_accepted_values_still_work(clean_env, caplog, value, expected):
    with caplog.at_level(logging.ERROR):
        env = clean_env(PROXY_PROTOCOL=value)
    for key in expected:
        assert env.get(key) == 'True', f'{value!r} should set {key}'
    assert caplog.text == ''


def test_unset_proxy_protocol_is_not_an_error(clean_env, caplog):
    os.environ.pop('PROXY_PROTOCOL', None)
    with caplog.at_level(logging.ERROR):
        env = clean_env()
    assert not [k for k in env if k.startswith('PROXY_PROTOCOL_')]
    assert caplog.text == ''
