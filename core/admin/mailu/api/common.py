from .. import models, utils
from . import v1
from flask import request
import flask
import hmac
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
            abort(401, 'A valid Bearer token is expected which is provided as request header')
        #Client provides 'Authentication: Bearer <token>'
        if (' ' in request.headers.get('Authorization')
                and not hmac.compare_digest(request.headers.get('Authorization'), 'Bearer ' + v1.api_token)):
            utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warn(f'Invalid API token provided by {client_ip}.')
            abort(403, 'A valid Bearer token is expected which is provided as request header')
        #Client provides 'Authentication: <token>'
        elif (' ' not in request.headers.get('Authorization')
                and not hmac.compare_digest(request.headers.get('Authorization'), v1.api_token)):
            utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warn(f'Invalid API token provided by {client_ip}.')
            abort(403, 'A valid Bearer token is expected which is provided as request header')
        flask.current_app.logger.info(f'Valid API token provided by {client_ip}.')
        return func(*args, **kwds)
    return decorated_function
