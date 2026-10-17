from werkzeug.utils import redirect
from mailu import models, utils, auth_flow, signin, passkeys as passkey_utils
from mailu.sso import sso, forms
from mailu.ui import access

from flask import current_app as app
from flask_babel import lazy_gettext as _
import flask
import flask_login
import secrets
import ipaddress
from markupsafe import Markup

@sso.route('/login', methods=['GET', 'POST'], defaults={'target': None})
@sso.route('/login/<any(admin,webmail):target>', methods=['GET', 'POST'])
def login(target):
    if target:
        signin.target_path(target)
        signin.clear()
        signin.remember(signin.target_path(target))
    elif flask.request.method == 'GET' and 'url' in flask.request.args and 'homepage' not in flask.request.args:
        # Compatibility for existing bookmarks; new links never generate ?url=.
        signin.remember(flask.request.args['url'])
    if flask.request.headers.get(app.config['PROXY_AUTH_HEADER']) and 'noproxyauth' not in flask.request.args:
        return _proxy()

    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    client_port = flask.request.headers.get('X-Real-Port', None)
    form = forms.LoginForm()
    form.destination.choices = [(value, label) for value, label in form.destination.choices
                                if (value == 'admin' and str(app.config['ADMIN']).upper() != 'FALSE')
                                or (value == 'webmail' and str(app.config['WEBMAIL']).upper() != 'NONE')]
    selected = target or flask.request.form.get('destination') or signin.default_target()
    if signin.pending():
        selected = 'admin' if signin.pending().startswith(app.config['WEB_ADMIN']) else 'webmail'
    if form.submitAdmin.data:
        selected = 'admin'
    elif form.submitWebmail.data:
        selected = 'webmail'
    form.destination.data = selected
    fields = []
    flask.session['passkey_login_redirect'] = signin.pending()

    if form.validate_on_submit():
        # Preserve old password form submissions while sharing destination policy.
        selected = target or ('admin' if form.submitAdmin.data else 'webmail' if form.submitWebmail.data else form.destination.data)
        destination = signin.resolve(selected)
        device_cookie, device_cookie_username = utils.limiter.parse_device_cookie(flask.request.cookies.get('rate_limit'))
        username = form.email.data
        if username != device_cookie_username and utils.limiter.should_rate_limit_ip(client_ip):
            flask.flash(_('Too many attempts from your IP (rate-limit)'), 'error')
            return flask.render_template('login.html', form=form, fields=fields)
        if utils.limiter.should_rate_limit_user(username, client_ip, device_cookie, device_cookie_username):
            flask.flash(_('Too many attempts for this user (rate-limit)'), 'error')
            return flask.render_template('login.html', form=form, fields=fields)
        user = models.User.login(username, form.pw.data)
        if user:
            login_destination = destination
            signin.clear()
            flask.session.regenerate()
            flask_login.login_user(user)
            passkeys_url = flask.url_for('ui.passkey_list')
            nudge_body = Markup(_('For phishing-resistant sign-in, use a passkey next time. <a href="{}">Manage passkeys</a>.')).format(passkeys_url)
            nudge = Markup('<span {}>{}</span>').format(
                Markup(passkey_utils.PASSWORD_NUDGE_MARKER), nudge_body,
            )
            flask.flash(nudge, 'info')
            if user.change_pw_next_login:
                auth_flow.require_actions(flask.session, 'password_change', destination)
                destination = flask.url_for('sso.pw_change')
            response = _clear_webmail_cookies(flask.redirect(destination))
            response.set_cookie('rate_limit', utils.limiter.device_cookie(username), max_age=31536000, path=flask.url_for('sso.login'), secure=app.config['SESSION_COOKIE_SECURE'], httponly=True)
            flask.current_app.logger.info(f'Login attempt for: {username}/sso/{flask.request.headers.get("X-Forwarded-Proto")} from: {client_ip}/{client_port}: success: password: {form.pwned.data}')
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
            return signin.remember_preference(response, login_destination)
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
            return auth_flow.complete_action(flask.session, 'password_change')
        flask.flash(_("The current password is incorrect!"), "error")

    return flask.render_template('pw_change.html', form=form)

@sso.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    flask.session.destroy()
    response = flask.redirect(app.config['PROXY_AUTH_LOGOUT_URL'] or flask.url_for('.login'))
    return _clear_webmail_cookies(response)

"""
Drop any webmail session left over from a previous login: its credentials
are bound to the Mailu session that was just replaced and no longer work.
"""
def _clear_webmail_cookies(response):
    for cookie in ['roundcube_sessauth', 'roundcube_sessid', 'smsession']:
        response.set_cookie(cookie, 'empty', expires=0)
    return response

"""
https://mailu.io/master/configuration.html#header-authentication-using-an-external-proxy
"""
def _proxy():
    proxy_ip = flask.request.headers.get('X-Forwarded-By', flask.request.remote_addr)
    ip = ipaddress.ip_address(proxy_ip)
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    if not any(ip in cidr for cidr in app.config['PROXY_AUTH_WHITELIST']):
        flask.current_app.logger.error(f'Login failed by proxy - not on whitelist: from {client_ip} through {flask.request.remote_addr}.')
        return flask.abort(500, '%s is not on PROXY_AUTH_WHITELIST' % proxy_ip)

    email = flask.request.headers.get(app.config['PROXY_AUTH_HEADER'])
    if not email:
        flask.current_app.logger.error(f'Login failed by proxy - no header: from {client_ip} through {flask.request.remote_addr}.')
        return flask.abort(500, 'No %s header' % app.config['PROXY_AUTH_HEADER'])

    url = signin.resolve()
    login_destination = url
    signin.clear()

    user = models.User.get(email)
    if user:
        flask.session.regenerate()
        flask_login.login_user(user)
        flask.current_app.logger.info(f'Login succeeded by proxy created user: {user} from {client_ip} through {flask.request.remote_addr}.')
        if user.change_pw_next_login:
            auth_flow.require_actions(flask.session, 'password_change', url)
            url = flask.url_for('sso.pw_change')
        return signin.remember_preference(_clear_webmail_cookies(flask.redirect(url)), login_destination)

    if not app.config['PROXY_AUTH_CREATE']:
        flask.current_app.logger.warning(f'Login failed by proxy - does not exist: {user} from {client_ip} through {flask.request.remote_addr}.')
        return flask.abort(500, 'You don\'t exist. Go away! (%s)' % email)

    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    try:
        localpart, desireddomain = email.rsplit('@')
    except Exception as e:
        flask.current_app.logger.error('Error creating a new user via proxy for %s from %s: %s' % (email, client_ip, str(e)), e)
        return flask.abort(500, 'You don\'t exist. Go away! (%s)' % email)
    domain = models.db.session.get(models.Domain, desireddomain) or flask.abort(500, 'You don\'t exist. Go away! (domain=%s)' % desireddomain)
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
    return signin.remember_preference(_clear_webmail_cookies(flask.redirect(url)), login_destination)
