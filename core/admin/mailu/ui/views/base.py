from mailu import models, utils
from mailu.ui import ui, forms, access

from flask import current_app as app
import flask
import flask_login


@ui.route('/', methods=["GET"])
@access.authenticated
def index():
    return flask.redirect(flask.url_for('.user_settings'))

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

