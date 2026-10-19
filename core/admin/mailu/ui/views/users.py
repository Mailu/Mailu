from mailu import models, utils, openpgp, announcements
from datetime import date, datetime
from markupsafe import escape
from mailu.ui import ui, access, forms
from flask import current_app as app

import flask
import flask_login
import wtforms
import wtforms_components
import secrets

@ui.route('/user/list/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def user_list(domain_name):
    domain = models.db.session.get(models.Domain, domain_name) or flask.abort(404)
    passkey_counts = {}
    rows = (
        models.db.session.query(
            models.Passkey.user_email,
            models.db.func.count(),
        )
        .join(models.User, models.User.email == models.Passkey.user_email)
        .filter(models.User.domain_name == domain.name)
        .group_by(models.Passkey.user_email)
    )
    passkey_counts = dict(rows)
    return flask.render_template(
        'user/list.html', domain=domain,
        passkey_counts=passkey_counts,
    )


@ui.route('/user/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def user_create(domain_name):
    domain = models.db.session.get(models.Domain, domain_name) or flask.abort(404)
    if not domain.max_users == -1 and len(domain.users) >= domain.max_users:
        flask.flash('Too many users for domain %s' % domain, 'error')
        return flask.redirect(
            flask.url_for('.user_list', domain_name=domain.name))
    form = forms.UserForm()
    password_disabled = app.config.get('PASSKEY_REQUIRED', False)
    form.pw.validators = [] if password_disabled else [wtforms.validators.DataRequired()]
    max_quota_bytes = min(domain.max_quota_bytes or forms.MAX_QUOTA_BYTES, forms.MAX_QUOTA_BYTES)
    form.quota_bytes.validators = [
        wtforms.validators.NumberRange(min=0, max=max_quota_bytes)]
    form.quota_bytes.default = min(int(app.config['DEFAULT_QUOTA']), max_quota_bytes)
    if form.validate_on_submit():
        if msg := utils.isBadOrPwned(form):
            flask.flash(msg, "error")
            return flask.render_template('user/create.html',
                domain=domain, form=form, max_quota_bytes=max_quota_bytes)
        if domain.has_email(form.localpart.data):
            flask.flash('Email is already used', 'error')
        else:
            user = models.User(domain=domain)
            form.populate_obj(user)
            user.set_password(form.pw.data or secrets.token_urlsafe())
            models.db.session.add(user)
            models.db.session.commit()
            user.send_welcome()
            flask.flash('User %s created' % user)
            return flask.redirect(
                flask.url_for('.user_list', domain_name=domain.name))
    elif not form.is_submitted():
        # only (re)apply the dynamic field defaults on the initial GET; on a
        # failed submit keep the entered values and validation errors
        form.process()
    return flask.render_template('user/create.html',
        domain=domain, form=form, max_quota_bytes=max_quota_bytes)


@ui.route('/user/edit/<path:user_email>', methods=['GET', 'POST'])
@access.domain_admin(models.User, 'user_email')
def user_edit(user_email):
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    # Handle the case where user quota is more than allowed
    max_quota_bytes = min(
        user.domain.max_quota_bytes or forms.MAX_QUOTA_BYTES,
        forms.MAX_QUOTA_BYTES)
    if max_quota_bytes and user.quota_bytes > max_quota_bytes:
        max_quota_bytes = user.quota_bytes
    # Create the form
    form = forms.UserForm(obj=user)
    wtforms_components.read_only(form.localpart)
    form.localpart.validators = []
    password_disabled = app.config.get('PASSKEY_REQUIRED', False)
    if user.passkeys or password_disabled:
        form.pw.validators = []
        form.pw2.validators = []
    form.quota_bytes.validators = [
        wtforms.validators.NumberRange(min=0, max=max_quota_bytes)]
    if form.validate_on_submit():
        if form.pw.data and not user.passkeys and not password_disabled:
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
                return _render_user_edit(form, user, max_quota_bytes)
        keep_passkey_enrollment_flag = (
            user.passkey_enroll_next_login
            if user.domain.passkey_require_enrollment
            else None
        )
        form.populate_obj(user)
        if keep_passkey_enrollment_flag is not None:
            user.passkey_enroll_next_login = keep_passkey_enrollment_flag
        if form.pw.data and not user.passkeys and not password_disabled:
            user.set_password(form.pw.data, keep_sessions=set(flask.session))
        models.db.session.commit()
        flask.flash('User %s updated' % user)
        return flask.redirect(
            flask.url_for('.user_list', domain_name=user.domain.name))
    return _render_user_edit(form, user, max_quota_bytes)


def _render_user_edit(form, user, max_quota_bytes):
    can_generate_enrollment_link = (
        user.email != flask_login.current_user.email
        and (flask_login.current_user.global_admin
             or user.domain in flask_login.current_user.get_managed_domains())
    )
    return flask.render_template(
        'user/edit.html', form=form, user=user, domain=user.domain,
        max_quota_bytes=max_quota_bytes,
        can_generate_enrollment_link=can_generate_enrollment_link,
        enrollment_url=flask.session.pop('new_passkey_enrollment_url', None),
        enrollment_expires_at=flask.session.pop('new_passkey_enrollment_expires_at', None),
    )


@ui.route('/user/settings', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user/usersettings/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_settings(user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email_or_current) or flask.abort(404)
    form = forms.UserSettingsForm(obj=user)
    utils.formatCSVField(form.forward_destination)
    if form.validate_on_submit():
        submitted_key = (form.gpg_key.data or '').strip()
        key_changed = (
            submitted_key != (user.gpg_key or '')
            or 'submit_gpg_key' in flask.request.form
        )
        uid_keys = []
        if key_changed and submitted_key:
            public_key, uid_keys = openpgp.parse_public_key(submitted_key, user.email,
                authorize_addresses=lambda addresses: models.wkd_addresses_for_user(user, addresses))
            if public_key is None:
                form.gpg_key.errors = [utils.flask_babel.gettext('Enter a valid OpenPGP public key for this email address.')]
                flask.flash('The OpenPGP key is invalid, contains secret material, or has no valid user ID for this email address', 'error')
                return flask.render_template('user/settings.html', form=form, user=user)
            form.gpg_key.data = public_key
        user.forward_enabled = bool(flask.request.form.get('forward_enabled', False))
        if user.forward_enabled and not form.forward_destination.data:
            form.forward_destination.errors = [utils.flask_babel.gettext('Destination email address is missing')]
            flask.flash('Destination email address is missing', 'error')
            return flask.render_template('user/settings.html', form=form, user=user)
        form.forward_destination.data = form.forward_destination.data.replace(" ","").split(",")
        form.populate_obj(user)
        if key_changed:
            models.update_wkd_keys(user, uid_keys)
        models.db.session.commit()
        form.forward_destination.data = ", ".join(form.forward_destination.data)
        flask.flash('Settings updated for %s' % user)
        if user_email:
            return flask.redirect(
                flask.url_for('.user_list', domain_name=user.domain.name))
    elif form.is_submitted() and not form.validate():
            flask.flash('Error validating the form', 'error')
            return flask.render_template('user/settings.html', form=form, user=user)
    return flask.render_template('user/settings.html', form=form, user=user)


def wkd_lookup(key_hash, domain_name=None):
    domain_name = _wkd_domain_from_request(domain_name)
    if len(key_hash) != 32 or any(c not in 'ybndrfg8ejkmcpqxot1uwisza345h769' for c in key_hash):
        flask.abort(404)
    keys = [key_data for key_data, in models.db.session.query(models.WkdKey.key_data
        ).filter_by(key_hash=key_hash, domain_name=domain_name).all()]
    keys = list(dict.fromkeys(key for key in keys if key))
    if not keys:
        flask.abort(404)
    return flask.Response(b''.join(keys), mimetype='application/octet-stream')


def wkd_policy(domain_name=None):
    _wkd_domain_from_request(domain_name)
    return flask.Response('', mimetype='text/plain')


def _wkd_domain_from_request(domain_name=None):
    host = flask.request.host.split(':', 1)[0].lower()
    domain_name = (domain_name or host).lower()
    if host not in (domain_name, f'openpgpkey.{domain_name}'):
        flask.abort(404)
    return domain_name

def _process_password_change(form, user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email_or_current) or flask.abort(404)
    if user.passkeys or app.config.get('PASSKEY_REQUIRED', False):
        flask.flash(utils.flask_babel.gettext('Password sign-in is disabled because passkeys are required.'), 'info')
        return flask.redirect(flask.url_for('.passkey_list', user_email=user.email))
    if form.validate_on_submit():
        if form.pw.data != form.pw2.data:
            flask.flash('Passwords do not match', 'error')
        elif user_email or models.User.login(user_email_or_current, form.current_pw.data):
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
                return flask.render_template('user/password.html', form=form, user=user)
            flask.session.regenerate()
            user.set_password(form.pw.data, keep_sessions=set(flask.session))
            models.db.session.commit()
            flask.flash('Password updated for %s' % user)
            if user_email:
                return flask.redirect(flask.url_for('.user_list',
                    domain_name=user.domain.name))
        else:
            flask.flash('Wrong current password', 'error')
    return flask.render_template('user/password.html', form=form, user=user)

@ui.route('/user/password', methods=['GET', 'POST'], defaults={'user_email': None})
@access.owner(models.User, 'user_email')
def user_password_change(user_email):
    return _process_password_change(forms.UserPasswordChangeForm(), user_email)

@ui.route('/user/password/<path:user_email>', methods=['GET', 'POST'])
@access.domain_admin(models.User, 'user_email')
def user_password(user_email):
    return _process_password_change(forms.UserPasswordForm(), user_email)

@ui.route('/user/reply', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user/reply/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_reply(user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email_or_current) or flask.abort(404)
    form = forms.UserReplyForm(obj=user)
    if flask.request.method == 'GET':
        unlimited = user.reply_startdate == date(1900, 1, 1) and user.reply_enddate == date(2999, 12, 31)
        form.reply_schedule.data = 'always' if unlimited and user.reply_enabled else 'dates'
        if unlimited:
            form.reply_startdate.data = form.reply_enddate.data = None
    if flask.request.method == 'POST' and flask.request.form.get('reply_formatted') != '1':
        form.reply_body_html.data = ''
    if form.validate_on_submit():
        if not form.reply_enabled.data:
            user.reply_enabled = False
            models.db.session.commit()
            flask.flash(utils.flask_babel.gettext('Automatic reply is off. Your saved message and dates have been kept.'), 'success')
            return flask.redirect(flask.url_for('.user_reply', user_email=user_email))
        html, plain = None, form.reply_body.data or ''
        try:
            if form.reply_body_html.data:
                try:
                    html, plain = announcements.sanitize(form.reply_body_html.data)
                except ValueError:
                    if form.reply_enabled.data:
                        raise
                    plain = ''
            if form.reply_enabled.data and not plain.strip():
                raise ValueError('Enter a message before continuing.')
        except ValueError as error:
            form.reply_body.errors = [utils.flask_babel.gettext(str(error))]
        else:
            user.reply_enabled = form.reply_enabled.data
            user.reply_subject = form.reply_subject.data or ''
            user.reply_body = plain
            user.reply_body_html = html
            if form.reply_schedule.data == 'always':
                user.reply_startdate, user.reply_enddate = date(1900, 1, 1), date(2999, 12, 31)
            elif form.reply_startdate.data and form.reply_enddate.data:
                user.reply_startdate, user.reply_enddate = form.reply_startdate.data, form.reply_enddate.data
            models.db.session.commit()
            flask.flash(utils.flask_babel.gettext('Auto-reply message updated for %(user)s', user=user.email), 'success')
            if user_email:
                return flask.redirect(flask.url_for('.user_list', domain_name=user.domain.name))
            return flask.redirect(flask.url_for('.user_reply'))
    if not user.reply_enabled:
        status = utils.flask_babel.gettext('Off')
    elif user.reply_active:
        status = utils.flask_babel.gettext('Active')
    elif user.reply_startdate > date.today():
        status = utils.flask_babel.gettext('Scheduled')
    else:
        status = utils.flask_babel.gettext('Ended')
    return flask.render_template('user/reply.html', form=form, user=user, reply_status=status,
                                 server_timezone=datetime.now().astimezone().tzname())



@ui.route('/user/reply/preview', methods=['POST'], defaults={'user_email': None})
@ui.route('/user/reply/<path:user_email>/preview', methods=['POST'])
@access.owner(models.User, 'user_email')
def user_reply_preview(user_email):
    form = forms.ConfirmationForm()
    if not form.validate_on_submit():
        return flask.jsonify(error=utils.flask_babel.gettext('Your session expired. Reload the page and try again.')), 400
    body = flask.request.form.get('reply_body_html', '')
    if len(body) > 100000:
        return flask.jsonify(error=utils.flask_babel.gettext('The message is too long.')), 400
    try:
        if body:
            html, plain = announcements.sanitize(body)
        else:
            plain = flask.request.form.get('reply_body', '').strip()
            if not plain or len(plain) > 100000:
                raise ValueError('Enter a message before continuing.')
            html = '<p>' + str(escape(plain)).replace('\n', '<br>') + '</p>'
    except ValueError as error:
        return flask.jsonify(error=utils.flask_babel.gettext(str(error))), 400
    return flask.jsonify(html=html, plain=plain)


@ui.route('/user/signup', methods=['GET', 'POST'])
@ui.route('/user/signup/<domain_name>', methods=['GET', 'POST'])
def user_signup(domain_name=None):
    available_domains = {
        domain.name: domain
        for domain in models.Domain.query.filter_by(signup_enabled=True).all()
        if domain.max_users == -1 or len(domain.users) < domain.max_users
    }
    if not available_domains:
        flask.flash('No domain available for registration')
    if not domain_name:
        return flask.render_template('user/signup_domain.html',
            available_domains=available_domains)
    domain = available_domains.get(domain_name) or flask.abort(404)
    quota_bytes = domain.max_quota_bytes or app.config['DEFAULT_QUOTA']
    if app.config['RECAPTCHA_PUBLIC_KEY'] == "" or app.config['RECAPTCHA_PRIVATE_KEY'] == "":
        form = forms.UserSignupForm()
    else:
        form = forms.UserSignupFormCaptcha()

    if form.validate_on_submit():
        if domain.has_email(form.localpart.data) or models.Alias.resolve(form.localpart.data, domain_name):
            flask.flash('Email is already used', 'error')
        else:
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
                return flask.render_template('user/signup.html', domain=domain, form=form)
            flask.session.regenerate()
            user = models.User(domain=domain)
            form.populate_obj(user)
            user.change_pw_next_login = True
            user.set_password(form.pw.data)
            user.quota_bytes = quota_bytes
            models.db.session.add(user)
            models.db.session.commit()
            user.send_welcome()
            flask.flash('Successfully signed up %s' % user)
            return flask.redirect(flask.url_for('.index'))
    return flask.render_template('user/signup.html', domain=domain, form=form)
