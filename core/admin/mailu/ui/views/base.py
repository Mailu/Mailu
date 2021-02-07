from mailu import models, utils
from mailu.ui import ui, forms, access

import flask
import flask_login
from flask import current_app as app

@ui.route('/', methods=["GET"])
@access.authenticated
def index():
    return flask.redirect(flask.url_for('.user_settings'))


@ui.route('/login', methods=['GET', 'POST'])
def login():
    client_ip = flask.request.headers["X-Real-IP"] if 'X-Real-IP' in flask.request.headers else flask.request.remote_addr
    form = forms.LoginForm()
    if app.config['RECAPTCHA_PUBLIC_KEY'] != "" and app.config['RECAPTCHA_PRIVATE_KEY'] != "":
        form = forms.LoginFormCaptcha()
    if utils.limiter.should_rate_limit_ip(client_ip):
        flask.flash('Too many attempts from your IP (rate-limit)', 'error')
        return flask.render_template('login.html', form=form)
    if form.validate_on_submit():
        username = form.email.data
        if utils.limiter.should_rate_limit_user(username, client_ip):
            flask.flash('Too many attempts for this user (rate-limit)', 'error')
            return flask.render_template('login.html', form=form)
        user = models.User.login(username, form.pw.data)
        if user:
            flask_login.login_user(user)
            utils.limiter.exempt_ip_from_ratelimits(client_ip)
            endpoint = flask.request.args.get('next', '.index')
            return flask.redirect(flask.url_for(endpoint)
                or flask.url_for('.index'))
        else:
            utils.limiter.rate_limit_user(username, client_ip) if models.User.get(username) else utils.limiter.rate_limit_ip(client_ip)
            flask.flash('Wrong e-mail or password', 'error')
    return flask.render_template('login.html', form=form)


@ui.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    return flask.redirect(flask.url_for('.index'))


@ui.route('/announcement', methods=['GET', 'POST'])
@access.global_admin
def announcement():
    form = forms.AnnouncementForm()
    if form.validate_on_submit():
        for user in models.User.query.all():
            user.sendmail(form.announcement_subject.data,
                form.announcement_body.data)
        # Force-empty the form
        form.announcement_subject.data = ''
        form.announcement_body.data = ''
        flask.flash('Your announcement was sent', 'success')
    return flask.render_template('announcement.html', form=form)

@ui.route('/webmail', methods=['GET'])
def webmail():
    return flask.redirect(app.config['WEB_WEBMAIL'])

@ui.route('/client', methods=['GET'])
def client():
    return flask.render_template('client.html')
