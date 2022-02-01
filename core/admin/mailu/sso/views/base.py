from werkzeug.utils import redirect
from mailu import models, utils
from mailu.sso import sso, forms
from mailu.ui import access

from flask import current_app as app
import flask
import flask_login
import secrets

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

@sso.route('/proxy', methods=['GET'])
def proxy():
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    username=flask.request.headers.get('X-Auth-Email') or ""
    secret=flask.request.headers.get('X-Auth-Proxy-Secret') or ""
    target=flask.request.headers.get('X-Auth-Proxy-Target') or ""
    tokens=username.split("@")
    domain_name=""
    if (len(tokens)==2):
        domain_name=tokens[1]
        localpart=tokens[0]
    domain = models.Domain.query.get(domain_name)
    if not domain or domain=="None":
        return flask.redirect(flask.url_for('.login'))

    form = forms.LoginForm()
    form.submitAdmin.label.text = form.submitAdmin.label.text + ' Admin'
    form.submitWebmail.label.text = form.submitWebmail.label.text + ' Webmail'

    fields = []
    if str(app.config["WEBMAIL"]).upper() != "NONE":
        fields.append(form.submitWebmail)
    if str(app.config["ADMIN"]).upper() != "FALSE":
        fields.append(form.submitAdmin)
    fields = [fields]

    if str(target).upper()=="ADMIN":
        destination = "0; url="+ app.config['WEB_ADMIN']
    else:
        destination = "0; url="+ app.config['WEB_WEBMAIL']

    payload_dict = {
        'Refresh': destination
    }

    device_cookie, device_cookie_username = utils.limiter.parse_device_cookie(flask.request.cookies.get('rate_limit'))
    if username != device_cookie_username and utils.limiter.should_rate_limit_ip(client_ip):
        flask.flash('Too many attempts from your IP (rate-limit)', 'error')
        return flask.render_template('login.html', form=form, fields=fields)
    if utils.limiter.should_rate_limit_user(username, client_ip, device_cookie, device_cookie_username):
        flask.flash('Too many attempts for this user (rate-limit)', 'error')
        return flask.render_template('login.html', form=form, fields=fields)

    if username and len(secret)>16 and app.config.get('PROXY_SECRET', "") == secret:
        user = models.User.get(flask.request.headers.get('X-Auth-Email'))
        if user:
            flask.session.regenerate()
            flask_login.login_user(user)
            return flask.render_template('login.html', form=form, fields=fields), payload_dict
        else:
            if app.config['PROXY_CREATE']:
                if domain.has_email(localpart):
                    flask.flash('Email is already used', 'error')
                    return flask.redirect(flask.url_for('.login'))
                else:
                    #Create a user
                    user = models.User(
                        localpart=localpart,
                        domain=domain,
                        global_admin=False
                    )
                    user.set_password(secrets.token_urlsafe(32))
                    models.db.session.add(user)
                    models.db.session.commit()
                    user.send_welcome()
                    flask.session.regenerate()
                    flask_login.login_user(user)
                    flask.current_app.logger.info(f'Login succeeded by proxy created user: {username} from {client_ip}.')
                    return flask.render_template('login.html', form=form, fields=fields), payload_dict
            else:
                utils.limiter.rate_limit_ip(client_ip)
                flask.current_app.logger.warn(f'Login failed by proxy for {username} from {client_ip}.')
    return flask.redirect(flask.url_for('.login'))

@sso.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    flask.session.destroy()
    return flask.redirect(flask.url_for('.login'))

