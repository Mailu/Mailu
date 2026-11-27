"""Keycloak sign-in routes.

The Mailu session cookie is SameSite=Strict, so browsers drop it on the
cross-site redirect back from Keycloak. ``/sso/keycloak/callback`` therefore
never touches the session: it returns a page that continues to
``/sso/keycloak/finish`` as a same-site navigation, which carries the session
holding the pending state, nonce and PKCE verifier.
"""

import flask
import flask_login
from flask import current_app as app
from flask_babel import lazy_gettext as _
from markupsafe import escape

from mailu import keycloak, signin, utils
from mailu.sso import sso
from mailu.sso.views.base import _clear_webmail_cookies


CALLBACK_PARAMS = ('code', 'state', 'error', 'error_description', 'iss')


def _no_store(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


def _client():
    ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    port = flask.request.headers.get('X-Real-Port', None)
    return f'{ip}/{port}'


def _failure(reason, message=None, status=400):
    app.logger.warning(f'Keycloak sign-in failed from {_client()}: {reason}')
    response = flask.make_response(flask.render_template(
        'keycloak_error.html',
        message=message or _('Single sign-on failed. Try again, or contact your administrator.'),
    ), status)
    return _no_store(response)


@sso.route('/keycloak/login', methods=['GET'])
def keycloak_login():
    if not keycloak.enabled():
        flask.abort(404)
    target = flask.request.args.get('target')
    if target in ('admin', 'webmail'):
        signin.clear()
        signin.remember(signin.target_path(target))
    if flask_login.current_user.is_authenticated:
        return flask.redirect(signin.resolve())
    login_hint = flask.request.args.get('login_hint', '')
    if not (0 < len(login_hint) <= 254 and utils.is_valid_email(login_hint)):
        login_hint = None
    try:
        location = keycloak.authorization_redirect(login_hint)
    except keycloak.KeycloakError as exc:
        return _failure(
            exc.reason, _('Single sign-on is temporarily unavailable. Try again later.'), 503,
        )
    return _no_store(flask.redirect(location))


@sso.route('/keycloak/callback', methods=['GET'])
def keycloak_callback():
    if not keycloak.enabled():
        flask.abort(404)
    params = {key: flask.request.args[key] for key in CALLBACK_PARAMS if key in flask.request.args}
    target = flask.url_for('sso.keycloak_finish', **params)
    # Deliberately static: rendering the normal templates would touch the
    # (cookie-less) session and replace the user's real session cookie.
    body = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={escape(target)}">'
        '<title>Signing in…</title></head><body>'
        f'<p><a href="{escape(target)}">Continue signing in</a></p>'
        '</body></html>'
    )
    return _no_store(flask.Response(body, mimetype='text/html'))


@sso.route('/keycloak/finish', methods=['GET'])
def keycloak_finish():
    if not keycloak.enabled():
        flask.abort(404)
    args = flask.request.args
    pending = keycloak.take_pending(args.get('state'))
    if pending is None:
        return _failure('unknown or expired state', _('Your sign-in attempt expired. Try again.'))
    if 'error' in args:
        return _failure(
            f'authorization error {args.get("error")!r}: {args.get("error_description", "")!r}',
            _('Sign-in was cancelled or refused by the identity provider.'),
        )
    # RFC 9207: reject responses that claim to come from another issuer.
    if 'iss' in args and args['iss'].rstrip('/') != app.config['KEYCLOAK_ISSUER']:
        return _failure(f'response issuer {args["iss"]!r} does not match')
    code = args.get('code')
    if not code:
        return _failure('callback lacks an authorization code')

    try:
        claims, id_token = keycloak.exchange_code(code, pending)
        keycloak.check_mfa(claims)
        email = keycloak.email_from_claims(claims)
        user = keycloak.find_or_create_user(email)
    except keycloak.KeycloakError as exc:
        return _failure(exc.reason, exc.message)

    destination = signin.resolve()
    signin.clear()
    flask.session.regenerate()
    flask_login.login_user(user)
    flask.session[keycloak.SESSION_AUTH_METHOD] = 'keycloak'
    flask.session[keycloak.SESSION_ID_TOKEN] = id_token
    app.logger.info(
        f'Login attempt for: {user}/sso/keycloak from: {_client()}: success: '
        f'sub={claims.get("sub")!r} acr={claims.get("acr")!r} amr={claims.get("amr")!r}'
    )
    response = _clear_webmail_cookies(flask.redirect(destination))
    return _no_store(signin.remember_preference(response, destination))
