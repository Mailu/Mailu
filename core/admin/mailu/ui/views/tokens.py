from mailu import models, utils
from mailu.ui import ui, forms, access

from passlib import pwd

import flask
import flask_login
import wtforms_components


@ui.route('/token/list', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/token/list/<path:user_email>', methods=['GET'])
@access.owner(models.User, 'user_email')
def token_list(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    return flask.render_template('token/list.html', user=user)


@ui.route('/token/create', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/token/create/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def token_create(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    form = forms.TokenForm()
    wtforms_components.read_only(form.displayed_password)
    if not form.raw_password.data:
        form.raw_password.data = pwd.genword(entropy=128, length=32, charset="hex")
    form.displayed_password.data = form.raw_password.data
    utils.formatCSVField(form.ip)
    if form.validate_on_submit():
        token = models.Token(user=user)
        token.set_password(form.raw_password.data)
        form.populate_obj(token)
        if form.ip.data:
            token.ip = form.ip.data.replace(' ','').split(',')
        else:
            del token.ip
        models.db.session.add(token)
        models.db.session.commit()
        flask.flash('Authentication token created')
        return flask.redirect(
            flask.url_for('.token_list', user_email=user.email))
    return flask.render_template('token/create.html', form=form)


@ui.route('/token/delete/<token_id>', methods=['GET', 'POST'])
@access.confirmation_required("delete an authentication token")
@access.owner(models.Token, 'token_id')
def token_delete(token_id):
    token = models.Token.query.get(token_id) or flask.abort(404)
    user = token.user
    models.db.session.delete(token)
    models.db.session.commit()
    flask.flash('Authentication token deleted')
    return flask.redirect(
        flask.url_for('.token_list', user_email=user.email))
