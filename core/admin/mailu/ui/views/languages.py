from mailu.ui import ui, forms, access

import flask


@ui.route('/language/<language>', methods=['GET'])
def set_language(language=None):
    flask.session['language'] = language
    return flask.redirect(flask.url_for('.user_settings'))
