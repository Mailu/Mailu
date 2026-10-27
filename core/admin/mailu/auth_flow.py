"""Session state and request enforcement for required user actions."""

import flask
from urllib.parse import urljoin, urlparse


SESSION_ACTIONS = 'required_actions'
SESSION_DESTINATION = 'required_actions_destination'

# Register action IDs against their endpoint here. Additional action handlers
# can complete themselves with ``complete_action`` after the user finishes.
ACTION_ENDPOINTS = {}
ACTION_ENDPOINTS['password_change'] = 'sso.pw_change'
ACTION_ENDPOINTS['passkey_enrollment'] = 'ui.passkey_required'
ACTION_ALLOWED_ENDPOINTS = {
    'password_change': {
        'ui.passkey_list', 'ui.passkey_create', 'ui.passkey_registration_options',
        'ui.passkey_register',
    },
    'passkey_enrollment': {
        'ui.passkey_required', 'ui.passkey_list', 'ui.passkey_create', 'ui.passkey_registration_options',
        'ui.passkey_register',
    },
}


def user_required_actions(user):
    """Return the login actions this user must complete, in order."""
    if user.passkeys:
        return []
    passkeys_required = (
        flask.current_app.config.get('PASSKEY_REQUIRED', False)
        or user.domain.passkey_require_enrollment
    )
    actions = []
    if user.change_pw_next_login and not passkeys_required:
        actions.append('password_change')
    if user.passkey_enroll_next_login or passkeys_required:
        actions.append('passkey_enrollment')
    return actions


def require_actions(session, actions, destination=None):
    """Queue required actions and optionally remember their final destination."""
    if isinstance(actions, str):
        actions = [actions]
    pending = session.setdefault(SESSION_ACTIONS, [])
    for action in actions:
        if action not in pending:
            pending.append(action)
    if destination is not None:
        target = urlparse(urljoin(flask.request.url, destination or '/'))
        origin = urlparse(flask.request.url)
        if target.scheme == origin.scheme and target.netloc == origin.netloc:
            session[SESSION_DESTINATION] = target.geturl()


def complete_action(session, action):
    actions = session.get(SESSION_ACTIONS, [])
    if action not in actions:
        raise ValueError('Cannot complete an action that is not pending')
    actions.remove(action)
    if actions:
        session[SESSION_ACTIONS] = actions
        handler = ACTION_ENDPOINTS.get(actions[0])
        if handler is None:
            raise ValueError('No handler registered for pending action: %s' % actions[0])
        return flask.redirect(flask.url_for(handler))
    session.pop(SESSION_ACTIONS, None)
    destination = session.pop(SESSION_DESTINATION, None)
    return flask.redirect(destination or flask.current_app.config['WEB_ADMIN'])


def enforce_pending_actions():
    """Redirect authenticated users to the first outstanding action."""
    import flask_login

    actions = flask.session.get(SESSION_ACTIONS, [])
    if not actions or not flask_login.current_user.is_authenticated:
        return

    endpoint = flask.request.endpoint
    if endpoint in {'static', 'ui.logout', 'sso.logout'}:
        return

    action = actions[0]
    handler = ACTION_ENDPOINTS.get(action)
    if handler and endpoint == handler:
        return
    if endpoint in ACTION_ALLOWED_ENDPOINTS.get(action, ()):
        if endpoint == 'ui.passkey_required':
            return
        user_email = flask.request.view_args.get('user_email') if flask.request.view_args else None
        if user_email in (None, flask_login.current_user.email):
            return
    if handler:
        return flask.redirect(flask.url_for(handler))

    flask.current_app.logger.error('Unknown required session action: %s', action)
    flask.session.pop(SESSION_ACTIONS, None)
    flask.session.pop(SESSION_DESTINATION, None)
