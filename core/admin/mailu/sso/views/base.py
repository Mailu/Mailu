from werkzeug.utils import redirect
from mailu import models, utils
from mailu.sso import sso, forms
from mailu.ui import access

from flask import current_app as app
from flask import session
import flask
import flask_login

@sso.route('/login', methods=['GET', 'POST'])
def login():
    device_cookie, device_cookie_username = utils.limiter.parse_device_cookie(flask.request.cookies.get('rate_limit'))

    if 'code' in flask.request.args:
        username, token_response = utils.oic_client.exchange_code(flask.request.query_string.decode())
        if username is not None:
            user = models.User.get(username)
            if user is None: # It is possible that the user never logged into Mailu with his OpenID account
                user = models.User.create(username) # Create user with no password to enable OpenID and Keycloak-only authentication

            client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
            keycloak_token = { # Minimize session data
                "access_token": token_response['access_token'],
                "refresh_token": token_response['refresh_token']
            }
            app.logger.warn('SESSION 1: %s', session)
            flask.session["keycloak_token"] = keycloak_token
            app.logger.warn('SESSION 2: %s', session)
            flask.session.regenerate()
            app.logger.warn('SESSION 3: %s', session)
            flask_login.login_user(user)
            app.logger.warn('SESSION 4: %s', session)
            response = flask.redirect(app.config['WEB_ADMIN'])
            response.set_cookie('rate_limit', utils.limiter.device_cookie(username), max_age=31536000, path=flask.url_for('sso.login'), secure=app.config['SESSION_COOKIE_SECURE'], httponly=True)
            flask.current_app.logger.info(f'Login succeeded for {username} from {client_ip}.')
            app.logger.warn('SESSION 5: %s', session)
            return response
        else:
            utils.limiter.rate_limit_user(username, client_ip, device_cookie, device_cookie_username) if models.User.get(username) else utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warn(f'Login failed for {username} from {client_ip}.')
            flask.flash('Wrong e-mail or password', 'error')
            
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
    
    return flask.render_template('login.html', form=form, fields=fields, openId=app.config['OIDC_ENABLED'], openIdEndpoint=utils.oic_client.get_redirect_url())

@sso.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.current_user.logout()
    flask_login.logout_user()
    flask.session.destroy()
    return flask.redirect(flask.url_for('.login'))

@sso.route('/auth', methods=['GET'])
def auth():
    form = forms.LoginForm()
    form.submitAdmin.label.text = form.submitAdmin.label.text + ' Admin'
    form.submitWebmail.label.text = form.submitWebmail.label.text + ' Webmail'
    fields = []
    if str(app.config["WEBMAIL"]).upper() != "NONE":
        fields.append(form.submitWebmail)
    if str(app.config["ADMIN"]).upper() != "FALSE":
        fields.append(form.submitAdmin)
    fields = [fields]
    device_cookie, device_cookie_username = utils.limiter.parse_device_cookie(flask.request.cookies.get('rate_limit'))
    username, token_response = utils.oic_client.exchange_code(flask.request.query_string.decode())
    if username is not None:
        user = models.User.get(username)
        if user is None: # It is possible that the user never logged into Mailu with his OpenID account
            user = models.User.create(username) # Create user with no password to enable OpenID and Keycloak-only authentication

        client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
        keycloak_token = { # Minimize session data
            "access_token": token_response['access_token'],
            "refresh_token": token_response['refresh_token']
        }
        flask.session["keycloak_token"] = keycloak_token
        flask.session.regenerate()
        flask_login.login_user(user)
        response = flask.redirect(app.config['WEB_ADMIN'])
        response.set_cookie('rate_limit', utils.limiter.device_cookie(username), max_age=31536000, path=flask.url_for('sso.auth'), secure=app.config['SESSION_COOKIE_SECURE'], httponly=True)
        flask.current_app.logger.info(f'Login succeeded for {username} from {client_ip}.')
        return response
    else:
        utils.limiter.rate_limit_user(username, client_ip, device_cookie, device_cookie_username) if models.User.get(username) else utils.limiter.rate_limit_ip(client_ip)
        flask.current_app.logger.warn(f'Login failed for {username} from {client_ip}.')
        flask.flash('Wrong e-mail or password', 'error')
    return flask.render_template('login.html', form=form, fields=fields, openId=app.config['OIDC_ENABLED'], openIdEndpoint=utils.oic_client.get_redirect_url())

