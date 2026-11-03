"""Quarantine operations and summaries backed by a shared message repository."""
import calendar
import html
import re
import uuid
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit, urlunsplit
from pathlib import Path

from flask import current_app
import requests
import nh3

from mailu import models, quarantine_repository, spam_settings


def directory():
    path = Path('/data/quarantine')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def cleanup_expired(retention_days):
    """Expire both types of stored messages in the shared repository."""
    return quarantine_repository.cleanup_expired(directory(), retention_days)


def entries(kind='quarantine'):
    """Return repository records, defaulting to actual quarantine messages."""
    cleanup_expired(current_app.config['QUARANTINE_RETENTION_DAYS'])
    return quarantine_repository.entries(directory(), kind=kind)


def all_entries():
    """Return quarantine and pending greylist records from one repository."""
    cleanup_expired(current_app.config['QUARANTINE_RETENTION_DAYS'])
    return quarantine_repository.entries(directory())


def visible_recipients(metadata, user):
    """Return mailbox recipients this user is allowed to view for a message."""
    recipients = [address for address in metadata.get('recipients', [])
                  if isinstance(address, str)]
    if user.global_admin:
        return recipients
    if hasattr(user, 'get_managed_domains'):
        managed_domains = user.get_managed_domains()
    else:
        managed_domains = getattr(user, 'manager_of', [])
    managed = {domain.name.lower() for domain in managed_domains}
    return [address for address in recipients
            if address.lower() == user.email.lower()
            or ('@' in address and address.rsplit('@', 1)[-1].lower() in managed)]


def visible_entries(user, source_entries=None):
    """Filter quarantine records to the mailboxes visible to this user."""
    source_entries = entries() if source_entries is None else source_entries
    return [item for item in source_entries if visible_recipients(item, user)]


def get(message_id):
    try:
        message_id = str(uuid.UUID(message_id))
    except (ValueError, TypeError, AttributeError):
        return None
    return quarantine_repository.get(
        directory(), message_id, 'quarantine',
        current_app.config['QUARANTINE_RETENTION_DAYS'],
    )


def get_any(record_id):
    """Read a rejected or greylisted record by its public repository ID."""
    try:
        message_id = str(uuid.UUID(record_id))
    except (ValueError, TypeError, AttributeError):
        if not isinstance(record_id, str) or not re.fullmatch(r'[0-9a-f]{64}', record_id):
            return None
        return quarantine_repository.get(
            directory(), record_id, 'greylist',
            quarantine_repository.GREYLIST_RETENTION_DAYS,
        )
    return get(message_id)


def store(raw_message, metadata):
    if not raw_message or len(raw_message) > current_app.config['QUARANTINE_MAX_MESSAGE_BYTES']:
        raise ValueError('message size is invalid')
    message_id = str(uuid.uuid4())
    return quarantine_repository.store(directory(), message_id, raw_message, metadata, 'quarantine')


def delete(message_id):
    try:
        message_id = str(uuid.UUID(message_id))
    except (ValueError, TypeError, AttributeError):
        if not isinstance(message_id, str) or not re.fullmatch(r'[0-9a-f]{64}', message_id):
            return False
        return quarantine_repository.delete(directory(), message_id, 'greylist')
    return quarantine_repository.delete(directory(), message_id, 'quarantine')


def flush(message_ids):
    """Remove the given visible held messages from the shared repository."""
    count = 0
    for message_id in dict.fromkeys(message_ids):
        count += bool(quarantine_repository.delete(directory(), message_id))
    return count


def learn_ham(raw_message):
    """Submit a released message to the same Rspamd learners used by Sieve."""
    base_url = f"http://{current_app.config.get('ANTISPAM_ADDRESS', 'antispam')}:11334"
    password = 'mailu'  # Matches worker-controller.inc and Dovecot's ham.script.
    commands = (
        ('learnham', {}),
        ('fuzzydel', {'Flag': '11'}),
        ('fuzzyadd', {'Flag': '13', 'Weight': '1'}),
    )
    failures = []
    for command, extra_headers in commands:
        response = None
        try:
            response = requests.post(
                f'{base_url}/{command}',
                headers={'Password': password, 'Content-Type': 'application/octet-stream',
                         **extra_headers},
                data=raw_message,
                timeout=5,
            )
            response.raise_for_status()
        except requests.Timeout:
            failures.append(f'{command}: timeout')
        except requests.RequestException:
            reason = f'HTTP {response.status_code}' if response is not None else 'connection error'
            failures.append(f'{command}: {reason}')
    return failures


