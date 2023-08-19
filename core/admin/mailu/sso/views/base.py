from werkzeug.utils import redirect
from mailu import models, utils
from mailu.sso import sso, forms
from mailu.ui import access

from flask import current_app as app
from flask_babel import lazy_gettext as _
import flask
import flask_login
import secrets
import ipaddress
from urllib.parse import urlparse, urljoin
from werkzeug.urls import url_unquote

@sso.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.headers.get(app.config['PROXY_AUTH_HEADER']) and not 'noproxyauth' in flask.request.url:
        return _proxy()

    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    client_port = flask.request.headers.get('X-Real-Port', None)
    form = forms.LoginForm()

    fields = []

    if 'url' in flask.request.args and not 'homepage' in flask.request.url:
        fields.append(form.submitAdmin)
    else:
        form.submitAdmin.label.text = form.submitAdmin.label.text + ' Admin'
        form.submitWebmail.label.text = form.submitWebmail.label.text + ' Webmail'
        if str(app.config["WEBMAIL"]).upper() != "NONE":
            fields.append(form.submitWebmail)
        if str(app.config["ADMIN"]).upper() != "FALSE":
            fields.append(form.submitAdmin)
    fields = [fields]

    if form.validate_on_submit():
        if destination := _has_usable_redirect():
            pass
        else:
            if form.submitAdmin.data:
                destination = app.config['WEB_ADMIN']
            elif form.submitWebmail.data:
                destination = app.config['WEB_WEBMAIL']
        device_cookie, device_cookie_username = utils.limiter.parse_device_cookie(flask.request.cookies.get('rate_limit'))
        username = form.email.data
        if not utils.is_app_token(form.pw.data):
            if username != device_cookie_username and utils.limiter.should_rate_limit_ip(client_ip):
                flask.flash(_('Too many attempts from your IP (rate-limit)'), 'error')
                return flask.render_template('login.html', form=form, fields=fields)
            if utils.limiter.should_rate_limit_user(username, client_ip, device_cookie, device_cookie_username):
                flask.flash(_('Too many attempts for this user (rate-limit)'), 'error')
                return flask.render_template('login.html', form=form, fields=fields)
        user = models.User.login(username, form.pw.data)
        if user:
            flask.session.regenerate()
            flask_login.login_user(user)
            if user.change_pw_next_login:
                flask.session['redirect_to'] = destination
                destination = flask.url_for('sso.pw_change')
            response = flask.redirect(destination)
            response.set_cookie('rate_limit', utils.limiter.device_cookie(username), max_age=31536000, path=flask.url_for('sso.login'), secure=app.config['SESSION_COOKIE_SECURE'], httponly=True)
            flask.current_app.logger.info(f'Login attempt for: {username}/sso/{flask.request.headers.get("X-Forwarded-Proto")} from: {client_ip}/{client_port}: success: password: {form.pwned.data}')
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
            return response
        else:
            utils.limiter.rate_limit_user(username, client_ip, device_cookie, device_cookie_username, form.pw.data) if models.User.get(username) else utils.limiter.rate_limit_ip(client_ip, username)
            flask.current_app.logger.info(f'Login attempt for: {username}/sso/{flask.request.headers.get("X-Forwarded-Proto")} from: {client_ip}/{client_port}: failed: badauth: {utils.truncated_pw_hash(form.pw.data)}')
            flask.flash(_('Wrong e-mail or password'), 'error')
    return flask.render_template('login.html', form=form, fields=fields)

@sso.route('/pw_change', methods=['GET', 'POST'])
@access.authenticated
def pw_change():
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    client_port = flask.request.headers.get('X-Real-Port', None)
    form = forms.PWChangeForm()

    if form.validate_on_submit():
        if msg := utils.isBadOrPwned(form):
            flask.flash(msg, "error")
            return flask.redirect(flask.url_for('sso.pw_change'))
        if form.oldpw.data == form.pw2.data:
            # TODO: fuzzy match?
            flask.flash(_("The new password can't be the same as the old password"), "error")
            return flask.redirect(flask.url_for('sso.pw_change'))
        if form.pw.data != form.pw2.data:
            flask.flash(_("The new passwords don't match"), "error")
            return flask.redirect(flask.url_for('sso.pw_change'))
        user = models.User.login(flask_login.current_user.email, form.oldpw.data)
        if user:
            flask.session.regenerate()
            flask_login.login_user(user)
            user.set_password(form.pw.data, keep_sessions=set(flask.session))
            user.change_pw_next_login = False
            models.db.session.commit()
            flask.current_app.logger.info(f'Forced password change by {user} from: {client_ip}/{client_port}: success: password: {form.pwned.data}')
            destination = flask.session.pop('redir_to', None) or app.config['WEB_ADMIN']
            return flask.redirect(destination)
        flask.flash(_("The current password is incorrect!"), "error")

    return flask.render_template('pw_change.html', form=form)

@sso.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    flask.session.destroy()
    response = flask.redirect(app.config['PROXY_AUTH_LOGOUT_URL'] or flask.url_for('.login'))
    for cookie in ['roundcube_sessauth', 'roundcube_sessid', 'smsession']:
        response.set_cookie(cookie, 'empty', expires=0)
    return response

"""
Redirect to the url passed in parameter if any; Ensure that this is not an open-redirect too...
https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
"""
def _has_usable_redirect(is_proxied=False):
    if 'homepage' in flask.request.url and not is_proxied:
        return None
    if url := flask.request.args.get('url'):
        url = url_unquote(url)
        target = urlparse(urljoin(flask.request.url, url))
        if target.netloc == urlparse(flask.request.url).netloc:
            return target.geturl()
    return None

"""
https://mailu.io/master/configuration.html#header-authentication-using-an-external-proxy
"""
def _proxy():
    proxy_ip = flask.request.headers.get('X-Forwarded-By', flask.request.remote_addr)
    ip = ipaddress.ip_address(proxy_ip)
    if not any(ip in cidr for cidr in app.config['PROXY_AUTH_WHITELIST']):
        flask.current_app.logger.error(f'Login failed by proxy - not on whitelist: from {client_ip} through {flask.request.remote_addr}.')
        return flask.abort(500, '%s is not on PROXY_AUTH_WHITELIST' % proxy_ip)

    email = flask.request.headers.get(app.config['PROXY_AUTH_HEADER'])
    if not email:
        flask.current_app.logger.error(f'Login failed by proxy - no header: from {client_ip} through {flask.request.remote_addr}.')
        return flask.abort(500, 'No %s header' % app.config['PROXY_AUTH_HEADER'])

    url = _has_usable_redirect(True) or app.config['WEB_ADMIN']

    user = models.User.get(email)
    if user:
        flask.session.regenerate()
        flask_login.login_user(user)
        flask.current_app.logger.info(f'Login succeeded by proxy created user: {user} from {client_ip} through {flask.request.remote_addr}.')
        return flask.redirect(url)

    if not app.config['PROXY_AUTH_CREATE']:
        flask.current_app.logger.warning(f'Login failed by proxy - does not exist: {user} from {client_ip} through {flask.request.remote_addr}.')
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
    user.set_password(secrets.token_urlsafe(), keep_sessions=set(flask.session))
    models.db.session.add(user)
    models.db.session.commit()
    flask.session.regenerate()
    flask_login.login_user(user)
    user.send_welcome()
    flask.current_app.logger.info(f'Login succeeded by proxy created user: {user} from {client_ip} through {flask.request.remote_addr}.')
    return flask.redirect(url)
