import flask
import flask_login
import hashlib
import hmac
import secrets
from flask_babel import lazy_gettext as _
from datetime import datetime, timezone
from flask_wtf.csrf import validate_csrf
from sqlalchemy.exc import IntegrityError
from wtforms.validators import ValidationError
from webauthn import (
    generate_authentication_options, options_to_json,
    verify_authentication_response,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement
from flask_wtf import FlaskForm

from mailu import models, utils, signin, passkeys as webauthn_config, auth_flow, setup_tokens
from mailu.sso import sso, forms


def _csrf_error():
    if not flask.current_app.config.get('WTF_CSRF_ENABLED', True):
        return None
    try:
        validate_csrf(flask.request.headers.get('X-CSRFToken'))
    except ValidationError:
        return flask.jsonify(error='Your sign-in session expired. Reload the page and try again.'), 400
    return None


def _account_setup_requires_passkey(user):
    return bool(
        user.passkey_enroll_next_login
        or user.domain.passkey_require_enrollment
        or flask.current_app.config.get('PASSKEY_REQUIRED', False)
    )


def _render_account_setup(user, token, password_form=None, registration_form=None,
                          allow_password=None, passkey_options_url=None,
                          passkey_register_url=None, status=200):
    if allow_password is None:
        allow_password = not _account_setup_requires_passkey(user) and not user.passkeys
    response = flask.make_response(flask.render_template(
        'account_setup.html', user=user, token=token,
        password_form=password_form or forms.AccountSetupForm(),
        registration_form=registration_form or FlaskForm(),
        allow_password=allow_password,
        demo_account_email=utils.DEMO_ACCOUNT_EMAIL,
        passkey_options_url=passkey_options_url or flask.url_for(
            'sso.account_setup_options', token=token,
        ),
        passkey_register_url=passkey_register_url or flask.url_for(
            'sso.account_setup_register', token=token,
        ),
    ), status)
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response


@sso.route('/account/setup/<token>', methods=['GET'], endpoint='account_setup')
@sso.route('/passkey/enroll/<token>', methods=['GET'], endpoint='passkey_enroll')
def account_setup(token):
    grant = setup_tokens.lookup(token) or flask.abort(404)
    if not grant.user.enabled:
        flask.abort(404)
    return _render_account_setup(grant.user, token)


def _pending_passkey_signup(token):
    state = flask.session.get('pending_passkey_signup')
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if (not state or not hmac.compare_digest(state.get('token_hash', ''), token_hash)
            or state.get('expires_at', 0) <= datetime.now(timezone.utc).timestamp()):
        return None, None
    domain = models.db.session.get(models.Domain, state.get('domain_name'))
    if not domain or not domain.signup_enabled:
        return None, None
    try:
        localpart, domain_name = state['email'].rsplit('@', 1)
    except (KeyError, ValueError):
        return None, None
    if domain_name != domain.name:
        return None, None
    user = models.User(localpart=localpart, domain=domain)
    user.quota_bytes = state['quota_bytes']
    return state, user


def _signup_address_conflict(user):
    domain = user.domain
    if domain.has_email(user.localpart) or models.Alias.resolve(user.localpart, domain.name):
        return True
    return domain.max_users != -1 and len(domain.users) >= domain.max_users


@sso.route('/account/setup/signup/<token>', methods=['GET'])
def passkey_signup(token):
    state, user = _pending_passkey_signup(token)
    if not state or not user:
        flask.abort(404)
    if _signup_address_conflict(user):
        flask.session.pop('pending_passkey_signup', None)
        flask.flash(_('That email address is no longer available. Start signup again with a different address.'), 'error')
        return flask.redirect(flask.url_for('ui.user_signup', domain_name=user.domain.name))
    return _render_account_setup(
        user, token, allow_password=False,
        passkey_options_url=flask.url_for('sso.passkey_signup_options', token=token),
        passkey_register_url=flask.url_for('sso.passkey_signup_register', token=token),
    )


@sso.route('/account/setup/signup/<token>/options', methods=['POST'])
def passkey_signup_options(token):
    if error := _csrf_error():
        return error
    state, user = _pending_passkey_signup(token)
    if not state or not user:
        return flask.jsonify(error='This signup attempt has expired. Start again.'), 410
    if _signup_address_conflict(user):
        flask.session.pop('pending_passkey_signup', None)
        return flask.jsonify(error='This email address is no longer available. Start signup again.'), 409
    options = webauthn_config.registration_options(user)
    flask.session['passkey_signup_hash'] = state['token_hash']
    flask.session['passkey_signup_challenge'] = bytes_to_base64url(options.challenge)
    return flask.jsonify(flask.json.loads(options_to_json(options)))


@sso.route('/account/setup/signup/<token>/register', methods=['POST'])
def passkey_signup_register(token):
    if error := _csrf_error():
        return error
    state, user = _pending_passkey_signup(token)
    challenge = flask.session.pop('passkey_signup_challenge', None)
    session_hash = flask.session.pop('passkey_signup_hash', None)
    payload = flask.request.get_json(silent=True)
    if (not state or not user or session_hash != state['token_hash']
            or not challenge or not payload):
        return flask.jsonify(error='This signup attempt has expired. Start again.'), 410
    if _signup_address_conflict(user):
        flask.session.pop('pending_passkey_signup', None)
        return flask.jsonify(error='This email address is no longer available. Start signup again.'), 409
    try:
        webauthn_config.register_credential(user, payload, challenge)
    except webauthn_config.PasskeyRegistrationError as exc:
        flask.current_app.logger.warning(
            'Public passkey signup rejected user=%s reason=%s', user.email, exc.reason,
        )
        return flask.jsonify(error=str(exc)), exc.status

    user.password = models.User.get_password_context().hash(secrets.token_urlsafe(32))
    user.change_pw_next_login = False
    try:
        models.db.session.add(user)
        models.db.session.commit()
    except IntegrityError:
        models.db.session.rollback()
        flask.session.pop('pending_passkey_signup', None)
        return flask.jsonify(error='This email address is no longer available. Start signup again.'), 409

    user.send_welcome()
    flask_login.logout_user()
    flask.session.clear()
    flask.flash(_('Your account is ready. You can now sign in with your passkey.'), 'success')
    return flask.jsonify(ok=True, redirect=flask.url_for('sso.login'))


@sso.route('/account/setup/<token>/options', methods=['POST'], endpoint='account_setup_options')
@sso.route('/passkey/enroll/<token>/options', methods=['POST'], endpoint='passkey_enrollment_options')
def account_setup_options(token):
    if error := _csrf_error():
        return error
    grant = setup_tokens.lookup(token)
    if not grant or not grant.user.enabled:
        return flask.jsonify(error='This account setup link has expired or was already used.'), 410
    user = grant.user
    if utils.is_demo_account(user):
        return flask.jsonify(error=utils.DEMO_ACCOUNT_NOTICE), 403
    options = webauthn_config.registration_options(user)
    flask.session['account_setup_hash'] = grant.token_hash
    flask.session['account_setup_challenge'] = bytes_to_base64url(options.challenge)
    return flask.jsonify(flask.json.loads(options_to_json(options)))


@sso.route('/account/setup/<token>/register', methods=['POST'], endpoint='account_setup_register')
@sso.route('/passkey/enroll/<token>/register', methods=['POST'], endpoint='passkey_enrollment_register')
def account_setup_register(token):
    if error := _csrf_error():
        return error
    grant = setup_tokens.lookup(token)
    challenge = flask.session.pop('account_setup_challenge', None)
    session_hash = flask.session.pop('account_setup_hash', None)
    payload = flask.request.get_json(silent=True)
    if not grant or not grant.user.enabled or session_hash != grant.token_hash or not challenge or not payload:
        return flask.jsonify(error='This account setup link has expired. Start again with a new link.'), 410
    user = grant.user
    if utils.is_demo_account(user):
        return flask.jsonify(error=utils.DEMO_ACCOUNT_NOTICE), 403
    try:
        registration = webauthn_config.register_credential(user, payload, challenge)
    except webauthn_config.PasskeyRegistrationError as exc:
        flask.current_app.logger.warning(
            'Passkey enrollment-link registration rejected user=%s reason=%s',
            user.email, exc.reason,
        )
        return flask.jsonify(error=str(exc)), exc.status
    if not setup_tokens.consume(token):
        models.db.session.rollback()
        return flask.jsonify(error='This account setup link has expired or was already used.'), 410
    user.passkey_enroll_next_login = False
    models.db.session.commit()
    flask.session.pop('account_setup_hash', None)
    if (flask_login.current_user.is_authenticated
            and flask_login.current_user.email == user.email
            and 'passkey_enrollment' in flask.session.get(auth_flow.SESSION_ACTIONS, [])):
        response = auth_flow.complete_action(flask.session, 'passkey_enrollment')
        return flask.jsonify(ok=True, redirect=response.location)
    flask_login.logout_user()
    flask.session.clear()
    flask.flash(_('Passkey added. You can now sign in.'), 'success')
    return flask.jsonify(ok=True, redirect=flask.url_for('sso.login'))


@sso.route('/account/setup/<token>/password', methods=['POST'])
def account_setup_password(token):
    grant = setup_tokens.lookup(token)
    if not grant or not grant.user.enabled:
        flask.abort(404)
    user = grant.user
    if utils.is_demo_account(user):
        flask.abort(403, utils.DEMO_ACCOUNT_NOTICE)
    if _account_setup_requires_passkey(user) or user.passkeys:
        flask.abort(403)

    form = forms.AccountSetupForm()
    if form.validate_on_submit():
        if form.pw.data != form.pw.data.strip():
            form.pw.errors.append(_('Passwords should not start or end with whitespaces'))
        elif msg := utils.isBadOrPwned(form):
            form.pw.errors.append(msg)
        else:
            if not setup_tokens.consume(token):
                models.db.session.rollback()
                return flask.jsonify(error='This setup link has expired or was already used.'), 410
            user.set_password(form.pw.data)
            user.change_pw_next_login = False
            models.db.session.commit()
            flask_login.logout_user()
            flask.session.clear()
            flask.flash(_('Password set. You can now sign in.'), 'success')
            return flask.redirect(flask.url_for('sso.login'))

    return _render_account_setup(
        user, token, password_form=form,
        status=400 if flask.request.method == 'POST' else 200,
    )


@sso.route('/passkey/options', methods=['POST'])
def passkey_authentication_options():
    payload = flask.request.get_json(silent=True) or {}
    email = (payload.get('email') or '').strip()
    if email and not utils.is_valid_email(email):
        return flask.jsonify(error='Enter a valid email address, or leave it blank to choose a passkey.'), 400
    target = payload.get('target', 'admin')
    if target == 'admin' and str(flask.current_app.config['ADMIN']).upper() != 'FALSE':
        destination = flask.current_app.config['WEB_ADMIN']
    elif target == 'webmail' and str(flask.current_app.config['WEBMAIL']).upper() != 'NONE':
        destination = flask.current_app.config['WEB_WEBMAIL']
    else:
        return flask.jsonify(error='Invalid sign-in destination.'), 400
    destination = signin.pending() or destination
    flask.session['passkey_login_destination'] = destination
    user = models.User.get(email) if email else None
    credentials = user.passkeys if user and user.enabled else []
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    flask.current_app.logger.debug(
        'Passkey authentication options email=%r discoverable=%s credentials=%d ip=%s',
        email or None, not bool(email), len(credentials), client_ip,
    )
    options = generate_authentication_options(
        rp_id=webauthn_config.rp_id(),
        allow_credentials=(
            [PublicKeyCredentialDescriptor(id=key.credential_id) for key in credentials]
            if email else None
        ),
        user_verification=(
            UserVerificationRequirement.REQUIRED
            if not email or (user and user.domain.passkey_require_uv)
            else UserVerificationRequirement.PREFERRED
        ),
    )
    flask.session['passkey_login_challenge'] = bytes_to_base64url(options.challenge)
    if email:
        flask.session['passkey_login_email'] = email
    else:
        flask.session.pop('passkey_login_email', None)
    options_json = flask.json.loads(options_to_json(options))
    if not email:
        # Conditional mediation requests discoverable credentials. Omit the
        # member entirely so browsers treat every discoverable credential as eligible.
        options_json.pop('allowCredentials', None)
    return flask.jsonify(options_json)


@sso.route('/passkey/status', methods=['POST'])
def passkey_status():
    payload = flask.request.get_json(silent=True) or {}
    email = (payload.get('email') or '').strip()
    if not email or not utils.is_valid_email(email):
        return flask.jsonify(error='Enter a valid email address.'), 400
    user = models.User.get(email)
    return flask.jsonify(
        has_passkey=bool(user and user.enabled and user.passkeys),
        password_required=bool(flask.current_app.config.get('PASSKEY_REQUIRED', False)),
        enrollment_required=bool(
            user and user.enabled and not user.passkeys and (
                user.passkey_enroll_next_login
                or user.domain.passkey_require_enrollment
                or flask.current_app.config.get('PASSKEY_REQUIRED', False)
            )
        ),
    )

@sso.route('/passkey/verify', methods=['POST'])
def passkey_authenticate():
    if error := _csrf_error():
        return error
    challenge = flask.session.pop('passkey_login_challenge', None)
    email = flask.session.pop('passkey_login_email', None)
    payload = flask.request.get_json(silent=True)
    if not challenge or not payload:
        flask.current_app.logger.warning('Passkey authentication rejected reason=expired_challenge ip=%s', flask.request.remote_addr)
        return flask.jsonify(error='Sign-in expired. Please try again.'), 400
    try:
        credential_id = base64url_to_bytes(payload.get('id', ''))
    except (TypeError, ValueError):
        flask.current_app.logger.warning('Passkey authentication rejected reason=malformed_credential_id ip=%s', flask.request.remote_addr)
        return flask.jsonify(error='The browser returned an invalid passkey credential.'), 400
    query = models.Passkey.query.filter_by(credential_id=credential_id)
    if email:
        query = query.filter_by(user_email=email)
    credential = query.first()
    if not credential or not credential.user.enabled:
        flask.current_app.logger.warning(
            'Passkey authentication failed user=%r credential=%s result=unknown_or_disabled ip=%s',
            email or None, bytes_to_base64url(credential_id)[:16],
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        return flask.jsonify(error='Passkey sign-in failed.'), 401
    domain = credential.user.domain
    if not webauthn_config.aaguid_allowed(domain, credential.aaguid):
        flask.current_app.logger.warning(
            'Passkey authentication rejected user=%s credential=%s aaguid=%s '
            'reason=aaguid_policy ip=%s',
            credential.user_email, bytes_to_base64url(credential.credential_id)[:16],
            credential.aaguid,
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        return flask.jsonify(error='Passkey sign-in failed.'), 401
    current_sign_count = credential.sign_count
    current_device_bound = credential.device_bound
    try:
        verification = verify_authentication_response(
            credential=payload,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=webauthn_config.rp_id(),
            expected_origin=webauthn_config.origin(),
            credential_public_key=credential.public_key,
            credential_current_sign_count=(
                credential.sign_count if domain.passkey_require_sign_count_increase else 0
            ),
            require_user_verification=credential.user.domain.passkey_require_uv,
        )
    except Exception as exc:
        flask.current_app.logger.warning(
            'Passkey authentication failed user=%s credential=%s aaguid=%s '
            'uv_required=%s reason=%s: %s ip=%s',
            credential.user_email, bytes_to_base64url(credential.credential_id)[:16],
            credential.aaguid, credential.user.domain.passkey_require_uv,
            type(exc).__name__, exc,
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        return flask.jsonify(error='Passkey sign-in failed.'), 401
    flags = webauthn_config.authenticator_flags(payload)
    if not webauthn_config.authenticator_flags_allowed(domain, flags):
        flask.current_app.logger.warning(
            'Passkey authentication rejected user=%s credential=%s up=%s uv=%s be=%s bs=%s '
            'reason=backup_policy ip=%s',
            credential.user_email, bytes_to_base64url(credential.credential_id)[:16],
            flags.up, flags.uv, flags.be, flags.bs,
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        return flask.jsonify(error='Passkey sign-in failed.'), 401
    if not webauthn_config.sign_count_allowed(domain, current_sign_count, verification.new_sign_count):
        flask.current_app.logger.warning(
            'Passkey authentication rejected user=%s credential=%s sign_count=%s->%s '
            'reason=sign_count_policy ip=%s',
            credential.user_email, bytes_to_base64url(credential.credential_id)[:16],
            current_sign_count, verification.new_sign_count,
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        return flask.jsonify(error='Passkey sign-in failed.'), 401
    if domain.passkey_device_bound and (
        webauthn_config.enum_value(verification.credential_device_type) != 'single_device'
        or verification.credential_backed_up
    ):
        flask.current_app.logger.warning(
            'Passkey authentication rejected user=%s credential=%s aaguid=%s '
            'device_type=%s backed_up=%s reason=device_bound_policy ip=%s',
            credential.user_email, bytes_to_base64url(credential.credential_id)[:16],
            credential.aaguid,
            webauthn_config.enum_value(verification.credential_device_type),
            verification.credential_backed_up,
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        return flask.jsonify(error='Passkey sign-in failed.'), 401
    credential.sign_count = verification.new_sign_count
    credential.device_bound = (
        webauthn_config.enum_value(verification.credential_device_type) == 'single_device'
        and not verification.credential_backed_up
    )
    credential.user_verified = verification.user_verified
    credential.user_present = flags.up
    credential.credential_device_type = webauthn_config.enum_value(verification.credential_device_type)
    credential.backup_eligible = flags.be
    credential.backed_up = flags.bs
    credential.last_used_at = datetime.now(timezone.utc)
    models.db.session.commit()
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    client_port = flask.request.headers.get('X-Real-Port')
    flask.current_app.logger.info(
        'Login attempt for: %s/sso/%s from: %s/%s: success: passkey: %r (AAGUID: %s)',
        credential.user_email, flask.request.headers.get('X-Forwarded-Proto'),
        client_ip, client_port, credential.name, credential.aaguid,
    )
    flask.current_app.logger.info(
        'Passkey authentication success user=%s domain=%s credential=%s aaguid=%s '
        'up=%s uv=%s be=%s bs=%s device_type=%s backed_up=%s device_bound=%s->%s sign_count=%s->%s '
        'uv_required=%s device_bound_required=%s resident_key=%s rp_id=%s ip=%s',
        credential.user_email, domain.name, bytes_to_base64url(credential.credential_id)[:16],
        credential.aaguid, flags.up, verification.user_verified, flags.be, flags.bs,
        webauthn_config.enum_value(verification.credential_device_type),
        verification.credential_backed_up, current_device_bound, credential.device_bound,
        current_sign_count, verification.new_sign_count,
        domain.passkey_require_uv, domain.passkey_device_bound, domain.passkey_resident_key,
        webauthn_config.rp_id(), client_ip,
    )
    webauthn_config.clear_password_passkey_nudge(flask.session)
    destination = flask.session.pop('passkey_login_destination', None)
    signin.clear()
    flask.session.regenerate()
    flask_login.login_user(credential.user)
    response = signin.remember_preference(
        flask.jsonify(redirect=destination or flask.current_app.config['WEB_ADMIN']),
        destination or flask.current_app.config['WEB_ADMIN'],
    )
    response.set_cookie(
        'rate_limit', utils.limiter.device_cookie(credential.user_email),
        max_age=31536000, path=flask.url_for('sso.login'),
        secure=flask.current_app.config['SESSION_COOKIE_SECURE'], httponly=True,
    )
    return response
