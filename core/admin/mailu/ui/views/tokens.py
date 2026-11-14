from mailu import models, utils, oauth2
from mailu.ui import ui, forms, access

from passlib import pwd

import flask
import flask_login
import time
import wtforms_components


@ui.route('/token/list', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/token/list/<path:user_email>', methods=['GET'])
@access.owner(models.User, 'user_email')
def token_list(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    return flask.render_template('token/list.html', user=user)


@ui.route('/token/create', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/token/create/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def token_create(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    form = forms.TokenForm()
    wtforms_components.read_only(form.displayed_password)
    if not form.raw_password.data:
        form.raw_password.data = pwd.genword(entropy=128, length=32, charset="hex")
    form.displayed_password.data = form.raw_password.data
    utils.formatCSVField(form.ip)
    if form.validate_on_submit():
        token = models.Token(user=user)
        token.set_password(form.raw_password.data)
        form.populate_obj(token)
        if form.ip.data:
            token.ip = form.ip.data.replace(' ','').split(',')
        else:
            del token.ip
        models.db.session.add(token)
        models.db.session.commit()
        flask.flash('Authentication token created')
        return flask.redirect(
            flask.url_for('.token_list', user_email=user.email))
    return flask.render_template('token/create.html', form=form, user=user)


@ui.route('/token/delete/<token_id>', methods=['GET', 'POST'])
@access.confirmation_required("delete an authentication token")
@access.owner(models.Token, 'token_id')
def token_delete(token_id):
    token = models.db.session.get(models.Token, token_id) or flask.abort(404)
    user = token.user
    models.db.session.delete(token)
    models.db.session.commit()
    flask.flash('Authentication token deleted')
    return flask.redirect(
        flask.url_for('.token_list', user_email=user.email))


@ui.route('/oauth2/tokens', defaults={'user_email': None})
@ui.route('/oauth2/tokens/<path:user_email>')
@access.owner(models.User, 'user_email')
def oauth2_token_list(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    now = int(time.time())
    refresh_ttl = flask.current_app.config['OAUTH2_REFRESH_TOKEN_TTL']
    refresh_idle = flask.current_app.config['OAUTH2_REFRESH_TOKEN_IDLE']
    expired_grant_ids = set()
    for grant in user.oauth2_grants:
        if grant.refresh_expires_at is None:
            needs_reauthentication = grant.access_expires_at <= now
        else:
            last_use = grant.last_refresh_at
            if last_use is None:
                last_use = grant.refresh_expires_at - refresh_ttl
            needs_reauthentication = (
                grant.refresh_expires_at <= now
                or last_use is None
                or last_use + refresh_idle <= now
            )
        if needs_reauthentication:
            expired_grant_ids.add(grant.id)
    return flask.render_template(
        'oauth2_tokens.html',
        user=user,
        expired_grant_ids=expired_grant_ids,
        grants=sorted(user.oauth2_grants,
                      key=lambda grant: grant.last_refresh_at or 0, reverse=True),
    )


@ui.route('/oauth2/tokens/revoke/<int:grant_id>', methods=['GET', 'POST'])
@access.owner(models.OAuth2Grant, 'grant_id')
@access.confirmation_required(lambda grant_id: _oauth_revoke_confirmation(grant_id))
def oauth2_token_revoke(grant_id):
    grant = models.db.session.get(models.OAuth2Grant, grant_id) or flask.abort(404)
    user_email = grant.user.email
    models.db.session.delete(grant)
    models.db.session.commit()
    flask.flash('Mail app access revoked')
    return flask.redirect(flask.url_for('.oauth2_token_list', user_email=user_email))


@ui.route('/oauth2/tokens/reauthenticate/<int:grant_id>', methods=['GET', 'POST'])
@access.owner(models.OAuth2Grant, 'grant_id')
@access.confirmation_required(lambda grant_id: _oauth_reauthentication_confirmation(grant_id))
def oauth2_token_reauthenticate(grant_id):
    grant = models.db.session.get(models.OAuth2Grant, grant_id) or flask.abort(404)
    user_email = grant.user.email
    oauth2.force_reauthentication(
        grant,
        'administrator request',
        actor=getattr(flask_login.current_user, 'email', 'unknown'),
        peer_ip=flask.request.headers.get('X-Real-IP', flask.request.remote_addr),
    )
    models.db.session.commit()
    flask.flash('Mail app must sign in again')
    return flask.redirect(flask.url_for('.oauth2_token_list', user_email=user_email))


def _oauth_revoke_confirmation(grant_id):
    grant = models.db.session.get(models.OAuth2Grant, grant_id) or flask.abort(404)
    return utils.flask_babel.gettext(
        'revoke OAuth access for %(client)s (grant #%(grant_id)s)',
        client=grant.client_name or 'Mail app',
        grant_id=grant.id,
    )


def _oauth_reauthentication_confirmation(grant_id):
    grant = models.db.session.get(models.OAuth2Grant, grant_id) or flask.abort(404)
    return utils.flask_babel.gettext(
        'force %(client)s (grant #%(grant_id)s) to authenticate again by expiring its OAuth tokens',
        client=grant.client_name or 'Mail app',
        grant_id=grant.id,
    )
