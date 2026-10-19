import flask
import flask_login
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _
from webauthn import options_to_json
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes

from mailu import models, passkeys as webauthn_config, auth_flow, setup_tokens
from mailu.ui import ui, access


def _challenge_key():
    return 'passkey_registration_challenge'


@ui.route('/user/passkeys', methods=['GET'], defaults={'user_email': None})
@ui.route('/user/passkeys/<path:user_email>', methods=['GET'])
@access.owner(models.User, 'user_email')
def passkey_list(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    restricted_navigation = (
        user.email == flask_login.current_user.email
        and (
            user.change_pw_next_login
            or 'password_change' in flask.session.get(auth_flow.SESSION_ACTIONS, [])
        )
    )
    return _render_passkey_list(user, restricted_navigation=restricted_navigation)


@ui.route('/user/passkey-required', methods=['GET'])
@access.authenticated
def passkey_required():
    user = flask_login.current_user
    passkey_required = (
        flask.current_app.config.get('PASSKEY_REQUIRED', False)
        or user.domain.passkey_require_enrollment
    )
    if user.passkeys or (not user.passkey_enroll_next_login and not passkey_required):
        if 'passkey_enrollment' in flask.session.get(auth_flow.SESSION_ACTIONS, []):
            response = auth_flow.complete_action(flask.session, 'passkey_enrollment')
            return response
        return flask.redirect(flask.url_for('.passkey_list'))
    return _render_passkey_list(user, required_enrollment=True)


def _render_passkey_list(user, required_enrollment=False, restricted_navigation=False):
    return flask.render_template(
        'user/passkeys.html', user=user,
        passkeys=[(key, bytes_to_base64url(key.credential_id)) for key in user.passkeys],
        delete_form=FlaskForm(),
        required_enrollment=required_enrollment,
        restricted_navigation=restricted_navigation,
    )


@ui.route('/user/setup-link/<path:user_email>', methods=['POST'])
@ui.route('/user/passkeys/<path:user_email>/enrollment-link', methods=['POST'])
@access.domain_admin(models.User, 'user_email')
def account_setup_link(user_email):
    form = FlaskForm()
    if not form.validate_on_submit():
        flask.abort(400)
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    raw_token, expires_at = setup_tokens.issue(
        user, flask.current_app.config['ACCOUNT_SETUP_TOKEN_TTL'],
    )
    models.db.session.commit()
    flask.session['new_account_setup_url'] = flask.url_for(
        'sso.account_setup', token=raw_token, _external=True,
    )
    flask.session['new_account_setup_expires_at'] = expires_at
    return flask.redirect(flask.url_for('ui.user_edit', user_email=user.email))


@ui.route('/user/passkeys/options', methods=['POST'], defaults={'user_email': None})
@ui.route('/user/passkeys/<path:user_email>/options', methods=['POST'])
@access.owner(models.User, 'user_email')
def passkey_registration_options(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    actor = flask_login.current_user
    domain = user.domain
    flask.current_app.logger.debug(
        'Passkey registration options actor=%s user=%s domain=%s credential_count=%d '
        'uv_required=%s resident_key=%s ip=%s',
        actor.email, user.email, domain.name, len(user.passkeys),
        domain.passkey_require_uv, domain.passkey_resident_key,
        flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
    )
    options = webauthn_config.registration_options(user)
    flask.session[_challenge_key()] = bytes_to_base64url(options.challenge)
    flask.session['passkey_registration_user'] = user.email
    return flask.jsonify(flask.json.loads(options_to_json(options)))


@ui.route('/user/passkeys', methods=['POST'], defaults={'user_email': None})
@ui.route('/user/passkeys/<path:user_email>', methods=['POST'])
@access.owner(models.User, 'user_email')
def passkey_register(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    actor = flask_login.current_user
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    challenge = flask.session.pop(_challenge_key(), None)
    challenge_user = flask.session.pop('passkey_registration_user', None)
    payload = flask.request.get_json(silent=True)
    if not challenge or challenge_user != user.email or not payload:
        return flask.jsonify(error='Registration expired. Please try again.'), 400
    try:
        registration = webauthn_config.register_credential(user, payload, challenge)
    except webauthn_config.PasskeyRegistrationError as exc:
        flask.current_app.logger.warning(
            'Passkey registration rejected actor=%s user=%s domain=%s reason=%s ip=%s',
            actor.email, user.email, user.domain.name, exc.reason, client_ip,
        )
        return flask.jsonify(error=str(exc)), exc.status
    verification = registration.verification
    flags = registration.flags
    credential = registration.credential
    attestation_format = registration.attestation_format
    credential_id = credential.credential_id
    user.passkey_enroll_next_login = False
    pending_actions = flask.session.get(auth_flow.SESSION_ACTIONS, [])
    if actor.email == user.email and 'password_change' in pending_actions:
        user.change_pw_next_login = False
    models.db.session.commit()
    flask.current_app.logger.info(
        'Passkey registered actor=%s user=%s domain=%s credential=%s name=%r aaguid=%s '
        'attestation=%s up=%s uv=%s be=%s bs=%s device_type=%s backed_up=%s device_bound=%s sign_count=%s '
        'uv_required=%s device_bound_required=%s resident_key=%s rp_id=%s ip=%s',
        actor.email, user.email, user.domain.name, bytes_to_base64url(credential_id)[:16], credential.name,
        verification.aaguid, attestation_format, flags.up, verification.user_verified,
        flags.be, flags.bs,
        webauthn_config.enum_value(verification.credential_device_type),
        verification.credential_backed_up, credential.device_bound, verification.sign_count,
        user.domain.passkey_require_uv, user.domain.passkey_device_bound, user.domain.passkey_resident_key,
        webauthn_config.rp_id(), client_ip,
    )
    if actor.email == user.email:
        pending_actions = flask.session.get(auth_flow.SESSION_ACTIONS, [])
        action = next((action for action in pending_actions
                       if action in ('password_change', 'passkey_enrollment')), None)
        if action:
            response = auth_flow.complete_action(flask.session, action)
            return flask.jsonify(ok=True, redirect=response.location)
    return flask.jsonify(ok=True)


@ui.route('/user/passkeys/<credential_id>/delete', methods=['POST'], defaults={'user_email': None})
@ui.route('/user/passkeys/<path:user_email>/<credential_id>/delete', methods=['POST'])
@access.owner(models.User, 'user_email')
def passkey_delete(credential_id, user_email):
    form = FlaskForm()
    if not form.validate_on_submit():
        flask.abort(400)
    try:
        credential_key = base64url_to_bytes(credential_id)
    except Exception:
        flask.abort(404)
    user_email = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    credential = models.db.session.get(models.Passkey, credential_key) or flask.abort(404)
    if credential.user_email != user.email:
        flask.abort(404)
    actor = flask_login.current_user
    flask.current_app.logger.info(
        'Passkey deletion actor=%s user=%s domain=%s credential=%s name=%r aaguid=%s device_bound=%s '
        'uv_required=%s device_bound_required=%s resident_key=%s rp_id=%s ip=%s',
        actor.email, user.email, user.domain.name, bytes_to_base64url(credential.credential_id)[:16],
        credential.name, credential.aaguid, credential.device_bound,
        user.domain.passkey_require_uv, user.domain.passkey_device_bound,
        user.domain.passkey_resident_key, webauthn_config.rp_id(),
        flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
    )
    models.db.session.delete(credential)
    models.db.session.commit()
    flask.flash(_('Passkey deleted'))
    return flask.redirect(flask.url_for('.passkey_list', user_email=user.email))
