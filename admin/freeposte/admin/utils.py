from freeposte.admin import models
from flask.ext import login as flask_login

import flask


def get_domain_admin(domain_name):
    domain = models.Domain.query.filter_by(name=domain_name).first()
    if not domain:
        flask.abort(404)
    if not domain in flask_login.current_user.get_managed_domains():
        flask.abort(403)
    return domain


def require_global_admin():
    if not flask_login.current_user.global_admin:
        flask.abort(403)


def get_user(user_email, admin=False):
    if user_email is None:
        user = flask_login.current_user
    else:
        user = models.User.get_by_email(user_email)
    if not user:
        flask.abort(404)
    if not user.domain in flask_login.current_user.get_managed_domains():
        if admin:
            flask.abort(403)
        elif not user == flask_login.current_user:
            flask.abort(403)
    return user


def get_alias(alias):
    alias = models.Alias.get_by_email(alias)
    if not alias:
        flask.abort(404)
    if not alias.domain in flask_login.current_user.get_managed_domains():
        return 403
    return alias


def get_fetch(fetch_id):
    fetch = models.Fetch.query.filter_by(id=fetch_id).first()
    if not fetch:
        flask.abort(404)
    if not fetch.user.domain in flask_login.current_user.get_managed_domains():
        if not fetch.user == flask_login.current_user:
            flask.abort(403)
    return fetch
