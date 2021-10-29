from mailu.sso import sso
import flask

@sso.route('/language/<language>', methods=['POST'])
def set_language(language=None):
    flask.session['language'] = language
    return flask.Response(status=200)
