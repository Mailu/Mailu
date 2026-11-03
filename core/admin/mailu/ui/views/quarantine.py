import math
import smtplib

import flask
import flask_login
from flask import current_app as app

from mailu import greylist, models, quarantine
from mailu.ui import access, forms, ui


def _visible(metadata, user):
    return bool(_visible_recipients(metadata, user))


def _visible_recipients(metadata, user):
    return quarantine.visible_recipients(metadata, user)


def _release_recipients(metadata, user):
    recipients = _visible_recipients(metadata, user)
    if not any(address.lower() == user.email.lower() for address in metadata.get('recipients', [])
               if isinstance(address, str)):
        recipients.append(user.email)
    return recipients


@ui.route('/quarantine')
@access.authenticated
def quarantine_list():
    user = flask_login.current_user
    messages = quarantine.visible_entries(user, quarantine.all_entries())
    has_messages = bool(messages)
    return flask.render_template('quarantine/list.html', messages=messages,
                                 has_messages=has_messages)


@ui.route('/quarantine/<message_id>')
@access.authenticated
def quarantine_detail(message_id):
    record = quarantine.get(message_id)
    if not record or not _visible(record[0], flask_login.current_user):
        flask.abort(404)
    message = record[0]
    return flask.render_template(
        'quarantine/detail.html', message=message,
        body=quarantine.safe_preview(record[1]),
        symbols=_symbols(message.get('symbols')),
        extra_metadata={key: value for key, value in message.items()
                        if key not in {'id', 'received', 'recipients', 'from', 'subject',
                                       'header_from', 'header_subject', 'score', 'symbols',
                                       'size', 'kind', 'greylisted'}},
    )


def _symbols(raw_symbols):
    if isinstance(raw_symbols, dict):
        raw_symbols = [{'name': name, **(data if isinstance(data, dict) else {'score': data})}
                       for name, data in raw_symbols.items()]
    if not isinstance(raw_symbols, list):
        return []
    result = []
    for symbol in raw_symbols:
        if isinstance(symbol, str):
            result.append({'name': symbol, 'score': None, 'options': []})
        elif isinstance(symbol, dict):
            name = symbol.get('name') or symbol.get('symbol')
            if isinstance(name, str):
                options = symbol.get('options', [])
                result.append({'name': name, 'score': symbol.get('score'),
                               'options': options if isinstance(options, list) else []})
    result.sort(
        key=lambda symbol: abs(symbol['score'])
        if isinstance(symbol['score'], (int, float)) and not isinstance(symbol['score'], bool)
        and math.isfinite(symbol['score']) else -1,
        reverse=True,
    )
    return result


@ui.route('/quarantine/<message_id>/release', methods=['GET', 'POST'])
@access.authenticated
def quarantine_release(message_id):
    record = quarantine.get(message_id)
    if not record or not _visible(record[0], flask_login.current_user):
        flask.abort(404)
    metadata, path = record
    recipients = _release_recipients(metadata, flask_login.current_user)
    form = forms.ConfirmationForm()
    if not form.validate_on_submit():
        return flask.render_template('quarantine/release.html', message=metadata,
                                     recipients=recipients, form=form)
    selected = list(dict.fromkeys(flask.request.form.getlist('recipients')))
    if not selected or any(recipient not in recipients for recipient in selected):
        flask.abort(400)
    mailboxes = [models.User.get(recipient) for recipient in selected]
    if any(not mailbox or not mailbox.enabled for mailbox in mailboxes):
        flask.abort(404)
    learning_failures = quarantine.learn_ham(path.read_bytes())
    sender = f"{app.config['POSTMASTER']}@{app.config['DOMAIN']}"
    try:
        with smtplib.LMTP(host=app.config['FRONT_ADDRESS'], port=2525, timeout=10) as lmtp:
            refused = lmtp.sendmail(sender, selected, path.read_bytes())
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
    except (smtplib.SMTPException, OSError):
        app.logger.exception('Quarantine release failed for %s', message_id)
        flask.abort(503)
    quarantine.delete(message_id)
    if learning_failures:
        reason = '; '.join(learning_failures)
        app.logger.warning('Rspamd ham learning failed for quarantine message %s: %s',
                           message_id, reason)
        flask.flash(f'Message released, but Rspamd ham learning failed ({reason}).', 'warning')
    else:
        flask.flash('Message released to the mailbox and learned as ham.', 'success')
    return flask.redirect(flask.url_for('.quarantine_list'))


@ui.route('/quarantine/greylist/<record_id>/release', methods=['GET', 'POST'])
@access.authenticated
def greylist_release(record_id):
    record = greylist.get(record_id)
    if not record or not _visible(record[0], flask_login.current_user):
        flask.abort(404)
    metadata, path = record
    recipients = _release_recipients(metadata, flask_login.current_user)
    form = forms.ConfirmationForm()
    if not form.validate_on_submit():
        return flask.render_template('quarantine/release.html', message=metadata,
                                     recipients=recipients, form=form, greylisted=True)
    selected = list(dict.fromkeys(flask.request.form.getlist('recipients')))
    if not selected or any(recipient not in recipients for recipient in selected):
        flask.abort(400)
    mailboxes = [models.User.get(recipient) for recipient in selected]
    if any(not mailbox or not mailbox.enabled for mailbox in mailboxes):
        flask.abort(404)
    raw_message = path.read_bytes()
    learning_failures = quarantine.learn_ham(raw_message)
    sender = f"{app.config['POSTMASTER']}@{app.config['DOMAIN']}"
    try:
        with smtplib.LMTP(host=app.config['FRONT_ADDRESS'], port=2525, timeout=10) as lmtp:
            refused = lmtp.sendmail(sender, selected, raw_message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
    except (smtplib.SMTPException, OSError):
        app.logger.exception('Greylisted message release failed for %s', record_id)
        flask.abort(503)
    greylist.delete(record_id)
    if learning_failures:
        reason = '; '.join(learning_failures)
        app.logger.warning('Rspamd ham learning failed for released greylisted message %s: %s',
                           record_id, reason)
        flask.flash(f'Message released, but Rspamd ham learning failed ({reason}).', 'warning')
    else:
        flask.flash('Message released to the mailbox and learned as ham.', 'success')
    return flask.redirect(flask.url_for('.quarantine_list'))


@ui.route('/quarantine/<message_id>/delete', methods=['GET', 'POST'])
@access.authenticated
def quarantine_delete(message_id):
    record = quarantine.get_any(message_id)
    if not record or not _visible(record[0], flask_login.current_user):
        flask.abort(404)
    form = forms.ConfirmationForm()
    if form.validate_on_submit():
        quarantine.delete(message_id)
        flask.flash('Saved message permanently deleted.', 'success')
        return flask.redirect(flask.url_for('.quarantine_list'))
    if flask.request.method == 'POST':
        flask.abort(400)
    return flask.render_template('quarantine/confirm_delete.html',
                                 message=record[0], form=form, flush=False)


@ui.route('/quarantine/flush', methods=['GET', 'POST'])
@access.authenticated
def quarantine_flush():
    form = forms.ConfirmationForm()
    messages = [item for item in quarantine.all_entries()
                if _visible(item, flask_login.current_user)]
    count = len(messages)
    if form.validate_on_submit():
        count = quarantine.flush(item['id'] for item in messages)
        flask.flash(f'{count} held messages permanently deleted.', 'success')
        return flask.redirect(flask.url_for('.quarantine_list'))
    if flask.request.method == 'POST':
        flask.abort(400)
    return flask.render_template('quarantine/confirm_delete.html',
                                 form=form, flush=True, count=count)
