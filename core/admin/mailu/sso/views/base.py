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
from urllib.parse import urlparse, urljoin, unquote

@sso.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.headers.get(app.config['PROXY_AUTH_HEADER']) and 'noproxyauth' not in flask.request.url:
        return _proxy()

    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    client_port = flask.request.headers.get('X-Real-Port', None)
    form = forms.LoginForm()

    # [OIDC] Make sure the client_ip is an alphanumeric string containing only digits and dots
    if client_ip is None or not client_ip.isalnum():
        client_ip = flask.request.remote_addr
    else:
        client_ip = ''.join(c for c in client_ip if c.isdigit() or c == '.')

    # [OIDC] Parse the device cookie for rate limiting
    device_cookie, device_cookie_username = utils.limiter.parse_device_cookie(flask.request.cookies.get('rate_limit'))

    fields = []

    if 'url' in flask.request.args and 'homepage' not in flask.request.url:
        fields.append(form.submitAdmin)
    else:
        form.submitAdmin.label.text = form.submitAdmin.label.text + ' Admin'
        form.submitWebmail.label.text = form.submitWebmail.label.text + ' Webmail'
        if str(app.config["WEBMAIL"]).upper() != "NONE":
            fields.append(form.submitWebmail)
        if str(app.config["ADMIN"]).upper() != "FALSE":
            fields.append(form.submitAdmin)
    fields = [fields]

    # [OIDC] Add the OIDC login flow
    if 'code' in flask.request.args:
        try:
            username, sub, id_token, token_response = utils.oic_client.exchange_code(flask.request.query_string.decode())
        
            if username is None:
                utils.limiter.rate_limit_user(username, client_ip, device_cookie, device_cookie_username) if models.User.get(username) else utils.limiter.rate_limit_ip(client_ip)
                flask.current_app.logger.warning(f'Login failed for {username} from {client_ip}.')
                flask.flash('Wrong e-mail or password', 'error')
                return render_oidc_template(form, fields)
            
            user = models.User.get(username)
            if user is None:
                user = models.User.create(username)

            flask.session.regenerate()

            flask.session['oidc_token'] = token_response
            flask.session['oidc_sub'] = sub
            flask.session['oidc_id_token'] = id_token

            flask_login.login_user(user)

            response = redirect(flask.session['redirect_to'] if 'redirect_to' in flask.session else app.config['WEB_ADMIN'])
            response.set_cookie('rate_limit', utils.limiter.device_cookie(username), max_age=31536000, path=flask.url_for('sso.login'), secure=app.config['SESSION_COOKIE_SECURE'], httponly=True)
            flask.current_app.logger.info(f'Login succeeded for {username} from {client_ip}.')
            return response
        except Exception as e:
            flask.flash(str(e), 'error')

    if form.validate_on_submit():
        if destination := _has_usable_redirect():
            pass
        else:
            if form.submitAdmin.data:
                destination = app.config['WEB_ADMIN']
            elif form.submitWebmail.data:
                destination = app.config['WEB_WEBMAIL']
        # [OIDC] device_cookie and device_cookie_username are already set
        username = form.email.data
        if not utils.is_app_token(form.pw.data):
            if username != device_cookie_username and utils.limiter.should_rate_limit_ip(client_ip):
                flask.flash(_('Too many attempts from your IP (rate-limit)'), 'error')
                return render_oidc_template(form, fields)
            if utils.limiter.should_rate_limit_user(username, client_ip, device_cookie, device_cookie_username):
                flask.flash(_('Too many attempts for this user (rate-limit)'), 'error')
                return render_oidc_template(form, fields)
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
    # [OIDC] Forward the OIDC data to the login template
    return render_oidc_template(form, fields)

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
            destination = flask.session.pop('redirect_to', None) or app.config['WEB_ADMIN']
            return flask.redirect(destination)
        flask.flash(_("The current password is incorrect!"), "error")

    return flask.render_template('pw_change.html', form=form, fields=[])

@sso.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    flask.session.destroy()
    response = flask.redirect(app.config['PROXY_AUTH_LOGOUT_URL'] or flask.url_for('.login'))
    for cookie in ['roundcube_sessauth', 'roundcube_sessid', 'smsession']:
        response.set_cookie(cookie, 'empty', expires=0)
    return response

# [OIDC] Add the backchannel logout endpoint
@sso.route('/backchannel-logout', methods=['POST'])
def backchannel_logout():
    if not utils.oic_client.is_enabled():
        return flask.abort(404)
    if not utils.oic_client.backchannel_logout(flask.request.form):
        return flask.abort(400)
    return {'code': 200, 'message': 'Backchannel logout successful.'}, 200

"""
Redirect to the url passed in parameter if any; Ensure that this is not an open-redirect too...
https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
"""
def _has_usable_redirect(is_proxied=False):
    if 'homepage' in flask.request.url and not is_proxied:
        return None
    if url := flask.request.args.get('url'):
        target = urlparse(urljoin(flask.request.url, unquote(url)))
        if target.netloc == urlparse(flask.request.url).netloc:
            return target.geturl()
    return None

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

def render_oidc_template(form, fields):
    redirect_url = utils.oic_client.get_redirect_url()
    if 'url' in flask.request.args:
        flask.session['redirect_to'] = flask.request.args.get('url')
    
    oidc_enabled = utils.oic_client.is_enabled()
    if redirect_url is None:
        oidc_enabled = False
    return flask.render_template('login.html', form=form, fields=fields, openId=oidc_enabled, openIdEndpoint=redirect_url)