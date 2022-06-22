from werkzeug.utils import redirect
from mailu import models, utils
from mailu.sso import sso, forms, oauth
from mailu.ui import access

from flask import current_app as app
import flask
import flask_login
import requests


@sso.route('/login_oidc')
def login_oidc():
    redirect_uri = flask.url_for('sso.auth', _external=True, _scheme='https')
    return oauth.keycloak.authorize_redirect(redirect_uri)


@sso.route('/auth')
def auth():
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    tokenResponse = oauth.keycloak.authorize_access_token()

    app.logger.info(str(tokenResponse))
    idToken = oauth.keycloak.parse_id_token(tokenResponse, nonce=None)

    if idToken:
        flask.session['oidc_user'] = idToken
        flask.session['oidc_tokenResponse'] = tokenResponse
        if str(idToken['email_verified']).upper() == "TRUE":
            user = models.User.login_oidc(idToken['email'])  # Should probably also allow to get emails from attributes or similar
            if user:
                flask.session.regenerate()
                flask_login.login_user(user)
                if str(app.config["ADMIN"]).upper() != "FALSE":
                    response = flask.redirect(app.config['WEB_ADMIN'])
                else:
                    response = flask.redirect(app.config['WEB_WEBMAIL'])
                response.set_cookie('rate_limit', utils.limiter.device_cookie(idToken['email']), max_age=31536000, path=flask.url_for('sso.login'), secure=app.config['SESSION_COOKIE_SECURE'], httponly=True)
                flask.current_app.logger.info(f'OIDC login succeeded for {idToken["email"]} from {client_ip}.')
                return response
    return 'Unauthorized'


@sso.route('/login', methods=['GET', 'POST'])
def login():
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    form = forms.LoginForm()
    form.submitAdmin.label.text = form.submitAdmin.label.text + ' Admin'
    form.submitWebmail.label.text = form.submitWebmail.label.text + ' Webmail'

    fields = []
    if str(app.config["WEBMAIL"]).upper() != "NONE":
        fields.append(form.submitWebmail)
    if str(app.config["ADMIN"]).upper() != "FALSE":
        fields.append(form.submitAdmin)
    fields = [fields]

    if form.validate_on_submit():
        if form.submitAdmin.data:
            destination = app.config['WEB_ADMIN']
        elif form.submitWebmail.data:
            destination = app.config['WEB_WEBMAIL']
        device_cookie, device_cookie_username = utils.limiter.parse_device_cookie(flask.request.cookies.get('rate_limit'))
        username = form.email.data
        if username != device_cookie_username and utils.limiter.should_rate_limit_ip(client_ip):
            flask.flash('Too many attempts from your IP (rate-limit)', 'error')
            return flask.render_template('login.html', form=form, fields=fields)
        if utils.limiter.should_rate_limit_user(username, client_ip, device_cookie, device_cookie_username):
            flask.flash('Too many attempts for this user (rate-limit)', 'error')
            return flask.render_template('login.html', form=form, fields=fields)
        user = models.User.login(username, form.pw.data)
        if user:
            flask.session.regenerate()
            flask_login.login_user(user)
            response = flask.redirect(destination)
            response.set_cookie('rate_limit', utils.limiter.device_cookie(username), max_age=31536000, path=flask.url_for('sso.login'), secure=app.config['SESSION_COOKIE_SECURE'], httponly=True)
            flask.current_app.logger.info(f'Login succeeded for {username} from {client_ip}.')
            return response
        else:
            utils.limiter.rate_limit_user(username, client_ip, device_cookie, device_cookie_username) if models.User.get(username) else utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warn(f'Login failed for {username} from {client_ip}.')
            flask.flash('Wrong e-mail or password', 'error')
    return flask.render_template('login.html', form=form, fields=fields)

@sso.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    tokenResponse = flask.session.get('oidc_tokenResponse')
    if tokenResponse is not None:
        refreshToken = tokenResponse['refresh_token']
        endSessionEndpoint = f'{app.config["OIDC_ISSUER"]}/protocol/openid-connect/logout'

        # Logs you out of the SSO
        requests.post(endSessionEndpoint, data={
            'client_id': app.config['OIDC_CLIENTID'],
            'client_secret': app.config['OIDC_CLIENTSECRET'],
            'refresh_token': refreshToken,
            })
    flask.session.destroy()
    return flask.redirect(flask.url_for('.login'))

