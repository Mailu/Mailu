from mailu.sso import sso
import flask

@sso.route('/language/<language>', methods=['GET','POST'])
def set_language(language=None):
    if language:
        flask.session['language'] = language
    return flask.Response(status=200)
