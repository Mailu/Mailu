from mailu import models, utils
from mailu.ui import ui, forms, access

from flask import current_app as app
import flask
import flask_login


@ui.route('/', methods=["GET"])
@access.authenticated
def index():
    return flask.redirect(flask.url_for('.user_settings'))


@ui.route('/login', methods=['GET', 'POST'])
def login():
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    form = forms.LoginForm()
    if form.validate_on_submit():
        device_cookie, device_cookie_username = utils.limiter.parse_device_cookie(flask.request.cookies.get('rate_limit'))
        username = form.email.data
        if username != device_cookie_username and utils.limiter.should_rate_limit_ip(client_ip):
            flask.flash('Too many attempts from your IP (rate-limit)', 'error')
            return flask.render_template('login.html', form=form)
        if utils.limiter.should_rate_limit_user(username, client_ip, device_cookie, device_cookie_username):
            flask.flash('Too many attempts for this user (rate-limit)', 'error')
            return flask.render_template('login.html', form=form)
        user = models.User.login(username, form.pw.data)
        if user:
            flask.session.regenerate()
            flask_login.login_user(user)
            endpoint = flask.request.args.get('next', '.index')
            response = flask.redirect(flask.url_for(endpoint)
                or flask.url_for('.index'))
            response.set_cookie('rate_limit', utils.limiter.device_cookie(username), max_age=31536000, path=flask.url_for('ui.login'))
            flask.current_app.logger.info(f'Login succeeded for {username} from {client_ip}.')
            return response
        else:
            utils.limiter.rate_limit_user(username, client_ip, device_cookie, device_cookie_username) if models.User.get(username) else utils.limiter.rate_limit_ip(client_ip)
            flask.current_app.logger.warn(f'Login failed for {username} from {client_ip}.')
            flask.flash('Wrong e-mail or password', 'error')
    return flask.render_template('login.html', form=form)


@ui.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    flask.session.destroy()
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

@ui.route('/antispam', methods=['GET'])
def antispam():
    return flask.render_template('antispam.html')

