"""Normalize Dovecot full-text search environment settings."""

from socrate.system import parse_bool


def normalize_languages(value):
    """Normalize FULL_TEXT_SEARCH to a language list or ``off``."""
    config = str(value or "en").strip() or "en"
    enabled = parse_bool(config)
    if enabled is True:
        return "en"
    if enabled is False:
        return "off"
    return ",".join(language.strip() for language in config.split(","))
