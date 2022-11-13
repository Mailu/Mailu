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
            "user_email": fetch.user_email,
            "protocol": fetch.protocol,
            "host": fetch.host,
            "port": fetch.port,
            "folders": fetch.folders,
            "username": fetch.username,
            "password": fetch.password
        } for fetch in models.Fetch.query.all()
    ])


@internal.route("/fetch/<fetch_id>", methods=["POST"])
def fetch_done(fetch_id):
    fetch = models.Fetch.query.get(fetch_id) or flask.abort(404)
    fetch.last_check = datetime.datetime.now()
    fetch.error_message = str(flask.request.get_json())
    fetch.dont_change_updated_at()
    models.db.session.add(fetch)
    models.db.session.commit()
    return ""
