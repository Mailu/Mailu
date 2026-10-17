"""Bounded account search and shared authorization for bulk role forms."""
import flask
import flask_login
from flask_babel import gettext as _
from mailu import models
from mailu.ui import ui, access


def eligible(purpose, domain_name=None):
    actor = flask_login.current_user
    query = models.User.query
    domain = None
    if purpose == 'admin':
        if not actor.global_admin:
            flask.abort(403)
        existing = models.User.global_admin
    elif purpose in {'manager', 'anonmail'}:
        domain = models.db.session.get(models.Domain, domain_name) if domain_name else None
        if domain is None:
            flask.abort(404)
        if not actor.global_admin and domain not in actor.get_managed_domains():
            flask.abort(403)
        if purpose == 'anonmail':
            query = query.filter_by(domain_name=domain.name)
            existing = models.db.exists().where(models.DomainAccess.domain_name == domain.name, models.DomainAccess.user_email == models.User.email)
        else:
            if not actor.global_admin:
                query = query.filter(models.User.domain_name.in_([item.name for item in actor.get_managed_domains()]))
            existing = models.User.manager_of.any(models.Domain.name == domain.name)
    else:
        flask.abort(400)
    return query, existing


def label(user, already=False):
    text = user.email + (' — ' + user.displayed_name if user.displayed_name else '')
    return text + (' (' + _('Already has access') + ')' if already else '')


@ui.route('/users/options')
@access.authenticated
def user_options():
    query, existing = eligible(flask.request.args.get('purpose'), flask.request.args.get('domain'))
    term = flask.request.args.get('q', '').strip()
    if term:
        escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(models.db.or_(models.db.cast(models.User.email, models.db.String).ilike('%' + escaped + '%', escape='\\'), models.User.displayed_name.ilike('%' + escaped + '%', escape='\\')))
    rows = query.add_columns(existing.label('already')).order_by(models.User.email).limit(51).all()
    return flask.jsonify(options=[{'value': user.email, 'text': label(user, already), 'disabled': bool(already)} for user, already in rows[:50]], more=len(rows) > 50)


def configure(form, field_name, purpose, domain_name=None):
    field = getattr(form, field_name)
    query, existing = eligible(purpose, domain_name)
    selected = list(dict.fromkeys(field.data or []))
    if flask.request.method == 'POST':
        query = query.filter(models.User.email.in_(selected))
    rows = query.add_columns(existing.label('already')).order_by(models.User.email)
    if flask.request.method != 'POST':
        rows = rows.limit(50)
    field.choices = [(user.email, label(user, already), {'disabled': bool(already)}) for user, already in rows.all()]
    field.render_kw = {
        'class': 'mailu-user-picker',
        'autocomplete': 'off',
        'data-1p-ignore': 'true',
        'data-lpignore': 'true',
        'data-bwignore': 'true',
        'data-options-url': flask.url_for('ui.user_options', purpose=purpose, domain=domain_name),
        'data-placeholder': _('Search by email or name; select one or more accounts'),
        'data-no-results': _('No matching accounts'),
        'data-loading': _('Searching…'),
        'data-load-error': _('Could not load accounts. Try searching again.'),
        'data-more': _('More than 50 matches. Keep typing to narrow the search.'),
        'data-selected': _('_COUNT_ accounts selected'),
    }


def selected_users(form, field_name, purpose, domain_name=None):
    field = getattr(form, field_name)
    values = set(field.data or [])
    query, existing = eligible(purpose, domain_name)
    users = query.filter(models.User.email.in_(values)).all()
    if {user.email for user in users} != values:
        field.errors = [_("Some selected accounts are unavailable or outside your permissions.")]
        return None
    return users