def safe_preview(message_path, limit=20000):
    """Return a bounded plain-text preview; HTML mail is shown as source text."""
    try:
        parsed = BytesParser(policy=policy.default).parsebytes(message_path.read_bytes())
        for part in parsed.walk():
            if part.get_content_disposition() == 'attachment':
                continue
            if part.get_content_type() in ('text/plain', 'text/html'):
                content = part.get_content()
                if isinstance(content, str):
                    return content[:limit]
    except (OSError, ValueError, LookupError):
        current_app.logger.warning('Could not parse quarantined message preview')
    return ''


SUMMARY_STATE_KEY = 'rspamd_quarantine_summary_state'
SUMMARY_TABLE_TOKEN = 'MAILU_QUARANTINE_SUMMARY_TABLE_SLOT'
SUMMARY_URL_TOKEN = 'https://mailu-summary-placeholder.invalid/'
SUMMARY_TAGS = {
    'p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'ol', 'ul',
    'li', 'a', 'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
}


def _shift_period(value, periodicity, amount=1):
    if periodicity == '1d':
        return value + timedelta(days=amount)
    if periodicity == '1w':
        return value + timedelta(days=7 * amount)
    if periodicity == '1m':
        month_index = value.year * 12 + (value.month - 1) + amount
        year, month = divmod(month_index, 12)
        month += 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)
    raise ValueError('Invalid summary periodicity')


def _received(metadata):
    try:
        value = metadata.get('received')
        if not isinstance(value, str):
            return None
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def summary_messages(user, source_entries, periodicity, *, mailbox_emails=None,
                     period_start=None, now=None):
    """Select period-matching records scoped to one or more visible mailboxes."""
    now = now or datetime.now(timezone.utc)
    start = period_start or _shift_period(now, periodicity, -1)
    allowed = ({user.email.lower()} if mailbox_emails is None else
               {address.lower() for address in mailbox_emails if isinstance(address, str)})
    selected = []
    for entry in source_entries:
        recipients = {address.lower() for address in entry.get('recipients', [])
                      if isinstance(address, str)}
        visible = sorted(recipients & allowed)
        received = _received(entry)
        if visible and received is not None and start <= received <= now:
            visible_entry = dict(entry)
            visible_entry['recipients'] = visible
            selected.append(visible_entry)
    return sorted(selected, key=lambda item: item.get('received', ''), reverse=True)


def _quarantine_base_url():
    configured = str(current_app.config.get('WEB_ADMIN') or '/admin').strip()
    parsed = urlsplit(configured)
    if parsed.scheme in {'http', 'https'} and parsed.netloc:
        origin = f'{parsed.scheme}://{parsed.netloc}'
        admin_path = parsed.path.rstrip('/') or '/admin'
    else:
        hostname = str(current_app.config.get('HOSTNAMES') or current_app.config['DOMAIN']).split(',')[0].strip()
        scheme = 'http' if str(current_app.config.get('TLS_FLAVOR', '')).lower() == 'notls' else 'https'
        origin = f'{scheme}://{hostname}'
        admin_path = '/' + configured.lstrip('/').strip('/') if configured.strip('/') else '/admin'
    return origin + admin_path


def _summary_table(entries):
    rows = []
    for entry in entries:
        message_id = entry.get('id')
        if not isinstance(message_id, str):
            continue
        url = f'{_quarantine_base_url()}/quarantine/{quote(message_id, safe="")}'
        fields = (
            str(entry.get('received') or ''), str(entry.get('from') or ''),
            str(entry.get('subject') or ''), str(entry.get('score') if entry.get('score') is not None else ''),
            ', '.join(address for address in entry.get('recipients', [])
                      if isinstance(address, str)),
        )
        cells = ''.join(f'<td>{html.escape(value)}</td>' for value in fields)
        rows.append(f'<tr>{cells}<td><a href="{html.escape(url, quote=True)}">View</a></td></tr>')
    if not rows:
        rows.append('<tr><td colspan="6">No messages were quarantined during this period.</td></tr>')
    return (
        '<table border="1" cellpadding="4" cellspacing="0">'
        '<thead><tr><th>Received</th><th>From</th><th>Subject</th><th>Score</th><th>Mailbox</th><th>View</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


class _SummaryPlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.link = None

    def handle_starttag(self, tag, attrs):
        if tag in {'p', 'br', 'h1', 'h2', 'h3', 'blockquote', 'tr', 'li'}:
            self.parts.append('\n' + ('* ' if tag == 'li' else ''))
        elif tag in {'td', 'th'} and self.parts:
            self.parts.append(' | ')
        if tag == 'a':
            self.link = dict(attrs).get('href')

    def handle_endtag(self, tag):
        if tag == 'a' and self.link:
            self.parts.append(f' <{self.link}>')
            self.link = None
        if tag in {'p', 'h1', 'h2', 'h3', 'blockquote', 'tr', 'li'}:
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)


