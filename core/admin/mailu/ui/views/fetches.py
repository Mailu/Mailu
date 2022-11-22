from mailu import models, utils
from mailu.ui import ui, forms, access
from flask import current_app as app

import flask
import flask_login
import wtforms


@ui.route('/fetch/list', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/fetch/list/<path:user_email>', methods=['GET'])
@access.owner(models.User, 'user_email')
def fetch_list(user_email):
    if not app.config['FETCHMAIL_ENABLED']:
        flask.abort(404)
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    return flask.render_template('fetch/list.html', user=user)


@ui.route('/fetch/create', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/fetch/create/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def fetch_create(user_email):
    if not app.config['FETCHMAIL_ENABLED']:
        flask.abort(404)
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    form = forms.FetchForm()
    form.password.validators = [wtforms.validators.DataRequired()]
    utils.formatCSVField(form.folders)
    if form.validate_on_submit():
        fetch = models.Fetch(user=user)
        form.populate_obj(fetch)
        if form.folders.data:
            fetch.folders = form.folders.data.replace(' ','').split(',')
        models.db.session.add(fetch)
        models.db.session.commit()
        flask.flash('Fetch configuration created')
        return flask.redirect(
            flask.url_for('.fetch_list', user_email=user.email))
    return flask.render_template('fetch/create.html', form=form)


@ui.route('/fetch/edit/<fetch_id>', methods=['GET', 'POST'])
@access.owner(models.Fetch, 'fetch_id')
def fetch_edit(fetch_id):
    if not app.config['FETCHMAIL_ENABLED']:
        flask.abort(404)
    fetch = models.Fetch.query.get(fetch_id) or flask.abort(404)
    form = forms.FetchForm(obj=fetch)
    utils.formatCSVField(form.folders)
    if form.validate_on_submit():
        if not form.password.data:
            form.password.data = fetch.password
        form.populate_obj(fetch)
        if form.folders.data:
            fetch.folders = form.folders.data.replace(' ','').split(',')
        models.db.session.commit()
        flask.flash('Fetch configuration updated')
        return flask.redirect(
            flask.url_for('.fetch_list', user_email=fetch.user.email))
    return flask.render_template('fetch/edit.html',
        form=form, fetch=fetch)


@ui.route('/fetch/delete/<fetch_id>', methods=['GET', 'POST'])
@access.confirmation_required("delete a fetched account")
@access.owner(models.Fetch, 'fetch_id')
def fetch_delete(fetch_id):
    if not app.config['FETCHMAIL_ENABLED']:
        flask.abort(404)
    fetch = models.Fetch.query.get(fetch_id) or flask.abort(404)
    user = fetch.user
    models.db.session.delete(fetch)
    models.db.session.commit()
    flask.flash('Fetch configuration delete')
    return flask.redirect(
        flask.url_for('.fetch_list', user_email=user.email))
