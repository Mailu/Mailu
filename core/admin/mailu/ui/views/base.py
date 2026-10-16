from mailu import models, utils, announcements
from mailu.ui import ui, forms, access

from flask import current_app as app
import flask
import flask_login


@ui.route('/', methods=["GET"])
@access.authenticated
def index():
    return flask.redirect(flask.url_for('.user_settings'))

@ui.route('/ui/')
def redirect_old_path():
    return flask.redirect(flask.url_for('.index'), code=301)

@ui.route('/announcement', methods=['GET', 'POST'])
@access.global_admin
def announcement():
    form = forms.AnnouncementForm()
    owner = flask_login.current_user.email
    draft = None
    preview_token = None
    failures = []
    retry_token = flask.request.form.get('retry_token')
    recipients = [user.email for user in models.User.query.order_by(models.User.email).all()]
    if form.validate_on_submit():
        action = flask.request.form.get('action', 'preview')
        if action == 'send':
            draft = announcements.load(flask.request.form.get('draft_token'), owner, consume=True)
            if not draft:
                flask.flash(utils.flask_babel.gettext('This preview expired or was already sent. Preview your message again.'), 'warning')
            else:
                for address in draft['recipients']:
                    user = models.User.get(address)
                    if not user or not user.sendmail(draft['subject'], draft['plain'], html_body=draft['html']):
                        failures.append(address)
                succeeded = len(draft['recipients']) - len(failures)
                flask.flash(utils.flask_babel.gettext('%(sent)s delivered; %(failed)s failed.', sent=succeeded, failed=len(failures)), 'warning' if failures else 'success')
                app.logger.info('Announcement by %s: delivered=%s failed=%s', owner, succeeded, len(failures))
                if not failures:
                    return flask.redirect(flask.url_for('.announcement'))
                form.announcement_subject.data = draft['subject']
                form.announcement_body.data = draft['html']
                # A subsequent preview retries only failed deliveries, bound server-side.
                retry_token, _ = announcements.save(draft['subject'], draft['html'], draft['plain'], failures, owner)
                draft = None
        elif action in {'preview', 'test'}:
            try:
                html, plain = announcements.sanitize(form.announcement_body.data)
                form.announcement_body.data = html
                if action == 'test':
                    if flask_login.current_user.sendmail('[TEST] ' + form.announcement_subject.data, plain, html_body=html):
                        flask.flash(utils.flask_babel.gettext('Test email sent to %(email)s.', email=owner), 'success')
                    else:
                        flask.flash(utils.flask_babel.gettext('The test email could not be delivered. Your draft is unchanged.'), 'danger')
                else:
                    retry = announcements.load(retry_token, owner)
                    if retry_token and not retry:
                        flask.flash(utils.flask_babel.gettext('This retry expired. Start a new announcement to choose all recipients again.'), 'warning')
                    else:
                        targets = retry['recipients'] if retry else recipients
                        preview_token, draft = announcements.save(form.announcement_subject.data, html, plain, targets, owner)
            except ValueError as error:
                form.announcement_body.errors = [utils.flask_babel.gettext(str(error))]
        elif action == 'edit':
            pass
        else:
            flask.abort(400)
    retry = announcements.load(retry_token, owner)
    return flask.render_template('announcement.html', form=form, draft=draft, draft_token=preview_token,
                                 recipient_count=len(retry['recipients']) if retry else len(recipients), failures=failures, retry_token=retry_token)

@ui.route('/webmail', methods=['GET'])
def webmail():
    return flask.redirect(app.config['WEB_WEBMAIL'])

@ui.route('/client', methods=['GET'])
def client():
    return flask.render_template('client.html')

@ui.route('/webui_antispam', methods=['GET'])
def antispam():
    return flask.render_template('antispam.html')
