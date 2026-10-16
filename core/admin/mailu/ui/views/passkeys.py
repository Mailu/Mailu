import hashlib

import flask
import flask_login
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _
from webauthn import (
    generate_registration_options, options_to_json,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AttestationConveyancePreference, AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
    ResidentKeyRequirement, UserVerificationRequirement,
)

from mailu import models, passkeys as webauthn_config
from mailu.ui import ui, access


def _challenge_key():
    return 'passkey_registration_challenge'


@ui.route('/user/passkeys', methods=['GET'], defaults={'user_email': None})
@ui.route('/user/passkeys/<path:user_email>', methods=['GET'])
@access.owner(models.User, 'user_email')
def passkey_list(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    return flask.render_template(
        'user/passkeys.html', user=user,
        passkeys=[(key, bytes_to_base64url(key.credential_id)) for key in user.passkeys],
        delete_form=FlaskForm(),
    )


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
    options = generate_registration_options(
        rp_id=webauthn_config.rp_id(),
        rp_name=flask.current_app.config['SITENAME'],
        user_id=hashlib.sha256(user.email.encode()).digest(),
        user_name=user.email,
        user_display_name=user.displayed_name or user.email,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=key.credential_id)
            for key in user.passkeys
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement(domain.passkey_resident_key),
            user_verification=(
                UserVerificationRequirement.REQUIRED
                if domain.passkey_require_uv
                else UserVerificationRequirement.PREFERRED
            ),
        ),
        attestation=(
            AttestationConveyancePreference.DIRECT
            if domain.passkey_attestation_policy == 'require'
            else AttestationConveyancePreference.NONE
        ),
    )
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
        verification = verify_registration_response(
            credential=payload,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=webauthn_config.rp_id(),
            expected_origin=webauthn_config.origin(),
            require_user_verification=user.domain.passkey_require_uv,
        )
    except Exception as exc:
        flask.current_app.logger.warning(
            'Passkey registration failed actor=%s user=%s domain=%s result=verification_failed '
            'reason=%s: %s ip=%s',
            actor.email, user.email, user.domain.name, type(exc).__name__, exc, client_ip,
        )
        return flask.jsonify(error='Passkey registration could not be verified.'), 400
    credential_id = verification.credential_id
    attestation_format = webauthn_config.enum_value(verification.fmt)
    flags = webauthn_config.authenticator_flags(payload, registration=True)
    if not webauthn_config.aaguid_allowed(user.domain, verification.aaguid):
        flask.current_app.logger.warning(
            'Passkey registration rejected actor=%s user=%s domain=%s aaguid=%s '
            'reason=aaguid_policy ip=%s',
            actor.email, user.email, user.domain.name, verification.aaguid, client_ip,
        )
        return flask.jsonify(error='This authenticator is not allowed for this domain.'), 400
    if user.domain.passkey_device_bound and (
        webauthn_config.enum_value(verification.credential_device_type) != 'single_device'
        or verification.credential_backed_up
    ):
        flask.current_app.logger.warning(
            'Passkey registration rejected actor=%s user=%s domain=%s aaguid=%s '
            'device_type=%s backed_up=%s reason=device_bound_policy ip=%s',
            actor.email, user.email, user.domain.name, verification.aaguid,
            webauthn_config.enum_value(verification.credential_device_type),
            verification.credential_backed_up, client_ip,
        )
        return flask.jsonify(error='This domain only allows device-bound passkeys.'), 400
    if not webauthn_config.authenticator_flags_allowed(user.domain, flags):
        return flask.jsonify(error='This authenticator does not meet the domain backup requirements.'), 400
    if not webauthn_config.attestation_allowed(user.domain, attestation_format):
        return flask.jsonify(error='Authenticator attestation does not meet the domain policy.'), 400
    if models.db.session.get(models.Passkey, credential_id):
        flask.current_app.logger.warning(
            'Passkey registration rejected actor=%s user=%s domain=%s credential=%s aaguid=%s '
            'reason=duplicate_credential ip=%s',
            actor.email, user.email, user.domain.name, bytes_to_base64url(credential_id)[:16],
            verification.aaguid, client_ip,
        )
        return flask.jsonify(error='This passkey is already registered.'), 409
    credential = models.Passkey(
        user=user,
        credential_id=credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        aaguid=verification.aaguid,
        device_bound=(
            webauthn_config.enum_value(verification.credential_device_type) == 'single_device'
            and not verification.credential_backed_up
        ),
        user_verified=verification.user_verified,
        user_present=flags.up,
        credential_device_type=webauthn_config.enum_value(verification.credential_device_type),
        backup_eligible=flags.be,
        backed_up=verification.credential_backed_up,
        attestation_format=attestation_format,
        name=str(payload.get('name') or 'Passkey')[:255],
    )
    models.db.session.add(credential)
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
