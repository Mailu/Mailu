from mailu import models
from mailu.internal import internal
from flask import current_app as app

import flask
import sqlalchemy.exc

db = models.db


@internal.route("/dovecot/passdb/<path:user_email>")
def dovecot_passdb_dict(user_email):
    user = db.get_or_404(models.User, user_email)
    allow_nets = []
    allow_nets.append(app.config["SUBNET"])
    if app.config["SUBNET6"]:
        allow_nets.append(app.config["SUBNET6"])
    return flask.jsonify({
        "password": None,
        "nopassword": "Y",
        "allow_real_nets": ",".join(allow_nets)
    })


@internal.route("/dovecot/userdb/")
def dovecot_userdb_dict_list():
    return flask.jsonify([
        user[0] for user in db.session.execute(db.select(models.User).filter_by(enabled=True).with_only_columns(models.User.email)).all()
    ])


@internal.route("/dovecot/userdb/<path:user_email>")
def dovecot_userdb_dict(user_email):
    try:
        quota = db.one_or_404(db.select(models.User).filter_by(email=user_email).with_only_columns(models.User.quota_bytes))
    except sqlalchemy.exc.StatementError as exc:
        flask.abort(404)
    return flask.jsonify({
        "quota_rule": f"*:bytes={quota[0]}"
    })


@internal.route("/dovecot/quota/<ns>/<path:user_email>", methods=["POST"])
def dovecot_quota(ns, user_email):
    user = db.get_or_404(models.User, user_email)
    if ns == "storage":
        user.quota_bytes_used = flask.request.get_json()
        user.dont_change_updated_at()
        db.session.commit()
    return flask.jsonify(None)


@internal.route("/dovecot/sieve/name/<script>/<path:user_email>")
def dovecot_sieve_name(script, user_email):
    return flask.jsonify(script)


@internal.route("/dovecot/sieve/data/default/<path:user_email>")
def dovecot_sieve_data(user_email):
    user = db.get_or_404(models.User, user_email)
    return flask.jsonify(flask.render_template("default.sieve", user=user))
