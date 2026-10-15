"""Passkey management API."""

import json
import hashlib
import secrets
import time

import flask
from flask_restx import Resource, fields
from webauthn import generate_registration_options, options_to_json, verify_registration_response
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor, ResidentKeyRequirement,
    UserVerificationRequirement,
)

from . import api, response_fields
from .. import common
from ... import models, passkeys as passkey_utils, utils


passkey = api.namespace('passkey', description='Passkey operations')

passkey_fields = api.model('PasskeyInfo', {
    'credential_id': fields.String(description='Base64url passkey credential identifier'),
    'email': fields.String(description='Passkey owner email'),
    'name': fields.String(description='Administrator-provided device name'),
    'aaguid': fields.String(description='Authenticator AAGUID'),
    'device_bound': fields.Boolean(description='Whether the credential is currently device-bound'),
    'sign_count': fields.Integer(description='Authenticator signature counter'),
    'created_at': fields.String(description='Creation date'),
})

registration_options_fields = api.model('PasskeyRegistrationOptions', {
    'request_id': fields.String(description='Short-lived registration request identifier'),
    'options': fields.Raw(description='WebAuthn PublicKeyCredentialCreationOptions'),
})

registration_fields = api.model('PasskeyRegistration', {
    'request_id': fields.String(required=True, description='ID returned by registration-options'),
    'name': fields.String(required=True, description='Name to identify the device'),
    'credential': fields.Raw(required=True, description='Credential returned by navigator.credentials.create()'),
})


def _find_user(email):
    if not utils.is_valid_email(email):
        return None, ({'code': 400, 'message': 'Invalid email address'}, 400)
    user = models.db.session.get(models.User, email)
    if not user:
        return None, ({'code': 404, 'message': f'User {email} cannot be found'}, 404)
    return user, None


def _check_registration_policy(user, verification):
    domain = user.domain
    if not passkey_utils.aaguid_allowed(domain, verification.aaguid):
        return 'Authenticator AAGUID is not allowed for this domain'
    if domain.passkey_device_bound and (
        passkey_utils.enum_value(verification.credential_device_type) != 'single_device'
        or verification.credential_backed_up
    ):
        return 'This domain only allows device-bound passkeys'
    return None


@passkey.route('/user/<string:email>')
class UserPasskeys(Resource):
    @passkey.doc('list_user_passkeys')
    @passkey.marshal_with(passkey_fields, as_list=True, skip_none=True, mask=None)
    @passkey.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, email):
        """List passkeys registered for a user."""
        user, error = _find_user(email)
        if error:
            return error
        return [{
            'credential_id': bytes_to_base64url(item.credential_id),
            'email': item.user_email,
            'name': item.name,
            'aaguid': item.aaguid,
            'device_bound': item.device_bound,
            'sign_count': item.sign_count,
            'created_at': str(item.created_at),
        } for item in user.passkeys]


