"""Shared sign-in destination handling; destinations stay in server-side sessions."""
from urllib.parse import urljoin, urlsplit, unquote
import time
import flask

KEY = 'signin_destination'
PREFERENCE_COOKIE = 'mailu_signin_target'

def target_path(target):
    config = flask.current_app.config
    if target == 'admin' and str(config['ADMIN']).upper() != 'FALSE':
        return config['WEB_ADMIN']
    if target == 'webmail' and str(config['WEBMAIL']).upper() != 'NONE':
        return config['WEB_WEBMAIL']
    flask.abort(404)

def default_target():
    preference = flask.request.cookies.get(PREFERENCE_COOKIE)
    if preference == 'admin' and str(flask.current_app.config['ADMIN']).upper() != 'FALSE':
        return preference
    if preference == 'webmail' and str(flask.current_app.config['WEBMAIL']).upper() != 'NONE':
        return preference
    return 'webmail' if str(flask.current_app.config['WEBMAIL']).upper() != 'NONE' else 'admin'

def local_destination(value):
    if not isinstance(value, str) or not value or any(c in unquote(value) for c in ('\\', '\r', '\n')):
        return None
    origin = urlsplit(flask.request.host_url)
    try:
        target = urlsplit(urljoin(flask.request.host_url, value))
    except ValueError:
        return None
    if target.scheme != origin.scheme or target.netloc != origin.netloc:
        return None
    path = target.path or '/'
    if path.startswith(('/sso/', '/internal/')) or path.startswith('//'):
        return None
    return path + ('?' + target.query if target.query else '')

def remember(value):
    destination = local_destination(value)
    if destination:
        flask.session[KEY] = {'path': destination, 'expires': time.time() + 1800}
    return destination

def pending():
    state = flask.session.get(KEY, {})
    if state.get('expires', 0) > time.time():
        return local_destination(state.get('path'))
    flask.session.pop(KEY, None)
    return None

def resolve(target=None):
    return target_path(target) if target else pending() or target_path(default_target())

def clear():
    flask.session.pop(KEY, None)
    flask.session.pop('passkey_login_redirect', None)


def remember_preference(response, destination):
    """Remember the application selected at successful authentication, never a URL."""
    path = urlsplit(destination).path
    config = flask.current_app.config
    admin = config['WEB_ADMIN'].rstrip('/')
    webmail = config['WEB_WEBMAIL'].rstrip('/')
    target = None
    if admin and (path == admin or path.startswith(admin + '/')):
        target = 'admin'
    elif path == webmail or path.startswith(webmail + '/'):
        target = 'webmail'
    if target:
        response.set_cookie(PREFERENCE_COOKIE, target, max_age=31536000, path='/sso',
                            secure=config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
    return response
