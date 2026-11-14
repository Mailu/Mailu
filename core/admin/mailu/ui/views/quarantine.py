import math
import smtplib

import flask
import flask_login
from flask import current_app as app

from mailu import greylist, quarantine, utils
from mailu.ui import access, forms, ui


QUARANTINE_REINJECTION_PORT = 10026


def _visible(metadata, user):
    return bool(_visible_recipients(metadata, user))


def _visible_recipients(metadata, user):
    return quarantine.visible_recipients(metadata, user)


def _release_recipients(metadata, user):
    if user.global_admin:
        # Preserve the original SMTP route so Postfix can apply aliases,
        # forwarding and relayed-domain transports again.
        recipients = metadata.get('envelope_recipients') or metadata.get('recipients', [])
        if isinstance(recipients, str):
            recipients = [recipients]
        if not isinstance(recipients, list):
            recipients = []
        recipients = [address.strip() for address in recipients
                      if isinstance(address, str) and utils.is_valid_email(address.strip())]
    else:
        recipients = [address for address in _visible_recipients(metadata, user)
                      if utils.is_valid_email(address)]
    if not any(address.lower() == user.email.lower() for address in metadata.get('recipients', [])
               if isinstance(address, str)):
        recipients.append(user.email)
    return list(dict.fromkeys(recipients))


def _release_sender(metadata):
    """Return the captured SMTP envelope sender, including the null sender."""
    sender = metadata.get('from') or metadata.get('sender') or ''
    if sender in ('', '<>'):
        return ''
    if not isinstance(sender, str) or not utils.is_valid_email(sender):
        flask.abort(400)
    return sender


def _reinject(raw_message, metadata, recipients, record_id, message_type):
    """Put a learned message back into Postfix without invoking Rspamd again."""
    sender = _release_sender(metadata)
    try:
        with smtplib.SMTP(host=app.config.get('SMTP_ADDRESS', 'smtp'),
                          port=QUARANTINE_REINJECTION_PORT, timeout=10) as smtp:
            refused = smtp.sendmail(sender, recipients, raw_message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
    except (smtplib.SMTPException, OSError):
        app.logger.exception('%s release failed for %s', message_type, record_id)
        flask.abort(503)


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
    if not selected or any(recipient not in recipients or not utils.is_valid_email(recipient)
                           for recipient in selected):
        flask.abort(400)
    learning_failures = quarantine.learn_ham(path.read_bytes())
    _reinject(path.read_bytes(), metadata, selected, message_id, 'Quarantine')
    quarantine.delete(message_id)
    if learning_failures:
        reason = '; '.join(learning_failures)
        app.logger.warning('Rspamd ham learning failed for quarantine message %s: %s',
                           message_id, reason)
        flask.flash(f'Message re-injected, but Rspamd ham learning failed ({reason}).', 'warning')
    else:
        flask.flash('Message re-injected into Mailu and learned as ham.', 'success')
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
    if not selected or any(recipient not in recipients or not utils.is_valid_email(recipient)
                           for recipient in selected):
        flask.abort(400)
    raw_message = path.read_bytes()
    learning_failures = quarantine.learn_ham(raw_message)
    _reinject(raw_message, metadata, selected, record_id, 'Greylisted message')
    greylist.delete(record_id)
    if learning_failures:
        reason = '; '.join(learning_failures)
        app.logger.warning('Rspamd ham learning failed for released greylisted message %s: %s',
                           record_id, reason)
        flask.flash(f'Message re-injected, but Rspamd ham learning failed ({reason}).', 'warning')
    else:
        flask.flash('Message re-injected into Mailu and learned as ham.', 'success')
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
