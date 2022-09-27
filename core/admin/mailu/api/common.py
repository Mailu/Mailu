from .. import models, utils
from . import v1
from flask import request
import flask
import hmac
from functools import wraps
from flask_restx import abort

def fqdn_in_use(*names):
    for name in names:
        for model in models.Domain, models.Alternative, models.Relay:
            if model.query.get(name):
                return model
    return None

""" Decorator for validating api token for authentication """
def api_token_authorization(func):
    @wraps(func)
    def decorated_function(*args, **kwds):
        client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
        if utils.limiter.should_rate_limit_ip(client_ip):
            abort(429, 'Too many attempts from your IP (rate-limit)' )
        if (request.args.get('api_token') == '' or
            request.args.get('api_token') == None):
            abort(401, 'A valid API token is expected as query string parameter')
        if not hmac.compare_digest(request.args.get('api_token'), v1.api_token):
            utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warn(f'Invalid API token provided by {client_ip}.')
            abort(403, 'A valid API token is expected as query string parameter')
        else:
            flask.current_app.logger.info(f'Valid API token provided by {client_ip}.')
        return func(*args, **kwds)
    return decorated_function
