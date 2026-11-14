"""Administration of shared Rspamd maps."""

import flask
import flask_login
from flask import current_app as app
from flask_babel import gettext

from mailu import quarantine, spam_settings
from mailu.ui import access, forms, ui


@ui.route('/spam/settings', methods=['GET', 'POST'])
@access.spam_admin
def spam_settings_page():
    form = forms.SpamSettingsForm()
    settings = spam_settings.get_settings()
    if flask.request.method == 'GET':
        for key, value in settings.items():
            getattr(form, key).data = value
    elif form.validate_on_submit():
        values = {key: getattr(form, key).data for key in spam_settings.MAP_DEFAULTS}
        values.update({
            'summary_enabled': form.summary_enabled.data,
            'summary_periodicity': form.summary_periodicity.data,
            'summary_subject': form.summary_subject.data,
            'summary_template': form.summary_template.data,
        })
        try:
            settings = spam_settings.normalize_settings(values)
        except ValueError as error:
            if 'quarantine_table' in str(error):
                form.summary_template.errors.append(str(error))
            else:
                flask.flash(str(error), 'danger')
        else:
            if form.send_test.data:
                user = flask_login.current_user
                accessible = quarantine.visible_entries(user)
                mailboxes = {address for item in accessible
                             for address in item.get('recipients', [])
                             if isinstance(address, str)}
                matches = quarantine.summary_messages(
                    user, accessible, settings['summary_periodicity'],
                    mailbox_emails=mailboxes,
                )
                if not matches:
                    flask.flash(gettext('No quarantined messages are available in your mailboxes for this period; no test email was sent.'), 'info')
                else:
                    try:
                        subject, plain, html_body = quarantine.render_summary(
                            settings, user, accessible, test=True,
                            mailbox_emails=mailboxes,
                        )
                        if user.sendmail(subject, plain, html_body=html_body):
                            flask.flash(gettext('A test summary was sent to %(email)s.',
                                                email=user.email), 'success')
                        else:
                            flask.flash(gettext('The test summary could not be delivered.'), 'danger')
                    except ValueError as error:
                        flask.flash(str(error), 'danger')
            else:
                spam_settings.save_settings(values)
                app.logger.info('Global spam settings updated by %s', flask_login.current_user.email)
                flask.flash(gettext('Spam settings saved.'), 'success')
                return flask.redirect(flask.url_for('.spam_settings_page'))
    return flask.render_template('spam_settings.html', form=form)
