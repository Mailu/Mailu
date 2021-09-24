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

    if str(app.config['WEBMAIL']).upper != 'NONE' and str(app.config['ADMIN']).upper != 'NONE' and endpoint != 'ui.webmail':
        form.target.choices = [('Configuration page', 'Configuration page'), ('Webmail', 'Webmail')]
    elif str(app.config['WEBMAIL']).upper != 'NONE' and str(app.config['ADMIN']).upper != 'NONE' and endpoint == 'ui.webmail':
        form.target.choices = [('Webmail', 'Webmail'), ('Configuration page', 'Configuration page')]
    elif str(app.config['WEBMAIL']).upper != 'NONE' and str(app.config['ADMIN']).upper == 'NONE':
        form.target.choices = [('Webmail', 'Webmail')]
    elif str(app.config['WEBMAIL']).upper == 'NONE' and str(app.config['ADMIN']).upper != 'NONE':
        form.target.choices = [('Configuration page', 'Configuration page')]

    if form.validate_on_submit():
        if form.target.data == 'Configuration page':
            endpoint = 'ui.index'
        elif form.target.data == 'webmail':
            endpoint = 'ui.webmail'

        user = models.User.login(form.email.data, form.pw.data)
        if user:
            flask.session.regenerate()
            flask_login.login_user(user)           
            return flask.redirect(flask.url_for(endpoint))
        else:
            flask.flash('Wrong e-mail or password', 'error')
    return flask.render_template('login.html', form=form, endpoint=endpoint)
    