from mailu import db, models
from mailu.internal import internal, nginx

import flask


@internal.route("/nginx")
def nginx_authentication():
    headers = nginx.handle_authentication(flask.request.headers)
    response = flask.Response()
    for key, value in headers.items():
        response.headers[key] = str(value)
    return response

