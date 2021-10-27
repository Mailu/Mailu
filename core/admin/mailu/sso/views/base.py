from werkzeug.utils import redirect
from mailu import models
from mailu.sso import sso, forms
from mailu.ui import access

from flask import current_app as app
import flask
import flask_login

@sso.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LoginForm()
    endpoint = flask.request.args.get('next', 'ui.index')

    form.target.choices = []
    if str(app.config["ADMIN"]).upper() != "FALSE":
        form.target.choices += [("Admin", "Admin")]
    if str(app.config["WEBMAIL"]).upper() != "NONE":
        form.target.choices += [("Webmail", "Webmail")]
    if endpoint == "ui.webmail":
        form.target.choices.reverse()

    if form.validate_on_submit():
        if str(form.target.data) == 'Admin':
            endpoint = 'ui.index'
            destination = app.config['WEB_ADMIN']
        elif str(form.target.data) == 'Webmail':
            endpoint = 'ui.webmail'
            destination = app.config['WEB_WEBMAIL']

        user = models.User.login(form.email.data, form.pw.data)
        if user:
            flask.session.regenerate()
            flask_login.login_user(user)           
            return flask.redirect(destination)
        else:
            flask.flash('Wrong e-mail or password', 'error')
            client_ip = flask.request.headers["X-Real-IP"] if 'X-Real-IP' in flask.request.headers else flask.request.remote_addr
            flask.current_app.logger.warn(f'Login failed for {str(form.email.data)} from {client_ip}.')
    return flask.render_template('login.html', form=form, endpoint=endpoint)
    
@sso.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    flask.session.destroy()
    return flask.redirect(flask.url_for('.login'))