def render_summary(settings, user, entries, *, test=False, period_start=None, now=None,
                   mailbox_emails=None):
    """Build a safe HTML and plain-text digest for one mailbox."""
    now = now or datetime.now(timezone.utc)
    periodicity = settings['summary_periodicity']
    messages = summary_messages(
        user, entries, periodicity, mailbox_emails=mailbox_emails,
        period_start=period_start, now=now,
    )
    period_label = {'1d': 'one day', '1w': 'one week', '1m': 'one month'}[periodicity]
    quarantine_url = f'{_quarantine_base_url()}/quarantine'
    subject = settings['summary_subject'].replace('{{ mailbox }}', user.email).replace('{{ period }}', period_label)
    if test:
        subject = f'[TEST] {subject}'
    template = spam_settings.normalize_template_placeholders(settings['summary_template'])
    if template.count('{{ quarantine_table }}') != 1:
        raise ValueError('The email template must contain {{ quarantine_table }} exactly once')
    template = template.replace('{{ quarantine_table }}', SUMMARY_TABLE_TOKEN)
    template = template.replace('{{ quarantine_url }}', SUMMARY_URL_TOKEN)
    template = template.replace('{{ mailbox }}', html.escape(user.email))
    template = template.replace('{{ period }}', html.escape(period_label))
    sanitized = nh3.clean(
        template,
        tags=SUMMARY_TAGS,
        attributes={'a': {'href', 'title'}, 'table': {'border', 'cellpadding', 'cellspacing'}},
        url_schemes={'http', 'https', 'mailto'},
        clean_content_tags={'script', 'style', 'iframe', 'object'},
    )
    # The rich-text editor stores a standalone placeholder as a paragraph.
    # Remove that wrapper before inserting the generated table: a table cannot
    # be a child of <p>, and some mail clients otherwise display it poorly.
    sanitized = re.sub(
        rf'<p>\s*{re.escape(SUMMARY_TABLE_TOKEN)}\s*</p>',
        SUMMARY_TABLE_TOKEN,
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = sanitized.replace(SUMMARY_URL_TOKEN, html.escape(quarantine_url, quote=True))
    sanitized = sanitized.replace(SUMMARY_TABLE_TOKEN, _summary_table(messages))
    parser = _SummaryPlainText()
    parser.feed(sanitized)
    plain = '\n'.join(line.rstrip() for line in ''.join(parser.parts).splitlines()).strip()
    if not plain:
        raise ValueError('The email template must contain readable text')
    return subject, plain, sanitized


def send_due_summaries():
    """Send due quarantine digests, independently tracked for each mailbox."""
    settings = spam_settings.get_settings()
    if not settings['summary_enabled']:
        return 0
    now = datetime.now(timezone.utc)
    all_entries = entries()
    state_record = models.db.session.get(models.Config, SUMMARY_STATE_KEY)
    state = dict(state_record.value) if state_record and isinstance(state_record.value, dict) else {}
    sent = 0
    for user in models.User.query.filter_by(enabled=True).order_by(models.User.email).all():
        key = user.email.lower()
        previous = None
        try:
            if isinstance(state.get(key), str):
                previous = datetime.fromisoformat(state[key].replace('Z', '+00:00'))
                if previous.tzinfo is None:
                    previous = previous.replace(tzinfo=timezone.utc)
        except ValueError:
            previous = None
        if previous and _shift_period(previous, settings['summary_periodicity']) > now:
            continue
        start = previous or _shift_period(now, settings['summary_periodicity'], -1)
        recipient = user.email.lower()
        messages = [item for item in all_entries
                    if recipient in {address.lower() for address in item.get('recipients', [])
                                     if isinstance(address, str)}
                    and (received := _received(item)) is not None
                    and received > start and received <= now]
        if not messages:
            state[key] = now.isoformat()
            continue
        subject, plain, html_body = render_summary(
            settings, user, messages, period_start=start, now=now,
        )
        if not user.sendmail(subject, plain, html_body=html_body):
            continue
        state[key] = now.isoformat()
        sent += 1
        state_record = models.db.session.get(models.Config, SUMMARY_STATE_KEY)
        if state_record is None:
            state_record = models.Config(name=SUMMARY_STATE_KEY, value=state)
            models.db.session.add(state_record)
        else:
            state_record.value = state
        models.db.session.commit()
    if state_record is None and state:
        models.db.session.add(models.Config(name=SUMMARY_STATE_KEY, value=state))
        models.db.session.commit()
    elif state_record is not None and sent == 0 and state != state_record.value:
        state_record.value = state
        models.db.session.commit()
    return sent
