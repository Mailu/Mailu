from mailu import dockercli, app, db, models, forms, access

import flask
import flask_login
import smtplib

from email.mime import text
from urllib import parse


@app.route('/', methods=["GET"])
@access.authenticated
def index():
    return flask.redirect(flask.url_for('.user_settings'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LoginForm()
    if form.validate_on_submit():
        user = models.User.login(form.email.data, form.pw.data)
        if user:
            flask_login.login_user(user)
            endpoint = flask.request.args.get('next')
            return flask.redirect(flask.url_for(endpoint)
                or flask.url_for('.index'))
        else:
            flask.flash('Wrong e-mail or password', 'error')
    return flask.render_template('login.html', form=form)


@app.route('/logout', methods=['GET'])
@access.authenticated
def logout():
    flask_login.logout_user()
    return flask.redirect(flask.url_for('.index'))


@app.route('/services', methods=['GET'])
@access.global_admin
def services():
    try:
        containers = dockercli.get()
    except Exception as error:
        return flask.render_template('docker-error.html', error=error)
    return flask.render_template('services.html', containers=containers)


@app.route('/announcement', methods=['GET', 'POST'])
@access.global_admin
def announcement():
    from_address = '{}@{}'.format(
        app.config['POSTMASTER'], app.config['DOMAIN'])
    form = forms.AnnouncementForm()
    if form.validate_on_submit():
        with smtplib.SMTP('smtp') as smtp:
            for recipient in [user.email for user in models.User.query.all()]:
                msg = text.MIMEText(form.announcement_body.data)
                msg['Subject'] = form.announcement_subject.data
                msg['From'] = from_address
                msg['To'] = recipient
                smtp.sendmail(from_address, [recipient], msg.as_string())
        # Force-empty the form
        form.announcement_subject.data = ''
        form.announcement_body.data = ''
        flask.flash('Your announcement was sent', 'success')
    return flask.render_template('announcement.html', form=form,
        from_address=from_address)