@passkey.route('/user/<string:email>/registration-options')
class UserPasskeyRegistrationOptions(Resource):
    @passkey.doc('create_user_passkey_registration_options')
    @passkey.marshal_with(registration_options_fields, skip_none=True, mask=None)
    @passkey.doc(responses={400: 'Invalid email', 401: 'Authorization header missing', 403: 'Invalid authorization header', 404: 'User not found'})
    @passkey.doc(security='Bearer')
    @common.api_token_authorization
    def post(self, email):
        """Create a short-lived WebAuthn registration challenge for a user."""
        user, error = _find_user(email)
        if error:
            return error
        domain = user.domain
        options = generate_registration_options(
            rp_id=passkey_utils.rp_id(),
            rp_name=flask.current_app.config['SITENAME'],
            user_id=hashlib.sha256(user.email.encode()).digest(),
            user_name=user.email,
            user_display_name=user.displayed_name or user.email,
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=item.credential_id)
                for item in user.passkeys
            ],
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement(domain.passkey_resident_key),
                user_verification=(
                    UserVerificationRequirement.REQUIRED
                    if domain.passkey_require_uv
                    else UserVerificationRequirement.PREFERRED
                ),
            ),
        )
        request_id = secrets.token_urlsafe(32)
        flask.current_app.session_store.put(
            'api-passkey-registration-' + request_id,
            json.dumps({
                'email': user.email,
                'challenge': bytes_to_base64url(options.challenge),
                'expires_at': time.time() + 300,
            }).encode(),
            ttl=300,
        )
        flask.current_app.logger.info(
            'API passkey registration challenge actor=api-token user=%s domain=%s '
            'uv_required=%s device_bound_required=%s resident_key=%s ip=%s',
            user.email, domain.name,
            domain.passkey_require_uv, domain.passkey_device_bound, domain.passkey_resident_key,
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        return {
            'request_id': request_id,
            'options': flask.json.loads(options_to_json(options)),
        }


@passkey.route('/user/<string:email>')
class UserPasskeyRegistration(Resource):
    @passkey.doc('register_user_passkey')
    @passkey.expect(registration_fields, validate=True)
    @passkey.marshal_with(passkey_fields, skip_none=True, mask=None)
    @passkey.doc(responses={400: 'Invalid registration or policy rejection', 401: 'Authorization header missing', 403: 'Invalid authorization header', 404: 'User not found', 409: 'Credential already registered'})
    @passkey.doc(security='Bearer')
    @common.api_token_authorization
    def post(self, email):
        """Verify and store a user's WebAuthn registration response."""
        user, error = _find_user(email)
        if error:
            return error
        data = api.payload
        if not isinstance(data.get('name'), str) or not data['name'].strip():
            return {'code': 400, 'message': 'A non-empty passkey name is required'}, 400
        request_id = data['request_id']
        challenge_key = 'api-passkey-registration-' + request_id
        try:
            state = json.loads(flask.current_app.session_store.get(challenge_key))
        except (KeyError, TypeError, ValueError):
            return {'code': 400, 'message': 'Registration request expired or invalid'}, 400
        finally:
            flask.current_app.session_store.delete(challenge_key)
        if state.get('expires_at', 0) < time.time():
            return {'code': 400, 'message': 'Registration request expired or invalid'}, 400
        if state.get('email') != user.email:
            return {'code': 400, 'message': 'Registration request does not match the specified user'}, 400
        try:
            verification = verify_registration_response(
                credential=data['credential'],
                expected_challenge=base64url_to_bytes(state['challenge']),
                expected_rp_id=passkey_utils.rp_id(),
                expected_origin=passkey_utils.origin(),
                require_user_verification=user.domain.passkey_require_uv,
            )
        except Exception as exc:
            flask.current_app.logger.warning(
                'API passkey registration failed user=%s reason=%s: %s ip=%s',
                user.email, type(exc).__name__, exc,
                flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
            )
            return {'code': 400, 'message': 'Passkey registration could not be verified'}, 400
        if reason := _check_registration_policy(user, verification):
            flask.current_app.logger.warning(
                'API passkey registration rejected user=%s aaguid=%s reason=%s ip=%s',
                user.email, verification.aaguid, reason,
                flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
            )
            return {'code': 400, 'message': reason}, 400
        credential_id = verification.credential_id
        if models.db.session.get(models.Passkey, credential_id):
            return {'code': 409, 'message': 'Passkey is already registered'}, 409
        attestation = passkey_utils.enum_value(verification.fmt)
        item = models.Passkey(
            user=user,
            credential_id=credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            aaguid=verification.aaguid,
            device_bound=(
                passkey_utils.enum_value(verification.credential_device_type) == 'single_device'
                and not verification.credential_backed_up
            ),
            name=data['name'].strip()[:255],
        )
        models.db.session.add(item)
        models.db.session.commit()
        flask.current_app.logger.info(
            'API passkey registered actor=api-token user=%s credential=%s name=%r aaguid=%s '
            'attestation=%s user_verified=%s device_type=%s backed_up=%s device_bound=%s sign_count=%s ip=%s',
            user.email, bytes_to_base64url(credential_id)[:16], item.name, item.aaguid,
            attestation, verification.user_verified,
            passkey_utils.enum_value(verification.credential_device_type),
            verification.credential_backed_up, item.device_bound, verification.sign_count,
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        return {
            'credential_id': bytes_to_base64url(item.credential_id),
            'email': item.user_email,
            'name': item.name,
            'aaguid': item.aaguid,
            'device_bound': item.device_bound,
            'sign_count': item.sign_count,
            'created_at': str(item.created_at),
        }


@passkey.route('/user/<string:email>/<string:credential_id>')
class UserPasskey(Resource):
    @passkey.doc('delete_user_passkey')
    @passkey.marshal_with(response_fields)
    @passkey.doc(responses={400: 'Invalid credential identifier', 401: 'Authorization header missing', 403: 'Invalid authorization header', 404: 'User or passkey not found'})
    @passkey.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, email, credential_id):
        """Delete a user's passkey."""
        user, error = _find_user(email)
        if error:
            return error
        try:
            credential_key = base64url_to_bytes(credential_id)
        except Exception:
            return {'code': 400, 'message': 'Invalid passkey credential identifier'}, 400
        item = models.db.session.get(models.Passkey, credential_key)
        if not item or item.user_email != user.email:
            return {'code': 404, 'message': 'Passkey not found for the specified user'}, 404
        flask.current_app.logger.info(
            'API passkey deletion actor=api-token user=%s credential=%s name=%r aaguid=%s device_bound=%s ip=%s',
            user.email, credential_id[:16], item.name, item.aaguid, item.device_bound,
            flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
        )
        models.db.session.delete(item)
        models.db.session.commit()
        return {'code': 200, 'message': 'Passkey deleted'}, 200
