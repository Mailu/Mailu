"""Session state and request enforcement for required user actions."""

import flask
from urllib.parse import urljoin, urlparse


SESSION_ACTIONS = 'required_actions'
SESSION_DESTINATION = 'required_actions_destination'

# Register action IDs against their endpoint here. Additional action handlers
# can complete themselves with ``complete_action`` after the user finishes.
ACTION_ENDPOINTS = {}
ACTION_ENDPOINTS['password_change'] = 'sso.pw_change'


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
    if handler:
        return flask.redirect(flask.url_for(handler))

    flask.current_app.logger.error('Unknown required session action: %s', action)
    flask.session.pop(SESSION_ACTIONS, None)
    flask.session.pop(SESSION_DESTINATION, None)
