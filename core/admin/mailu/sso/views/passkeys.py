import flask
import flask_login
from webauthn import (
    generate_authentication_options, options_to_json,
    verify_authentication_response,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement

from mailu import models, utils, passkeys as webauthn_config, auth_flow
from mailu.sso import sso


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
    destination = flask.session.pop('passkey_login_redirect', None) or destination
    flask.session['passkey_login_destination'] = destination
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    if utils.limiter.should_rate_limit_ip(client_ip) or utils.limiter.should_rate_limit_user(email, client_ip):
        return flask.jsonify(error='Too many sign-in attempts. Try again later.'), 429
    user = models.User.get(email) if email else None
    credentials = user.passkeys if user and user.enabled else []
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
    return flask.jsonify(flask.json.loads(options_to_json(options)))

@sso.route('/passkey/verify', methods=['POST'])
def passkey_authenticate():
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
    email_for_rate_limit = email or (credential.user_email if credential else '')
    if not credential or not credential.user.enabled:
        flask.current_app.logger.warning(
            'Passkey authentication failed user=%r credential=%s result=unknown_or_disabled ip=%s',
            email or None, bytes_to_base64url(credential_id)[:16],
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        utils.limiter.rate_limit_user(email_for_rate_limit, flask.request.headers.get('X-Real-IP', flask.request.remote_addr))
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
            credential_current_sign_count=credential.sign_count,
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
        utils.limiter.rate_limit_user(email_for_rate_limit, flask.request.headers.get('X-Real-IP', flask.request.remote_addr))
        return flask.jsonify(error='Passkey sign-in failed.'), 401
    domain = credential.user.domain
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
        utils.limiter.rate_limit_user(email_for_rate_limit, flask.request.headers.get('X-Real-IP', flask.request.remote_addr))
        return flask.jsonify(error='Passkey sign-in failed.'), 401
    credential.sign_count = verification.new_sign_count
    credential.device_bound = (
        webauthn_config.enum_value(verification.credential_device_type) == 'single_device'
        and not verification.credential_backed_up
    )
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
        'uv=%s device_type=%s backed_up=%s device_bound=%s->%s sign_count=%s->%s '
        'uv_required=%s device_bound_required=%s resident_key=%s rp_id=%s ip=%s',
        credential.user_email, domain.name, bytes_to_base64url(credential.credential_id)[:16],
        credential.aaguid, verification.user_verified,
        webauthn_config.enum_value(verification.credential_device_type),
        verification.credential_backed_up, current_device_bound, credential.device_bound,
        current_sign_count, verification.new_sign_count,
        domain.passkey_require_uv, domain.passkey_device_bound, domain.passkey_resident_key,
        webauthn_config.rp_id(), client_ip,
    )
    webauthn_config.clear_password_passkey_nudge(flask.session)
    destination = flask.session.pop('passkey_login_destination', None)
    flask.session.regenerate()
    flask_login.login_user(credential.user)
    if credential.user.change_pw_next_login:
        auth_flow.require_actions(flask.session, 'password_change', destination)
        return flask.jsonify(redirect=flask.url_for('sso.pw_change'))
    return flask.jsonify(redirect=destination or flask.current_app.config['WEB_ADMIN'])
