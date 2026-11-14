"""Tests for administrative webmail availability and user selection."""
from mailu import webmail


def test_default_and_explicit_list():
    assert webmail.available({}) == ["roundcube", "snappymail"]
    assert webmail.available({"WEBMAIL_AVAILABLE": " SnappyMail, roundcube,snappymail,unknown "}) == ["snappymail", "roundcube"]
    assert webmail.available({"WEBMAIL_AVAILABLE": ""}) == ["roundcube", "snappymail"]
    assert webmail.available({"WEBMAIL_AVAILABLE": "  "}) == ["roundcube", "snappymail"]
    assert webmail.available({"WEBMAIL_AVAILABLE": "none"}) == []
    assert webmail.available({"WEBMAIL_AVAILABLE": "roundcube, NONE, snappymail"}) == []


def test_preference_and_disabled_fallback():
    config = {"WEBMAIL_AVAILABLE": "roundcube,snappymail"}
    assert webmail.selected(config, "snappymail") == "snappymail"
    assert webmail.selected({"WEBMAIL_AVAILABLE": "roundcube"}, "snappymail") == "roundcube"
    assert webmail.selected({"WEBMAIL_AVAILABLE": "none"}, "roundcube") is None
