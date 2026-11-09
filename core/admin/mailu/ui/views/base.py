from mailu import models, utils, announcements, oauth2, webmail
from mailu.ui import ui, forms, access

import hashlib
import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import flask
import flask_login
from flask import current_app as app


THUNDERBIRD_OAUTH_ADDON_VERSION = '1.0.3'


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
@access.authenticated
def webmail_redirect():
    client = webmail.selected(app.config, flask_login.current_user.webmail_preference)
    if not client:
        flask.abort(404)
    return flask.redirect('/' + client + '/')

@ui.route('/client', methods=['GET'])
def client():
    return flask.render_template(
        'client.html',
        thunderbird_addon_version=THUNDERBIRD_OAUTH_ADDON_VERSION,
    )


def _thunderbird_oauth_manifest():
    hostname = app.config['HOSTNAME']
    hostnames = sorted({
        item.strip()
        for item in app.config['HOSTNAMES'].split(',')
        if item.strip()
    }) or [hostname]
    base_url = f"{oauth2.issuer()}{app.config['WEB_ADMIN'].rstrip('/')}/client"
    return {
        'manifest_version': 2,
        'name': f"Mailu OAuth2 for {hostname}",
        'version': THUNDERBIRD_OAUTH_ADDON_VERSION,
        'description': f"Use OAuth2 to access mail hosted by {hostname}.",
        'applications': {
            'gecko': {
                'id': f'mailu-oauth2@{hostname}',
                'strict_min_version': '140.0',
                'update_url': f'{base_url}/thunderbird-updates.json',
            },
        },
        'oauth_provider': {
            'issuer': f'mailu-oauth2-{hostname}',
            'clientId': app.config['OAUTH2_CLIENT_ID'],
            'clientSecret': '',
            'authorizationEndpoint': oauth2.auth_url(),
            'tokenEndpoint': oauth2.token_url(),
            'redirectionEndpoint': 'http://127.0.0.1',
            'usePKCE': True,
            'useExternalBrowser': True,
            'hostnames': hostnames,
            'scopes': app.config['OAUTH2_SCOPE'],
        },
    }


def _thunderbird_oauth_package():
    package = BytesIO()
    with ZipFile(package, 'w', ZIP_DEFLATED) as addon:
        info = ZipInfo('manifest.json', date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        addon.writestr(info, json.dumps(_thunderbird_oauth_manifest(), indent=2) + '\n')
    return package.getvalue()

@ui.route('/client/thunderbird.xpi', methods=['GET'])
def thunderbird_oauth_addon():
    """Build an instance-specific Thunderbird OAuth provider add-on."""
    package = _thunderbird_oauth_package()
    response = flask.send_file(
        BytesIO(package),
        mimetype='application/x-xpinstall',
        as_attachment=True,
        download_name='mailu-thunderbird-oauth2.xpi',
        max_age=31536000,
    )
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


@ui.route('/client/thunderbird-updates.json', methods=['GET'])
def thunderbird_oauth_updates():
    """Serve the self-hosted update manifest for the Thunderbird add-on."""
    hostname = app.config['HOSTNAME']
    addon_id = f'mailu-oauth2@{hostname}'
    download_url = (
        f"{oauth2.issuer()}{app.config['WEB_ADMIN'].rstrip('/')}/client/"
        f"thunderbird.xpi?v={THUNDERBIRD_OAUTH_ADDON_VERSION}"
    )
    package = _thunderbird_oauth_package()
    response = flask.jsonify({
        'addons': {
            addon_id: {
                'updates': [{
                    'version': THUNDERBIRD_OAUTH_ADDON_VERSION,
                    'update_link': download_url,
                    'update_hash': f'sha256:{hashlib.sha256(package).hexdigest()}',
                    'applications': {'gecko': {'strict_min_version': '140.0'}},
                }],
            },
        },
    })
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

@ui.route('/webui_antispam', methods=['GET'])
def antispam():
    return flask.render_template('antispam.html')
