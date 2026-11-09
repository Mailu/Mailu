"""Selection of administratively enabled webmails."""

from socrate.webmail import available as parse_available


def available(config):
    """Return enabled webmails in administrator-specified order."""
    return parse_available(config.get("WEBMAIL_AVAILABLE"))

def selected(config, preference=None):
    """Select a webmail, falling back when a preference is disabled."""
    enabled = available(config)
    if not enabled:
        return None
    return preference if preference in enabled else enabled[0]
