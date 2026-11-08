"""Shared spam settings exposed as line-based Rspamd maps."""

from copy import deepcopy
import html
import re
from urllib.parse import unquote

from mailu import models


CONFIG_KEY = "rspamd_spam_settings"
SETTINGS_VERSION = 2
LEGACY_ARC_SIGNERS = "google.com\nmicrosoft.com\nyahoo.com"

MAP_DEFAULTS = {
    "arc_signers": (
        "google.com\nmicrosoft.com\nyahoo.com\nmailgun.org\nmailchannels.net\n"
        "dkim.mimecast.com\ncheckpointcloudsec.com\npphosted.com\nsendgrid.net\namazonses.com"
    ),
    "greylist_ips": "",
    "greylist_domains": "",
    "url_regexps": "",
    "blacklist_domains": "",
    "whitelist_domains": "",
    "redirector_domains": "",
}

SUMMARY_DEFAULTS = {
    "summary_enabled": True,
    "summary_periodicity": "1w",
    "summary_subject": "Quarantine summary for {{ mailbox }}",
    "summary_template": """<h2>Your quarantine summary</h2>
<p>Hello {{ mailbox }}, here are the messages added to your quarantine during the {{ period }} period.</p>
{{ quarantine_table }}
<p><a href=\"{{ quarantine_url }}\">Open your quarantine</a></p>""",
}

DEFAULTS = {**MAP_DEFAULTS, **SUMMARY_DEFAULTS}
SUMMARY_PERIODICITIES = {"1d", "1w", "1m"}

MAP_FIELDS = {
    "arc-signers": "arc_signers",
    "greylist-ips": "greylist_ips",
    "greylist-domains": "greylist_domains",
    "url-regexps": "url_regexps",
    "blacklist-domains": "blacklist_domains",
    "whitelist-domains": "whitelist_domains",
    "redirector-domains": "redirector_domains",
}

_HREF_ATTRIBUTE = re.compile(r'(?P<prefix>\bhref\s*=\s*)(?P<quote>["\'])(?P<value>.*?)(?P=quote)', re.IGNORECASE | re.DOTALL)
_QUARANTINE_URL_TOKEN = re.compile(r'\{\{\s*quarantine_url\s*\}\}', re.IGNORECASE)
_TEMPLATE_TOKEN = re.compile(r'\{\{(.*?)\}\}', re.DOTALL)
_SUMMARY_PLACEHOLDERS = {
    "mailbox": "mailbox",
    "period": "period",
    "quarantine_url": "quarantine_url",
    "quarantine_table": "quarantine_table",
}


def normalize_template_placeholders(template):
    """Normalize template tokens after rich-text editor whitespace changes."""
    template = re.sub(r'(?i)&(?:#0*123|#x0*7b);?', '{', template)
    template = re.sub(r'(?i)&(?:#0*125|#x0*7d);?', '}', template)
    template = template.replace('\u00a0', ' ')

    def normalize_token(match):
        text = html.unescape(re.sub(r'<[^>]*>', '', match.group(1)))
        compact = re.sub(r'\s+', '', text.replace('\u00a0', ' ')).lower()
        placeholder = _SUMMARY_PLACEHOLDERS.get(compact)
        if placeholder:
            return f'{{{{ {placeholder} }}}}'
        return match.group(0)

    template = _TEMPLATE_TOKEN.sub(normalize_token, template)

    def restore(match):
        decoded = unquote(html.unescape(match.group('value')))
        if _QUARANTINE_URL_TOKEN.search(decoded):
            quote = match.group('quote')
            return f"{match.group('prefix')}{quote}{{{{ quarantine_url }}}}{quote}"
        return match.group(0)

    return _HREF_ATTRIBUTE.sub(restore, template)


