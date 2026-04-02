# Two-Factor Authentication (TOTP) — Planning Document

> **Note for reviewers:** This planning document is included for review context only.
> It should be removed before merging, or moved to the wiki/issue discussion if preferred.

**Status:** Implemented  
**Date:** 2026-04-02  
**Branch:** `feat-2fa-totp`  
**Upstream:** Mailu has zero 2FA support today  
**Upstream Issues:** [#783](https://github.com/Mailu/Mailu/issues/783) (Redesign auth systems), [#2222](https://github.com/Mailu/Mailu/issues/2222) (2FA/SSO considerations)

---

## 1. Goal

Add optional TOTP-based two-factor authentication to Mailu so that users can
protect their web login (SSO/Admin) with a time-based one-time password
(Google Authenticator, Authy, etc.), while keeping IMAP/SMTP/POP3 mail client
access working via the existing App Token mechanism.

---

## 1a. Context & Alternatives

### Why native 2FA instead of an external IdP?

Mailu already supports delegating authentication to external identity providers
(Authelia, Authentik, Keycloak) via Header Authentication (`PROXY_AUTH_HEADER`).
This is considered the "enterprise best practice" — the IdP handles MFA
(TOTP, WebAuthn, push notifications) and Mailu trusts the validated header.

However, native 2FA is still valuable because:

- **Simplicity:** many self-hosters run Mailu standalone without a reverse proxy
  IdP stack. Requiring Authelia/Authentik just for TOTP adds significant
  infrastructure complexity (separate service, LDAP/file backend, proxy config).
- **Turnkey experience:** native 2FA works out of the box — no external
  dependencies, no proxy whitelisting, no header spoofing risks to manage.
- **Complementary:** native 2FA does not conflict with external IdP setups.
  If `PROXY_AUTH_HEADER` is configured, native 2FA is skipped (the IdP is
  already handling MFA). Both paths can coexist.

This aligns with upstream discussion in [#783](https://github.com/Mailu/Mailu/issues/783)
and [#2222](https://github.com/Mailu/Mailu/issues/2222), where native 2FA has been
a long-requested feature.

### Webmail-level 2FA plugins (not our approach)

Roundcube has a `twofactor_gauthenticator` plugin and SnappyMail has a built-in
2FA plugin. These protect webmail access only — they do NOT protect the Admin UI
or SSO login, creating a siloed security layer. Our approach implements 2FA at
the SSO layer, which gates all web access (admin + webmail) through a single
checkpoint. This is architecturally cleaner and avoids the fragmented auth
that Mailu 1.9's SSO consolidation was designed to eliminate.

---

## 2. Current Auth Architecture (as-is)

### 2.1 Web login (SSO)
- **Route:** `sso/views/base.py` → `POST /sso/login`
- **Flow:** email + password → `models.User.login()` → `flask_login.login_user()` → redirect
- Password-change interception exists: if `user.change_pw_next_login`, session
  stores redirect and sends user to `/sso/pw_change` first
- Session: Redis-backed `MailuSession` with regeneration on login

### 2.2 Mail protocol auth (IMAP/SMTP/POP3/Sieve)
- **Module:** `internal/nginx.py` → `check_credentials()`
- nginx sends HTTP auth sub-request to admin; admin validates and returns headers
- **App Tokens** (`models.Token`): 32-char hex passwords stored with low-round PBKDF2
  - Checked first if `is_app_token(password)` returns True
  - Already bypass normal password flow
  - Optional IP restriction per token
- `AUTH_REQUIRE_TOKENS` config: when True, plain password rejected for non-web protocols

### 2.3 Webmail SSO
- Roundcube plugin reads `X-Remote-User` / `X-Remote-User-Token` headers
- Snappymail uses `CreateUserSsoHash()` from same headers
- Temp tokens (`token-<base64>`) stored in Redis for webmail sessions

### 2.4 User model (`models.py:552`)
- `User(Base, Email)` with `password`, `enabled`, `global_admin`, etc.
- Password hashing: `passlib` bcrypt-sha256 with credential cache
- Related: `Token` model for app passwords

### 2.5 Dependencies (from `requirements-prod.txt`)
- `passlib==1.7.4`, `bcrypt==4.1.3`, `cryptography==42.0.6`
- `Flask-Login==0.6.3`, `Flask-WTF==1.2.1`, `WTForms==3.1.2`
- No OTP/TOTP/QR libraries present

---

## 3. Design Decisions

### 3.1 Where does 2FA apply?

| Protocol / Entry Point    | 2FA Required? | Rationale                                       |
|---------------------------|---------------|-------------------------------------------------|
| Web SSO (`/sso/login`)    | Yes           | Primary target — browser-based, high-value      |
| Admin UI (`/admin/*`)     | Yes (via SSO) | All admin routes require SSO session             |
| Webmail (Roundcube/Snappy)| Yes (via SSO) | Webmail login redirects through SSO              |
| IMAP / POP3               | No            | Use App Tokens; TOTP impractical for clients     |
| SMTP / Submission         | No            | Use App Tokens; mail clients can't prompt TOTP   |
| Sieve                     | No            | Use App Tokens                                   |
| REST API                  | No            | Bearer token auth (separate mechanism)           |
| Proxy Auth                | No            | External IdP handles MFA upstream                |

**Key principle:** 2FA protects the *web session*. Mail clients use App Tokens
(which are already separate credentials with optional IP restriction). When
`AUTH_REQUIRE_TOKENS` is enabled, plain password is rejected for mail protocols,
making App Tokens the only path — and those bypass 2FA by design.

### 3.2 TOTP algorithm
- Standard: RFC 6238 (TOTP), RFC 4226 (HOTP base)
- Library: `pyotp` (lightweight, well-maintained, MIT licensed)
- QR code: `qrcode[pil]` or `segno` (for provisioning URI → QR image)
- Parameters: SHA-1, 6 digits, 30-second period (Google Authenticator defaults)
- Clock skew tolerance: 1 step (±30s)

### 3.3 Backup / recovery codes
- 10 single-use codes generated at setup time
- Stored hashed (low-round PBKDF2, same pattern as App Tokens)
- Displayed once at setup; user must save them
- Each code can only be used once; consumed codes are deleted
- Admin (global_admin or domain_admin) can reset a user's 2FA

### 3.4 Enforcement model
- **Per-user opt-in** (default): each user chooses to enable 2FA via settings
- **Domain-level enforcement** (future/optional): domain admin can require 2FA
  for all users in their domain — similar to `change_pw_next_login` pattern
- **Global enforcement** (future/optional): config flag `REQUIRE_2FA=true`

Phase 1 implements per-user opt-in only.

### 3.5 Admin override
- Global admins and domain admins can disable/reset 2FA for users they manage
- Shown on user edit page (`/admin/user/edit/<email>`)
- Logged for audit

---

## 4. Database Changes

### 4.1 New columns on `user` table

```python
# models.py — User class additions
totp_secret    = db.Column(db.String(255), nullable=True, default=None)
totp_enabled   = db.Column(db.Boolean, nullable=False, default=False)
```

- `totp_secret`: Fernet-encrypted base32 shared secret (~120 chars, None = not enrolled).
  Accessed via `User.get_totp_secret()` / `User.set_totp_secret()` which
  handle encrypt/decrypt using a key derived from `SECRET_KEY`.
- `totp_enabled`: True only after user confirms setup with a valid code

### 4.2 New table: `backup_code`

```python
class BackupCode(Base):
    __tablename__ = 'backup_code'

    id         = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), db.ForeignKey('user.email'), nullable=False)
    user       = db.relationship(User, backref=db.backref('backup_codes', cascade='all, delete-orphan'))
    code_hash  = db.Column(db.String(255), nullable=False)
```

- 10 codes generated at setup
- Each is 8 alphanumeric chars (e.g. `a3f7-k9m2`)
- Hashed with `pbkdf2_sha256.using(rounds=1)` (same as Token — high entropy, not bruteforceable)
- Row deleted after successful use

### 4.3 Migration
- Alembic migration via `flask db migrate`
- Must use `batch_alter_table` for SQLite compatibility (per contributor docs)
- Single migration file: adds `totp_secret` + `totp_enabled` columns, creates `backup_code` table

---

## 5. Implementation Plan — Phases

### Phase 0: Dependencies & Branch Setup
- [ ] Create branch `feat-2fa-totp` from `master`
- [ ] Add `pyotp` and `segno` (or `qrcode`) to `requirements-prod.txt`
- [ ] Rebuild base image to verify clean install
- [ ] Add towncrier fragment: `towncrier/newsfragments/XXXX.feature`

### Phase 1: Model & Migration
- [ ] Add `totp_secret`, `totp_enabled` to `User` model
- [ ] Create `BackupCode` model
- [ ] Generate Alembic migration (batch ops for SQLite)
- [ ] Test migration up/down locally

### Phase 2: TOTP Setup UI (User Settings)
- [ ] New route: `GET/POST /user/2fa` (in `ui/views/users.py`)
- [ ] Access: `@access.owner` (same as user_settings)
- [ ] **Setup flow:**
  1. Generate secret → store in session (not DB yet)
  2. Render QR code (provisioning URI) + manual key display
  3. User enters 6-digit code to confirm
  4. On valid code: save `totp_secret` to DB, set `totp_enabled=True`
  5. Generate and display 10 backup codes (one-time view)
- [ ] **Disable flow:**
  1. User confirms with current password + TOTP code
  2. Clear `totp_secret`, set `totp_enabled=False`, delete backup codes
- [ ] **Regenerate backup codes:**
  1. Confirm with password + TOTP code
  2. Delete old codes, generate new set, display once
- [ ] Form: `UserTOTPSetupForm` in `ui/forms.py`
- [ ] Templates: `user/2fa_setup.html`, `user/2fa_backup_codes.html`
- [ ] i18n: wrap all strings with `_()` / `{% trans %}`

### Phase 3: Login Flow Modification
- [ ] Modify `sso/views/base.py` → `login()`:
  - After successful `User.login()`, check `user.totp_enabled`
  - If True: do NOT call `flask_login.login_user()` yet
  - Store `user.email` and `destination` in session as `pending_2fa_user`
  - Redirect to new route `/sso/2fa`
- [ ] New route: `GET/POST /sso/2fa`
  - Render TOTP input form (6-digit code + "Use backup code" link)
  - Validate code via `pyotp.TOTP(user.totp_secret).verify(code, valid_window=1)`
  - If backup code: check against `BackupCode` table, delete on success
  - On success: complete login (`flask_login.login_user()`, session regeneration, rate-limit cookie)
  - On failure: flash error, increment rate limiter
  - Timeout: if session `pending_2fa_user` is stale (>5 min), redirect to login
- [ ] New form: `TOTPVerifyForm` in `sso/forms.py`
- [ ] New template: `sso/templates/2fa_verify.html`

### Phase 4: Admin Controls
- [ ] User edit page (`/admin/user/edit/<email>`):
  - Show 2FA status (enabled/disabled)
  - "Reset 2FA" button (domain_admin or global_admin only)
  - Logs the reset action
- [ ] Optional: user list shows 2FA status icon/badge

### Phase 5: Testing
- [ ] Unit tests for TOTP verification logic
- [ ] Unit tests for backup code generation, hashing, consumption
- [ ] Integration test: full login flow with 2FA
- [ ] Integration test: app token bypasses 2FA for IMAP
- [ ] Integration test: admin reset flow
- [ ] Test with SQLite, PostgreSQL, MariaDB (migration compatibility)

### Phase 6: Documentation & i18n
- [ ] Extract Babel strings: `pybabel extract` / `pybabel update`
- [ ] Update `docs/configuration.rst` if any new env vars added
- [ ] Update `docs/webadministration.rst` with 2FA user guide
- [ ] Towncrier fragment for changelog

---

## 6. Login Flow Diagram (to-be)

```
User submits email + password
         │
         ▼
  ┌─────────────┐
  │ Rate limit   │──── exceeded ──→ Flash error, stay on login
  │ check        │
  └──────┬──────┘
         │ ok
         ▼
  ┌─────────────┐
  │ User.login() │──── fail ──→ Flash "wrong email/password"
  │ (password)   │
  └──────┬──────┘
         │ success
         ▼
  ┌─────────────────┐
  │ user.totp_enabled│
  │ == True ?        │
  └──┬──────────┬───┘
     │ no       │ yes
     ▼          ▼
  Complete   Store pending_2fa_user
  login      in session, redirect
  (as today) to /sso/2fa
                │
                ▼
         ┌─────────────┐
         │ User enters  │
         │ 6-digit code │
         │ or backup    │
         └──────┬──────┘
                │
         ┌──────┴──────┐
         │ Valid?       │
         └──┬──────┬───┘
            │ no   │ yes
            ▼      ▼
         Flash   Complete login
         error   (flask_login.login_user)
         (retry  → redirect to destination
         or back
         to login)
```

---

## 7. Security Considerations

1. **Secret storage:** `totp_secret` is a shared secret that must be readable to
   verify codes (unlike passwords, it cannot be one-way hashed). Two options:

   - **Option A — Plaintext in DB:** standard practice in most implementations
     (Django-OTP, Authelia, many others). Relies on DB-level encryption at rest.
     Simpler, fewer moving parts, no key management.

   - **Option B — Application-level encryption (recommended):** encrypt the
     secret using `cryptography.fernet.Fernet` with a key derived from Mailu's
     `SECRET_KEY` config. The secret is decrypted in-memory only when verifying
     a TOTP code. This provides defense-in-depth: a DB dump alone does not
     expose TOTP secrets. The `cryptography` library is already a dependency.

   **Decision:** Option B. The `cryptography` package is already in
   `requirements-prod.txt`, so there is no new dependency. The `totp_secret`
   column stores the Fernet-encrypted blob (base64, ~120 chars). Helper methods
   `User.get_totp_secret()` and `User.set_totp_secret(secret)` handle
   encrypt/decrypt transparently. If `SECRET_KEY` is rotated, a migration
   helper re-encrypts all secrets.

2. **QR code:** generated server-side, never stored; rendered inline as base64
   data URI or served from a one-time endpoint.

3. **Session hijacking:** `pending_2fa_user` session key expires after 5 minutes.
   Session ID is regenerated after full login completes.

4. **Brute force:** rate limiter already applies to login. The 2FA step reuses
   the same rate-limit counters. 6-digit TOTP with 1-step window = 3 valid
   codes at any time (999,997 invalid) — combined with rate limiting, brute
   force is infeasible.

5. **Backup codes:** single-use, hashed. 10 codes of 8 alphanumeric chars
   (~41 bits entropy each). Sufficient for recovery, not for daily use.

6. **App Tokens:** explicitly bypass 2FA. This is by design — they are
   long random credentials with optional IP binding. The existing
   `AUTH_REQUIRE_TOKENS` config already forces users to create tokens for
   mail clients, which is the recommended setup when 2FA is enabled.

7. **Admin reset:** domain/global admins can disable a user's 2FA. This is
   necessary for account recovery when backup codes are lost. The action
   is logged.

---

## 8. Files to Modify / Create

### Modified files
| File | Change |
|------|--------|
| `core/admin/mailu/models.py` | Add `totp_secret`, `totp_enabled` to User; add `BackupCode` model |
| `core/admin/mailu/sso/views/base.py` | 2FA challenge after password success |
| `core/admin/mailu/sso/forms.py` | Add `TOTPVerifyForm` |
| `core/admin/mailu/ui/views/users.py` | Add `user_2fa_setup`, admin reset route |
| `core/admin/mailu/ui/forms.py` | Add `UserTOTPSetupForm` |
| `core/admin/mailu/ui/templates/user/settings.html` | Link to 2FA setup page |
| `core/admin/mailu/ui/templates/user/edit.html` | Show 2FA status + reset button |
| `core/base/requirements-prod.txt` | Add `pyotp`, `segno` |

### New files
| File | Purpose |
|------|---------|
| `core/admin/migrations/versions/<hash>_add_totp_2fa.py` | Alembic migration |
| `core/admin/mailu/sso/templates/2fa_verify.html` | TOTP code input page |
| `core/admin/mailu/ui/templates/user/2fa_setup.html` | QR code + setup form |
| `core/admin/mailu/ui/templates/user/2fa_backup_codes.html` | One-time backup code display |
| `towncrier/newsfragments/XXXX.feature` | Changelog entry |

### Not modified
| File | Reason |
|------|--------|
| `core/admin/mailu/internal/nginx.py` | No changes — App Tokens already bypass password auth; 2FA is session-level only |
| `webmails/roundcube/login/mailu.php` | No changes — webmail auth goes through SSO session |
| `webmails/snappymail/login/sso.php` | No changes — same reason |
| `core/nginx/*` | No changes — nginx proxies auth to admin, protocol unchanged |

---

## 9. Contributor Compliance Checklist

Per `docs/contributors/`:

- [ ] PEP-8 compliant, pylint clean
- [ ] Database models use generic types (no DB-specific config)
- [ ] Migration uses `batch_alter_table` for SQLite compatibility
- [ ] All user-facing strings wrapped with `_()` / `{% trans %}`
- [ ] Babel extraction run before PR (`pybabel extract` / `pybabel update`)
- [ ] Dependency upgrade tested as separate PR first (if major)
- [ ] Towncrier fragment added
- [ ] PR against `master` branch
- [ ] Tested with `docker buildx bake` + `docker compose up`

---

## 10. Open Questions

1. **QR code library choice:** `segno` (pure Python, no PIL dependency, SVG output)
   vs `qrcode[pil]` (more common, needs Pillow). Leaning toward `segno` for
   smaller image size and no binary dependency.

2. **Domain-level enforcement:** should Phase 1 include a `require_2fa` flag on
   the Domain model, or defer to a follow-up? **Recommendation:** defer — keep
   Phase 1 as user opt-in only.

3. **API 2FA:** the REST API uses a single shared bearer token, not per-user auth.
   No 2FA needed there. But if per-user API auth is added later, 2FA should
   apply. Note for future.

4. **Proxy auth:** when `PROXY_AUTH_HEADER` is used, the external IdP is
   responsible for MFA. Mailu should skip its own 2FA check for proxy-authenticated
   sessions. Current design handles this (proxy auth calls `_proxy()` which
   doesn't go through the password flow).

5. **TOTP secret encryption key rotation:** if `SECRET_KEY` changes, all
   Fernet-encrypted `totp_secret` values become unreadable. Need a CLI command
   (`flask mailu reencrypt-totp --old-key <key>`) or document that changing
   `SECRET_KEY` requires users to re-enroll 2FA. **Recommendation:** document
   the constraint for Phase 1; add re-encryption CLI in a follow-up if needed.

---

## 11. Future Phases (beyond this implementation)

### 11.1 WebAuthn / FIDO2 (phishing-resistant 2FA)

TOTP is vulnerable to real-time phishing (attacker proxies the code to the
legitimate server). WebAuthn uses public-key cryptography tied to the specific
domain, making phishing mathematically impossible. This is the gold standard
for high-security environments.

**What it would require:**
- New dependency: `py_webauthn` or `fido2` (Python WebAuthn library)
- New DB table: `webauthn_credential` (credential ID, public key, sign count, user)
- Registration flow: browser `navigator.credentials.create()` → server stores public key
- Login flow: browser `navigator.credentials.get()` → server verifies signature
- UI changes: JavaScript for WebAuthn API calls in login and setup pages
- Users could register multiple keys (primary + backup hardware key)

**When:** after native TOTP is stable and adopted. WebAuthn can coexist with
TOTP as an alternative second factor (user chooses which to use at login).

### 11.2 XOAUTH2 / OIDC (protocol-level 2FA)

The fundamental limitation today is that IMAP/SMTP can't do interactive 2FA.
XOAUTH2 (SASL OAuth 2.0) solves this by allowing mail clients to trigger a
browser-based login flow, where the user completes MFA in the browser and the
client receives an OAuth token.

A fork already exists: [heviat/Mailu-OIDC](https://github.com/heviat/Mailu-OIDC)
(also tracked in upstream [#2575](https://github.com/Mailu/Mailu/issues/2575)).

**What it would require:**
- Mailu acting as an OIDC provider (or consuming an external OIDC provider)
- Dovecot and Postfix configured for XOAUTH2 SASL mechanism
- Token refresh flow for long-lived mail client sessions
- Significant complexity — this is a major architectural change

**When:** this is a longer-term goal. Native TOTP + App Tokens is the pragmatic
solution for now. XOAUTH2 would eventually make App Tokens unnecessary.

### 11.3 Domain-level and global enforcement

Phase 1 is per-user opt-in. Future phases could add:
- `Domain.require_2fa` (Boolean) — domain admin forces all users to enroll
- `REQUIRE_2FA` env var — global enforcement for all users
- Grace period: users get N days to set up 2FA before being locked to the
  setup page (similar to `change_pw_next_login` pattern)

### 11.4 Trusted devices / "Remember this browser"

After completing 2FA, the user could opt to trust the device for N days
(stored as a signed cookie). This reduces friction for daily webmail use
while maintaining security for new devices/locations. Common in Gmail,
GitHub, etc.
