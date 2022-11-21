from mailu import models, utils
from mailu.ui import ui, access, forms
from flask import current_app as app

import flask
import flask_login
import wtforms
import wtforms_components

@ui.route('/user/list/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def user_list(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.render_template('user/list.html', domain=domain)


@ui.route('/user/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def user_create(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    if not domain.max_users == -1 and len(domain.users) >= domain.max_users:
        flask.flash('Too many users for domain %s' % domain, 'error')
        return flask.redirect(
            flask.url_for('.user_list', domain_name=domain.name))
    form = forms.UserForm()
    form.pw.validators = [wtforms.validators.DataRequired()]
    if domain.max_quota_bytes:
        form.quota_bytes.validators = [
            wtforms.validators.NumberRange(max=domain.max_quota_bytes)]
    if form.validate_on_submit():
        if msg := utils.isBadOrPwned(form):
            flask.flash(msg, "error")
            return flask.render_template('user/create.html',
                domain=domain, form=form)
        if domain.has_email(form.localpart.data):
            flask.flash('Email is already used', 'error')
        else:
            user = models.User(domain=domain)
            form.populate_obj(user)
            user.set_password(form.pw.data)
            models.db.session.add(user)
            models.db.session.commit()
            user.send_welcome()
            flask.flash('User %s created' % user)
            return flask.redirect(
                flask.url_for('.user_list', domain_name=domain.name))
    return flask.render_template('user/create.html',
        domain=domain, form=form)


@ui.route('/user/edit/<path:user_email>', methods=['GET', 'POST'])
@access.domain_admin(models.User, 'user_email')
def user_edit(user_email):
    user = models.User.query.get(user_email) or flask.abort(404)
    # Handle the case where user quota is more than allowed
    max_quota_bytes = user.domain.max_quota_bytes
    if max_quota_bytes and user.quota_bytes > max_quota_bytes:
        max_quota_bytes = user.quota_bytes
    # Create the form
    form = forms.UserForm(obj=user)
    wtforms_components.read_only(form.localpart)
    form.localpart.validators = []
    if max_quota_bytes:
        form.quota_bytes.validators = [
            wtforms.validators.NumberRange(max=max_quota_bytes)]
    if form.validate_on_submit():
        if form.pw.data:
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
                return flask.render_template('user/edit.html', form=form, user=user,
                    domain=user.domain, max_quota_bytes=max_quota_bytes)
        form.populate_obj(user)
        if form.pw.data:
            user.set_password(form.pw.data)
        models.db.session.commit()
        flask.flash('User %s updated' % user)
        return flask.redirect(
            flask.url_for('.user_list', domain_name=user.domain.name))
    return flask.render_template('user/edit.html', form=form, user=user,
        domain=user.domain, max_quota_bytes=max_quota_bytes)


@ui.route('/user/delete/<path:user_email>', methods=['GET', 'POST'])
@access.domain_admin(models.User, 'user_email')
@access.confirmation_required("delete {user_email}")
def user_delete(user_email):
    user = models.User.query.get(user_email) or flask.abort(404)
    domain = user.domain
    models.db.session.delete(user)
    models.db.session.commit()
    flask.flash('User %s deleted' % user)
    return flask.redirect(
        flask.url_for('.user_list', domain_name=domain.name))


@ui.route('/user/settings', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user/usersettings/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_settings(user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email_or_current) or flask.abort(404)
    form = forms.UserSettingsForm(obj=user)
    utils.formatCSVField(form.forward_destination)
    if form.validate_on_submit():
        form.forward_destination.data = form.forward_destination.data.replace(" ","").split(",")
        form.populate_obj(user)
        models.db.session.commit()
        form.forward_destination.data = ", ".join(form.forward_destination.data)
        flask.flash('Settings updated for %s' % user)
        if user_email:
            return flask.redirect(
                flask.url_for('.user_list', domain_name=user.domain.name))
    return flask.render_template('user/settings.html', form=form, user=user)


@ui.route('/user/password', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user/password/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_password(user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email_or_current) or flask.abort(404)
    form = forms.UserPasswordForm()
    if form.validate_on_submit():
        if form.pw.data != form.pw2.data:
            flask.flash('Passwords do not match', 'error')
        else:
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
                return flask.render_template('user/password.html', form=form, user=user)
            flask.session.regenerate()
            user.set_password(form.pw.data)
            models.db.session.commit()
            flask.flash('Password updated for %s' % user)
            if user_email:
                return flask.redirect(flask.url_for('.user_list',
                    domain_name=user.domain.name))
    return flask.render_template('user/password.html', form=form, user=user)


@ui.route('/user/reply', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user/reply/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_reply(user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email_or_current) or flask.abort(404)
    form = forms.UserReplyForm(obj=user)
    if form.validate_on_submit():
        form.populate_obj(user)
        models.db.session.commit()
        flask.flash('Auto-reply message updated for %s' % user)
        if user_email:
            return flask.redirect(
                flask.url_for('.user_list', domain_name=user.domain.name))
    return flask.render_template('user/reply.html', form=form, user=user)


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
            user.set_password(form.pw.data)
            user.quota_bytes = quota_bytes
            models.db.session.add(user)
            models.db.session.commit()
            user.send_welcome()
            flask.flash('Successfully signed up %s' % user)
            return flask.redirect(flask.url_for('.index'))
    return flask.render_template('user/signup.html', domain=domain, form=form)
