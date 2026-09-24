from .. import models, utils
from . import v1
from flask import request
import flask
import flask_login
import urllib.parse
import hmac
from functools import wraps
from flask_restx import abort
import sqlalchemy

def fqdn_in_use(name):
    names = sqlalchemy.union_all(
        sqlalchemy.select(models.Domain.name.label('name')),
        sqlalchemy.select(models.Alternative.name.label('name')),
        sqlalchemy.select(models.Relay.name.label('name')),
    ).subquery()
    return models.db.session.scalar(
        sqlalchemy.select(sqlalchemy.exists().where(names.c.name == name))
    )

""" Decorator for validating api token for authentication """
def api_token_authorization(func):
    @wraps(func)
    def decorated_function(*args, **kwds):
        client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
        if utils.limiter.should_rate_limit_ip(client_ip):
            abort(429, 'Too many attempts from your IP (rate-limit)' )
        if not request.headers.get('Authorization'):
            abort(401, 'A valid Authorization header is mandatory')
        if len(v1.api_token) < 4 or not hmac.compare_digest(request.headers.get('Authorization').removeprefix('Bearer '), v1.api_token):
            utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warning(f'Invalid API token provided by {client_ip}.')
            abort(403, 'Invalid API token')
        flask.current_app.logger.info(f'Valid API token provided by {client_ip}.')
        return func(*args, **kwds)
    return decorated_function


def user_token_authorization(func):
    """Decorator to validate user credentials in the format 'email:token'.
    Uses the same authentication procedure as internal/nginx.py.
    On success it sets `flask.g.user`.
    Supports 'Authentication' header.
    """
    @wraps(func)
    def decorated_function(*args, **kwds):        
        client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
        
        # Rate limit check first
        if utils.limiter.should_rate_limit_ip(client_ip):
            abort(429, 'Too many attempts from your IP (rate-limit)')
        
        auth = request.headers.get('Authentication')
        if not auth:
            if not flask_login.current_user.is_authenticated:
                abort(401, 'A valid Authentication header is mandatory')
            flask.g.user = flask_login.current_user
            return func(*args, **kwds)
        
        user_email, _, token = auth.partition(':')
        if not token:
            utils.limiter.rate_limit_ip(client_ip)
            abort(401, 'Invalid credentials format (expected email:token)')
        
        user_email = urllib.parse.unquote(user_email)
        token = urllib.parse.unquote(token)
        
        # Try to get the user
        user = None
        cause = 'not found'
        try:
            user = models.db.session.get(models.User, user_email)
        except sqlalchemy.exc.StatementError as exc:
            cause, _, _ = str(exc).partition('\n')
        
        if not user:
            utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warning(f'Invalid user {user_email!r} from {client_ip}: {cause}')
            abort(403, 'Invalid credentials')
        
        # IP check (check token IP restrictions in check_credentials_for_api)
        # Check credentials using the same procedure as nginx.py
        if not utils.check_credentials_for_api(user, token, client_ip):
            utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warning(f'Invalid credentials for {user_email} from {client_ip}.')
            abort(403, 'Invalid credentials')
        
        flask.g.user = user
        flask.current_app.logger.info(f'Valid credentials for user {user_email} provided by {client_ip}.')
        return func(*args, **kwds)
    return decorated_function
