from freeposte import app, db, models, forms, utils
from flask.ext import login as flask_login

import os
import flask


@app.route('/user/list/<domain_name>', methods=['GET'])
@flask_login.login_required
def user_list(domain_name):
    domain = utils.get_domain_admin(domain_name)
    return flask.render_template('user/list.html', domain=domain)


@app.route('/user/create/<domain_name>', methods=['GET', 'POST'])
@flask_login.login_required
def user_create(domain_name):
    domain = utils.get_domain_admin(domain_name)
    if len(domain.users) >= domain.max_users:
        flask.flash('Too many users for domain %s' % domain, 'error')
        return flask.redirect(flask.url_for('user_list', domain_name=domain.name))
    form = forms.UserCreateForm()
    if form.validate_on_submit():
        for address in domain.users + domain.aliases:
            if address.localpart == form.localpart.data:
                flask.flash('Address %s is already used' % address, 'error')
                break
        else:
            user = models.User(localpart=form.localpart.data, domain=domain)
            user.set_password(form.pw.data)
            db.session.add(user)
            db.session.commit()
            flask.flash('User %s created' % user)
            return flask.redirect(
                flask.url_for('user_list', domain_name=domain.name))
    return flask.render_template('user/create.html',
        domain=domain, form=form)


@app.route('/user/edit/<user_email>', methods=['GET', 'POST'])
@flask_login.login_required
def user_edit(user_email):
    user = utils.get_user(user_email, True)
    form = forms.UserEditForm()
    if form.validate_on_submit():
        user.quota_bytes = form.quota.data
        db.session.add(user)
        db.session.commit()
        flask.flash('User %s updated' % user)
        return flask.redirect(
            flask.url_for('user_list', domain_name=user.domain.name))
    return flask.render_template('user/edit.html', form=form, user=user)


@app.route('/user/delete/<user_email>', methods=['GET'])
@flask_login.login_required
def user_delete(user_email):
    user = utils.get_user(user_email, True)
    db.session.delete(user)
    db.session.commit()
    flask.flash('User %s deleted' % user)
    return flask.redirect(flask.url_for('user_list', domain_name=user.domain.name))


@app.route('/user/settings', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/user/usersettings/<user_email>', methods=['GET', 'POST'])
@flask_login.login_required
def user_settings(user_email):
    user = utils.get_user(user_email)
    form = forms.UserSettingsForm()
    if form.validate_on_submit():
        user.displayed_name = form.displayed_name.data
        user.spam_enabled = form.spam_enabled.data
        user.spam_threshold = form.spam_threshold.data
        db.session.add(user)
        db.session.commit()
        flask.flash('Settings updated for %s' % user)
        if user_email:
            return flask.redirect(
                flask.url_for('user_list', domain_name=user.domain.name))
    return flask.render_template('user/settings.html', form=form, user=user)


@app.route('/user/password', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/user/password/<user_email>', methods=['GET', 'POST'])
@flask_login.login_required
def user_password(user_email):
    user = utils.get_user(user_email)
    form = forms.UserPasswordForm()
    if form.validate_on_submit():
        if form.pw.data != form.pw2.data:
            flask.flash('Passwords do not match', 'error')
        else:
            user.set_password(form.pw.data)
            db.session.add(user)
            db.session.commit()
            flask.flash('Password updated for %s' % user)
            if user_email:
                return flask.redirect(
                    flask.url_for('user_list', domain_name=user.domain.name))
    return flask.render_template('user/password.html', form=form, user=user)


@app.route('/user/forward', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/user/forward/<user_email>', methods=['GET', 'POST'])
@flask_login.login_required
def user_forward(user_email):
    user = utils.get_user(user_email)
    form = forms.UserForwardForm()
    if form.validate_on_submit():
        user.forward = form.forward.data
        db.session.add(user)
        db.session.commit()
        flask.flash('Forward destination updated for %s' % user)
        if user_email:
            return flask.redirect(
                flask.url_for('user_list', domain_name=user.domain.name))
    return flask.render_template('user/forward.html', form=form, user=user)


@app.route('/user/reply', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/user/reply/<user_email>', methods=['GET', 'POST'])
@flask_login.login_required
def user_reply(user_email):
    user = utils.get_user(user_email)
    form = forms.UserReplyForm()
    if form.validate_on_submit():
        user.reply_subject = form.reply_subject.data
        user.reply_body = form.reply_body.data
        db.session.add(user)
        db.session.commit()
        flask.flash('Auto-reply message updated for %s' % user)
        if user_email:
            return flask.redirect(
                flask.url_for('user_list', domain_name=user.domain.name))
    return flask.render_template('user/reply.html', form=form, user=user)


@app.route('/user/fetchmail', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/user/fetchmail/<user_email>', methods=['GET', 'POST'])
@flask_login.login_required
def user_fetchmail(user_email):
    return flask.render_template('user/fetchmail.html')