def get_settings():
    """Return persisted settings merged with defaults for new fields."""
    record = models.db.session.get(models.Config, CONFIG_KEY)
    settings = deepcopy(DEFAULTS)
    local_domains = _local_domains()
    settings["arc_signers"] = _append_lines(MAP_DEFAULTS["arc_signers"], local_domains)
    settings["redirector_domains"] = "\n".join(local_domains)
    if record and isinstance(record.value, dict):
        for key in MAP_DEFAULTS:
            value = record.value.get(key)
            if isinstance(value, str):
                settings[key] = value
        # Upgrade the values previously seeded as defaults while preserving
        # any settings an administrator had already customized.
        if record.value.get("_defaults_version", 0) < SETTINGS_VERSION:
            if settings["arc_signers"].strip() == LEGACY_ARC_SIGNERS:
                settings["arc_signers"] = MAP_DEFAULTS["arc_signers"]
            settings["arc_signers"] = _append_lines(settings["arc_signers"], local_domains)
            settings["redirector_domains"] = _append_lines(
                settings["redirector_domains"], local_domains
            )
        settings["summary_enabled"] = record.value.get(
            "summary_enabled", settings["summary_enabled"]
        ) is True
        periodicity = record.value.get("summary_periodicity")
        if periodicity in SUMMARY_PERIODICITIES:
            settings["summary_periodicity"] = periodicity
        for key in ("summary_subject", "summary_template"):
            value = record.value.get(key)
            if isinstance(value, str):
                settings[key] = (normalize_template_placeholders(value)
                                 if key == 'summary_template' else value)
    return settings


def _local_domains():
    """Return configured domain names and alternatives in stable order."""
    names = {name for (name,) in models.Domain.query.with_entities(models.Domain.name).all()}
    names.update(name for (name,) in
                 models.Alternative.query.with_entities(models.Alternative.name).all())
    return sorted(names, key=str.casefold)


def _append_lines(value, additions):
    """Append unique map entries while preserving existing custom entries."""
    lines = normalize_lines(value)
    seen = {line.casefold() for line in lines}
    for line in additions:
        if line.casefold() not in seen:
            lines.append(line)
            seen.add(line.casefold())
    return "\n".join(lines)


def normalize_lines(value, *, max_lines=1000, max_line_length=2048):
    """Normalize a textarea into safe, non-empty map entries."""
    if (not isinstance(value, str)
            or any(ord(char) < 32 and char not in "\r\n" for char in value)):
        raise ValueError("Invalid map data")
    lines = []
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if len(line) > max_line_length:
            raise ValueError("A map entry is too long")
        lines.append(line)
        if len(lines) > max_lines:
            raise ValueError("Too many map entries")
    return lines


def normalize_settings(values):
    """Validate and normalize the editable map and digest fields."""
    settings = get_settings()
    for key in MAP_DEFAULTS:
        value = values.get(key)
        if not isinstance(value, str) or len(value) > 65536:
            raise ValueError("Invalid spam settings")
        # Catch control characters and unreasonable map entries before saving.
        normalize_lines(value)
        settings[key] = value.replace("\r\n", "\n").replace("\r", "\n")
    enabled = values.get("summary_enabled")
    if not isinstance(enabled, bool):
        raise ValueError("Choose whether quarantine summaries are enabled")
    settings["summary_enabled"] = enabled
    periodicity = values.get("summary_periodicity")
    if periodicity not in SUMMARY_PERIODICITIES:
        raise ValueError("Choose a valid summary periodicity")
    settings["summary_periodicity"] = periodicity
    subject = values.get("summary_subject")
    if (not isinstance(subject, str) or not subject.strip() or len(subject) > 255
            or "\r" in subject or "\n" in subject):
        raise ValueError("Enter a one-line summary subject of at most 255 characters")
    template = values.get("summary_template")
    if not isinstance(template, str):
        raise ValueError("The email template must contain {{ quarantine_table }} exactly once")
    template = normalize_template_placeholders(template)
    if (not template.strip() or len(template) > 65536
            or template.count("{{ quarantine_table }}") != 1):
        raise ValueError("The template must contain {{ quarantine_table }} exactly once")
    settings["summary_subject"] = subject.strip()
    settings["summary_template"] = template
    return settings


def save_settings(values):
    """Persist validated shared spam and quarantine summary settings."""
    settings = normalize_settings(values)
    settings["_defaults_version"] = SETTINGS_VERSION
    record = models.db.session.get(models.Config, CONFIG_KEY)
    if record is None:
        record = models.Config(name=CONFIG_KEY, value=settings)
        models.db.session.add(record)
    else:
        record.value = settings
    models.db.session.commit()
    return settings


def map_content(name):
    """Return the requested map as UTF-8 text or None for unknown maps."""
    field = MAP_FIELDS.get(name)
    if field is None:
        return None
    return "\n".join(normalize_lines(get_settings()[field])) + "\n"
