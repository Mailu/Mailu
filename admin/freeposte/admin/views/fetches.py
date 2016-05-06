from freeposte.admin import app, db, models, forms, utils
from flask.ext import login as flask_login

import os
import flask
import wtforms_components


@app.route('/fetch/list', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/fetch/list/<user_email>', methods=['GET'])
@flask_login.login_required
def fetch_list(user_email):
    user = utils.get_user(user_email)
    return flask.render_template('fetch/list.html', user=user)


@app.route('/fetch/create', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/fetch/create/<user_email>', methods=['GET', 'POST'])
@flask_login.login_required
def fetch_create(user_email):
    user = utils.get_user(user_email)
    form = forms.FetchForm()
    if form.validate_on_submit():
        fetch = models.Fetch(user=user)
        form.populate_obj(fetch)
        db.session.add(fetch)
        db.session.commit()
        flask.flash('Fetch configuration created')
        return flask.redirect(
            flask.url_for('.fetch_list', user_email=user.email))
    return flask.render_template('fetch/create.html', form=form)


@app.route('/fetch/edit/<fetch_id>', methods=['GET', 'POST'])
@flask_login.login_required
def fetch_edit(fetch_id):
    fetch = utils.get_fetch(fetch_id)
    form = forms.FetchForm(obj=fetch)
    if form.validate_on_submit():
        form.populate_obj(fetch)
        db.session.commit()
        flask.flash('Fetch configuration updated')
        return flask.redirect(
            flask.url_for('.fetch_list', user_email=fetch.user.email))
    return flask.render_template('fetch/edit.html',
        form=form, fetch=fetch)


@app.route('/fetch/delete/<fetch_id>', methods=['GET'])
@flask_login.login_required
def fetch_delete(fetch_id):
    fetch = utils.get_fetch(fetch_id)
    db.session.delete(fetch)
    db.session.commit()
    flask.flash('Fetch configuration delete')
    return flask.redirect(
        flask.url_for('.fetch_list', user_email=fetch.user.email))
