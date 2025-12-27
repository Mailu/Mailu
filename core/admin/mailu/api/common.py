from .. import models, utils
from . import v1
from flask import request
import flask
import flask_login
import hmac
import hashlib
from functools import wraps
from flask_restx import abort
from sqlalchemy.sql.expression import label

def fqdn_in_use(name):
    d = models.db.session.query(label('name', models.Domain.name))
    a = models.db.session.query(label('name', models.Alternative.name))
    r = models.db.session.query(label('name', models.Relay.name))
    u = d.union_all(a).union_all(r).filter_by(name=name)
    if models.db.session.query(u.exists()).scalar():
        return True
    return False

""" Decorator for validating api token for authentication """
def api_token_authorization(func):
    @wraps(func)
    def decorated_function(*args, **kwds):
        client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
        if utils.limiter.should_rate_limit_ip(client_ip):
            abort(429, 'Too many attempts from your IP (rate-limit)' )
        if not request.headers.get('Authorization'):
            if flask_login.current_user.is_authenticated and flask_login.current_user.global_admin:
                return func(*args, **kwds)
            abort(401, 'A valid Authorization header is mandatory')
        if len(v1.api_token) < 4 or not hmac.compare_digest(request.headers.get('Authorization').removeprefix('Bearer '), v1.api_token):
            utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warn(f'Invalid API token provided by {client_ip}.')
            abort(403, 'Invalid API token')
        flask.current_app.logger.info(f'Valid API token provided by {client_ip}.')
        return func(*args, **kwds)
    return decorated_function


def user_token_authorization(func):
    """Decorator to validate a per-user personal access token from the Token table.
    This rejects the global `API_TOKEN` and requires a token associated with a user.
    On success it sets `flask.g.token` and `flask.g.user`.
    Supports both 'Authorization' and 'Authentication' headers for Bitwarden compatibility.
    """
    @wraps(func)
    def decorated_function(*args, **kwds):        
        client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
        if utils.limiter.should_rate_limit_ip(client_ip):
            abort(429, 'Too many attempts from your IP (rate-limit)')
        
        # Check both Authorization and Authentication headers for Bitwarden compatibility
        auth = request.headers.get('Authorization') or request.headers.get('Authentication')
        if not auth:
            if flask_login.current_user.is_authenticated:
                flask.g.token = None
                flask.g.user = flask_login.current_user
                return func(*args, **kwds)
            abort(401, 'A valid Authorization or Authentication header is mandatory')
        
        token_str = auth.removeprefix('Bearer ')
        if not utils.is_app_token(token_str):
            utils.limiter.rate_limit_ip(client_ip)
            abort(401, 'Invalid token format')

        # Fast O(1) lookup using HMAC-SHA256(token) if a server key is configured,
        # otherwise fall back to plain SHA-256 for compatibility.
        # Deterministic HMAC lookup using the application's SECRET_KEY
        key = flask.current_app.config['SECRET_KEY']
        lookup_hash = hmac.new(key.encode(), token_str.encode(), hashlib.sha256).hexdigest()
        token_obj = models.Token.query.filter_by(token_lookup_hash=lookup_hash).first()

        # Verify with bcrypt and handle legacy tokens without lookup hash
        if not token_obj or not token_obj.check_password(token_str):
            utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warn(f'Invalid personal token provided by {client_ip}.')
            abort(403, 'Invalid token')

        # IP restriction check
        if token_obj.ip and not utils.is_ip_in_subnet(client_ip, token_obj.ip):
            flask.current_app.logger.warn(f'Token access from forbidden IP {client_ip} for token-{token_obj.id}.')
            abort(403, 'Token not allowed from this IP')

        # Per-user rate limit
        if utils.limiter.should_rate_limit_user(token_obj.user_email, client_ip):
            abort(429, 'Too many attempts for this token (rate-limit)')

        flask.g.token = token_obj
        flask.g.user = token_obj.user
        flask.current_app.logger.info(f'Valid personal token token-{token_obj.id} for user {token_obj.user_email} provided by {client_ip}.')
        return func(*args, **kwds)
    return decorated_function
