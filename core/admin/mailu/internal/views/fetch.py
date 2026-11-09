from mailu import models
from mailu.internal import internal

import flask
import datetime


@internal.route("/fetch")
def fetch_list():
    return flask.jsonify([
        {
            "id": fetch.id,
            "tls": fetch.tls,
            "keep": fetch.keep,
            "scan": fetch.scan,
            "invisible": fetch.invisible,
            "user_email": fetch.user_email,
            "protocol": fetch.protocol,
            "host": fetch.host,
            "port": fetch.port,
            "folders": fetch.folders,
            "username": fetch.username,
            "password": fetch.password
        } for fetch in models.Fetch.query.with_entities(
            models.Fetch.id, models.Fetch.tls, models.Fetch.keep, models.Fetch.scan,
            models.Fetch.invisible, models.Fetch.user_email, models.Fetch.protocol,
            models.Fetch.host, models.Fetch.port, models.Fetch.folders,
            models.Fetch.username, models.Fetch.password,
        ).all()
    ])


@internal.route("/fetch/<fetch_id>", methods=["POST"])
def fetch_done(fetch_id):
    fetch = models.db.session.get(models.Fetch, fetch_id) or flask.abort(404)
    fetch.last_check = datetime.datetime.now()
    fetch.error_message = str(flask.request.get_json())
    fetch.dont_change_updated_at()
    models.db.session.add(fetch)
    models.db.session.commit()
    return ""
