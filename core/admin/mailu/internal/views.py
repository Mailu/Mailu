from mailu import db, models, app, limiter
from mailu.internal import internal, nginx
from sqlalchemy import or_

import flask
import flask_login
import base64
import urllib


@internal.route("/auth/email")
@limiter.limit(
    app.config["AUTH_RATELIMIT"],
    lambda: flask.request.headers["Client-Ip"]
)
def nginx_authentication():
    """ Main authentication endpoint for Nginx email server
    """
    headers = nginx.handle_authentication(flask.request.headers)
    response = flask.Response()
    for key, value in headers.items():
        response.headers[key] = str(value)
    return response


@internal.route("/auth/admin")
def admin_authentication():
    """ Fails if the user is not an authenticated admin.
    """
    if (not flask_login.current_user.is_anonymous
        and flask_login.current_user.global_admin
        and flask_login.current_user.enabled):
        return ""
    return flask.abort(403)


@internal.route("/auth/basic")
def basic_authentication():
    """ Tries to authenticate using the Authorization header.
    """
    authorization = flask.request.headers.get("Authorization")
    if authorization and authorization.startswith("Basic "):
        encoded = authorization.replace("Basic ", "")
        user_email, password = base64.b64decode(encoded).split(b":")
        user = models.User.query.get(user_email.decode("utf8"))
        if user and user.enabled and user.check_password(password.decode("utf8")):
            response = flask.Response()
            response.headers["X-User"] = user.email
            return response
    response = flask.Response(status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Login Required"'
    return response


@internal.route("/postfix/domain/<domain_name>")
def postfix_mailbox_domain(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.jsonify(domain.name)


@internal.route("/postfix/mailbox/<email>")
def postfix_mailbox_map(email):
    user = models.User.query.get(email) or flask.abort(404)
    return flask.jsonify(user.email)


@internal.route("/postfix/alias/<alias>")
def postfix_alias_map(alias):
    localpart, domain = alias.split('@', 1) if '@' in alias else (None, alias)
    alternative = models.Alternative.query.get(domain)
    if alternative:
        domain = alternative.domain_name
    email = '{}@{}'.format(localpart, domain)
    if localpart is None:
        return flask.jsonify(domain)
    else:
        alias_obj = models.Alias.resolve(localpart, domain)
        if alias_obj:
            return flask.jsonify(alias_obj.destination)
        user_obj = models.User.query.get(email)
        if user_obj:
            return flask.jsonify(user_obj.destination)
        return flask.abort(404)


@internal.route("/postfix/spoofed/<email>")
def postfix_spoofed(email):
    return flask.abort(404)


@internal.route("/postfix/transport/<email>")
def postfix_transport(email):
    return flask.abort(404)


@internal.route("/dovecot/passdb/<user_email>")
def dovecot_passdb_dict(user_email):
    user = models.User.query.get(user_email) or flask.abort(404)
    return flask.jsonify({
        "password": user.password,
    })


@internal.route("/dovecot/userdb/<user_email>")
def dovecot_userdb_dict(user_email):
    user = models.User.query.get(user_email) or flask.abort(404)
    return flask.jsonify({
        "quota_rule": "*:bytes={}".format(user.quota_bytes)
    })


@internal.route("/dovecot/quota/<ns>/<user_email>", methods=["POST"])
def dovecot_quota(ns, user_email):
    user = models.User.query.get(user_email) or flask.abort(404)
    if ns == "storage":
        user.quota_bytes_used = flask.request.get_json()
        db.session.commit()
    return flask.jsonify(None)


@internal.route("/dovecot/sieve/name/<script>/<user_email>")
def dovecot_sieve(script, user_email):
    user = models.User.query.get(user_email) or flask.abort(404)
    if script == "default":
        return flask.jsonify(flask.render_template("default.sieve"))
    else:
        flask.abort(404)

