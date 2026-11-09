from mailu import models
from mailu.internal import internal
from flask import current_app as app
from socrate.system import mailbox_shard

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


@internal.route("/dovecot/passdb/<path:user_email>")
def dovecot_passdb_dict(user_email):
    try:
        found = models.User.query.with_entities(models.User.email).filter_by(_email=user_email).first()
    except sqlalchemy.exc.StatementError:
        found = None
    if found is None:
        flask.abort(404)
    allow_nets = []
    allow_nets.append(app.config["SUBNET"])
    if app.config["SUBNET6"]:
        allow_nets.append(app.config["SUBNET6"])
    return flask.jsonify({
        # Dovecot's nopassword passdb requires an empty password value. JSON
        # null is decoded as an absent field and does not authenticate the
        # trusted proxy connection on current Dovecot releases.
        "password": "",
        "nopassword": "Y",
        "allow_real_nets": ",".join(allow_nets)
    })

@internal.route("/dovecot/userdb/")
def dovecot_userdb_dict_list():
    if flask.request.args.get("with_uid") == "1":
        return flask.jsonify([
            _userdb_fields(user)
            for user in models.User.query.with_entities(
                models.User.email, models.User.domain_name, models.User.localpart,
                models.User.quota_bytes, models.User.dovecot_uid,
            ).order_by(models.User.email).all()
        ])
    return flask.jsonify([
        user[0] for user in models.User.query.filter(models.User.enabled.is_(True)).with_entities(models.User.email).all()
    ])

@internal.route("/dovecot/userdb/<path:user_email>")
def dovecot_userdb_dict(user_email):
    try:
        user = models.User.query.with_entities(
            models.User.email, models.User.domain_name, models.User.localpart,
            models.User.quota_bytes, models.User.dovecot_uid,
        ).filter_by(_email=user_email).first()
    except sqlalchemy.exc.StatementError:
        user = None
    if user is None:
        flask.abort(404)
    if user.dovecot_uid is None:
        app.logger.error("Dovecot identity has not been allocated for %s", user_email)
        flask.abort(503)
    return flask.jsonify(_userdb_fields(user))


def _userdb_fields(user):
    # The /./ separator tells Dovecot to chroot at /mail and use the remainder
    # as the user's home inside that jail.
    mailbox_home = f"/mail/./{user.domain_name}/{mailbox_shard(user.email)}/{user.localpart}"
    return {
        "email": user.email,
        "quota_storage_size": str(user.quota_bytes),
        "uid": user.dovecot_uid,
        "gid": user.dovecot_uid,
        "home": mailbox_home,
    }


@internal.route("/dovecot/quota/<ns>/<path:user_email>", methods=["POST"])
def dovecot_quota(ns, user_email):
    try:
        user = models.User.query.with_entities(models.User.email).filter_by(_email=user_email).first()
    except sqlalchemy.exc.StatementError:
        user = None
    if user is None:
        flask.abort(404)
    if ns == "storage":
        value = flask.request.get_json(silent=True)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            flask.abort(400)
        models.db.session.execute(
            models.User.__table__.update()
            .where(models.User._email == user_email)
            # Keep both on-update columns unchanged. Their Python defaults
            # expect full User insert parameters, which this narrow update
            # intentionally does not load or provide.
            .values(
                quota_bytes_used=value,
                updated_at=models.User.__table__.c.updated_at,
                email=models.User.__table__.c.email,
            )
        )
        models.db.session.commit()
    return flask.jsonify(None)


@internal.route("/dovecot/sieve/name/<script>/<path:user_email>")
def dovecot_sieve_name(script, user_email):
    return flask.jsonify(script)


@internal.route("/dovecot/sieve/data/default/<path:user_email>")
def dovecot_sieve_data(user_email):
    user = _get_user_or_404(user_email)
    return flask.jsonify(flask.render_template("default.sieve", user=user))
