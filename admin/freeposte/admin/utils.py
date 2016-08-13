from freeposte.admin import models

import flask
import flask_login


def get_domain_admin(domain_name):
    domain = models.Domain.query.get(domain_name)
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
        user_email = flask_login.current_user.email
    user = models.User.query.get(user_email)
    if not user:
        flask.abort(404)
    if not user.domain in flask_login.current_user.get_managed_domains():
        if admin:
            flask.abort(403)
        elif not user.email == flask_login.current_user.email:
            flask.abort(403)
    return user


def get_alias(alias):
    alias = models.Alias.query.get(alias)
    if not alias:
        flask.abort(404)
    if not alias.domain in flask_login.current_user.get_managed_domains():
        return 403
    return alias


def get_fetch(fetch_id):
    fetch = models.Fetch.query.get(fetch_id)
    if not fetch:
        flask.abort(404)
    if not fetch.user.domain in flask_login.current_user.get_managed_domains():
        if not fetch.user.email == flask_login.current_user.email:
            flask.abort(403)
    return fetch
