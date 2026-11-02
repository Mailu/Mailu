from mailu import models
from mailu.internal import internal
from flask import current_app as app

import flask
import socket
import os
import sqlalchemy.exc

def _get_user_or_404(user_email):
    """ Look up a user by their (possibly malformed) address, returning a clean
        404 rather than a 500 when the address is not a valid stored e-mail. """
    try:
        user = models.db.session.get(models.User, user_email)
    except sqlalchemy.exc.StatementError:
        user = None
    return user or flask.abort(404)

def _resolve_user_or_404(user_email):
    """ Look up a user or an alias enabled for login, returning (user, via_alias)
        or a clean 404 rather than 500 when address is invalid. """
    try:
        user, via_alias = models.User.resolve_login(user_email)
    except sqlalchemy.exc.StatementError:
        user, via_alias = None, None
    if user is None:
        flask.abort(404)
    return user, via_alias

@internal.route("/dovecot/passdb/<path:user_email>")
def dovecot_passdb_dict(user_email):
    user, via_alias = _resolve_user_or_404(user_email)
    allow_nets = []
    allow_nets.append(app.config["SUBNET"])
    if app.config["SUBNET6"]:
        allow_nets.append(app.config["SUBNET6"])
    result = {
        "password": None,
        "nopassword": "Y",
        "allow_real_nets": ",".join(allow_nets)
    }
    if via_alias:
        result["user"] = user.email
    return flask.jsonify(result)

@internal.route("/dovecot/userdb/")
def dovecot_userdb_dict_list():
    return flask.jsonify([
        user[0] for user in models.User.query.filter(models.User.enabled.is_(True)).with_entities(models.User.email).all()
    ])

@internal.route("/dovecot/userdb/<path:user_email>")
def dovecot_userdb_dict(user_email):
    try:
        quota = models.User.query.filter(models.User.email==user_email).with_entities(models.User.quota_bytes).one_or_none() or flask.abort(404)
    except sqlalchemy.exc.StatementError as exc:
        flask.abort(404)
    return flask.jsonify({
        "quota_storage_size": str(quota[0]),
    })


@internal.route("/dovecot/quota/<ns>/<path:user_email>", methods=["POST"])
def dovecot_quota(ns, user_email):
    user = _get_user_or_404(user_email)
    if ns == "storage":
        user.quota_bytes_used = flask.request.get_json()
        user.dont_change_updated_at()
        models.db.session.commit()
    return flask.jsonify(None)


@internal.route("/dovecot/sieve/name/<script>/<path:user_email>")
def dovecot_sieve_name(script, user_email):
    return flask.jsonify(script)


@internal.route("/dovecot/sieve/data/default/<path:user_email>")
def dovecot_sieve_data(user_email):
    user = _get_user_or_404(user_email)
    return flask.jsonify(flask.render_template("default.sieve", user=user))
