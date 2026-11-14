"""Issue and consume single-use account setup links."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from mailu import models


def issue(user, lifetime):
    """Replace any outstanding setup link and return its raw token and expiry."""
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=lifetime)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    models.AccountSetupToken.query.filter_by(user_email=user.email).delete(synchronize_session=False)
    models.db.session.add(models.AccountSetupToken(
        token_hash=token_hash,
        user_email=user.email,
        expires_at=expires_at,
    ))
    return raw_token, expires_at


def lookup(raw_token):
    """Return an unexpired token record without exposing the raw token at rest."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    grant = models.db.session.get(models.AccountSetupToken, token_hash)
    if not grant:
        return None
    expires_at = grant.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return grant if expires_at > datetime.now(timezone.utc) else None


def consume(raw_token):
    """Atomically remove an unexpired token; return whether it was consumed."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return models.AccountSetupToken.query.filter_by(token_hash=token_hash).filter(
        models.AccountSetupToken.expires_at > datetime.now(timezone.utc),
    ).delete(synchronize_session=False) == 1
