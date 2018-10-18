from mailu import models
from mailu.internal import internal
from flask import current_app as app

import flask


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
        models.db.session.commit()
    return flask.jsonify(None)


@internal.route("/dovecot/sieve/name/<script>/<user_email>")
def dovecot_sieve_name(script, user_email):
    return flask.jsonify(script)


@internal.route("/dovecot/sieve/data/default/<user_email>")
def dovecot_sieve_data(user_email):
    user = models.User.query.get(user_email) or flask.abort(404)
    return flask.jsonify(flask.render_template("default.sieve", user=user))
