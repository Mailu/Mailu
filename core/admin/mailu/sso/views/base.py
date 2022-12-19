from werkzeug.utils import redirect
from mailu import models, utils
from mailu.sso import sso, forms
from mailu.ui import access

from flask import current_app as app
import flask
import flask_login
import secrets
import ipaddress

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
            flask.current_app.logger.info(f'Login succeeded for {username} from {client_ip} pwned={form.pwned.data}.')
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
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
    flask.session.destroy()
    return flask.redirect(flask.url_for('.login'))


@sso.route('/proxy', methods=['GET'])
@sso.route('/proxy/<target>', methods=['GET'])
def proxy(target='webmail'):
    ip = ipaddress.ip_address(flask.request.remote_addr)
    if not any(ip in cidr for cidr in app.config['PROXY_AUTH_WHITELIST']):
        return flask.abort(500, '%s is not on PROXY_AUTH_WHITELIST' % flask.request.remote_addr)

    email = flask.request.headers.get(app.config['PROXY_AUTH_HEADER'])
    if not email:
        return flask.abort(500, 'No %s header' % app.config['PROXY_AUTH_HEADER'])

    user = models.User.get(email)
    if user:
        flask.session.regenerate()
        flask_login.login_user(user)
        return flask.redirect(app.config['WEB_ADMIN'] if target=='admin' else app.config['WEB_WEBMAIL'])

    if not app.config['PROXY_AUTH_CREATE']:
        return flask.abort(500, 'You don\'t exist. Go away! (%s)' % email)

    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    try:
        localpart, desireddomain = email.rsplit('@')
    except Exception as e:
        flask.current_app.logger.error('Error creating a new user via proxy for %s from %s: %s' % (email, client_ip, str(e)), e)
        return flask.abort(500, 'You don\'t exist. Go away! (%s)' % email)
    domain = models.Domain.query.get(desireddomain) or flask.abort(500, 'You don\'t exist. Go away! (domain=%s)' % desireddomain)
    if not domain.max_users == -1 and len(domain.users) >= domain.max_users:
        flask.current_app.logger.warning('Too many users for domain %s' % domain)
        return flask.abort(500, 'Too many users in (domain=%s)' % domain)
    user = models.User(localpart=localpart, domain=domain)
    user.set_password(secrets.token_urlsafe())
    models.db.session.add(user)
    models.db.session.commit()
    user.send_welcome()
    flask.current_app.logger.info(f'Login succeeded by proxy created user: {user} from {client_ip} through {flask.request.remote_addr}.')
    return flask.redirect(app.config['WEB_ADMIN'] if target=='admin' else app.config['WEB_WEBMAIL'])
