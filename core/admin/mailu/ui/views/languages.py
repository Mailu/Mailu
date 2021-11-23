from mailu.ui import ui, forms, access

import flask

@ui.route('/language/<language>', methods=['POST'])
def set_language(language=None):
    flask.session['language'] = language
    return flask.Response(status=200)

