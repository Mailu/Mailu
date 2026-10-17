import flask


internal = flask.Blueprint('internal', __name__, template_folder='templates')


from mailu.internal.views import *


@internal.route('/sso/start')
def signin_start():
    # This endpoint is reachable only through nginx's internal handoff.
    from mailu import signin
    destination = flask.request.headers.get('X-Mailu-Return-To')
    if not signin.remember(destination):
        flask.abort(400)
    return flask.redirect(flask.url_for('sso.login'))
