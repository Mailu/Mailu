"""Best-effort per-domain storage checks for inbound SMTP."""

from mailu import models


def _recipient_domains(address):
    """Return domains owning local mailboxes reached by this recipient."""
    if not isinstance(address, str) or address.count('@') != 1:
        return set()
    localpart, domain_name = models.Email.resolve_domain(address.strip().lower())
    if not localpart or not models.db.session.get(models.Domain, domain_name):
        return set()

    mailboxes = models.Email.resolve_mailboxes(address)
    if mailboxes:
        return {mailbox.domain_name for mailbox in mailboxes}

    destinations = models.Email.resolve_destination(localpart, domain_name)
    if destinations is None:
        # Let Postfix's regular recipient checks reject unknown local addresses.
        return {domain_name}
    return set()


def check_domain_quota(recipient, incoming_size=0):
    """Return per-domain usage checks for the mailbox destinations of recipient.

    Usage comes from Dovecot quota-clone and is intentionally treated as a
    best-effort snapshot. Postfix calls this once per RCPT, before delivery, so
    simultaneous deliveries can exceed the configured limit.
    """
    checks = []
    for domain_name in sorted(_recipient_domains(recipient)):
        domain = models.db.session.get(models.Domain, domain_name)
        limit = domain.max_domain_quota_bytes
        if not limit:
            continue
        used = models.db.session.query(
            models.db.func.coalesce(models.db.func.sum(models.User.quota_bytes_used), 0)
        ).filter_by(domain_name=domain_name).scalar() or 0
        over_limit = used >= limit or used + incoming_size > limit
        checks.append({
            'domain': domain_name,
            'used': int(used),
            'limit': int(limit),
            'allowed': not over_limit,
        })
    return {
        'allowed': all(check['allowed'] for check in checks),
        'domains': checks,
    }
