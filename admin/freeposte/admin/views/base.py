from freeposte.admin import app, db, models, forms
from flask.ext import login as flask_login

import os
import flask


@app.route('/', methods=["GET"])
@flask_login.login_required
def index():
    return flask.redirect(flask.url_for('.user_settings'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LoginForm()
    if form.validate_on_submit():
        user = models.User.login(form.email.data, form.pw.data)
        if user:
            flask_login.login_user(user)
            return flask.redirect(flask.url_for('.index'))
        else:
            flask.flash('Wrong e-mail address or password', 'error')
    return flask.render_template('login.html', form=form)


@app.route('/logout', methods=['GET'])
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return flask.redirect(flask.url_for('.index'))
