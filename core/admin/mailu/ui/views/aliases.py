from mailu import models, utils
from mailu.ui import ui, forms, access
from flask import current_app as app

import flask
import flask_login
import validators
import wtforms_components


@ui.route('/alias/list/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def alias_list(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.render_template('alias/list.html', domain=domain)


@ui.route('/alias/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def alias_create(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    if not domain.max_aliases == -1 and len(domain.aliases) >= domain.max_aliases:
        flask.flash('Too many aliases for domain %s' % domain, 'error')
        return flask.redirect(
            flask.url_for('.alias_list', domain_name=domain.name))
    form = forms.AliasForm()
    if form.validate_on_submit():
        if domain.has_email(form.localpart.data):
            flask.flash('Email is already used', 'error')
        else:
            alias = models.Alias(domain=domain)
            form.populate_obj(alias)
            models.db.session.add(alias)
            models.db.session.commit()
            flask.flash('Alias %s created' % alias)
            return flask.redirect(
                flask.url_for('.alias_list', domain_name=domain.name))
    return flask.render_template('alias/create.html',
        domain=domain, form=form)


@ui.route('/alias/edit/<path:alias>', methods=['GET', 'POST'])
@access.domain_admin(models.Alias, 'alias')
def alias_edit(alias):
    alias = models.Alias.query.get(alias) or flask.abort(404)
    form = forms.AliasForm(obj=alias)
    wtforms_components.read_only(form.localpart)
    form.localpart.validators = []
    if form.validate_on_submit():
        form.populate_obj(alias)
        models.db.session.commit()
        flask.flash('Alias %s updated' % alias)
        return flask.redirect(
            flask.url_for('.alias_list', domain_name=alias.domain.name))
    return flask.render_template('alias/edit.html',
        form=form, alias=alias, domain=alias.domain)


@ui.route('/alias/delete/<path:alias>', methods=['GET', 'POST'])
@access.domain_admin(models.Alias, 'alias')
@access.confirmation_required("delete {alias}")
def alias_delete(alias):
    alias = models.Alias.query.get(alias) or flask.abort(404)
    domain = alias.domain
    models.db.session.delete(alias)
    models.db.session.commit()
    flask.flash('Alias %s deleted' % alias)
    return flask.redirect(
        flask.url_for('.alias_list', domain_name=domain.name))


@ui.route('/anonalias/list', methods=['GET'])
@access.authenticated
def anonalias_list():
    # Renders the Anonymous Aliases UI
    user = flask_login.current_user
    has_access = user.global_admin
    if not has_access:
        for d in models.Domain.query.all():
            if models.has_domain_access(d.name, user=user) or (d.anonmail_enabled and user.domain and d.name == user.domain.name):
                has_access = True
                break
    
    # Query user's anonymous aliases
    aliases = models.Alias.query.filter_by(owner_email=user.email).all()
    
    return flask.render_template('alias/anonaliases.html', has_access=has_access, aliases=aliases)


@ui.route('/anonalias/create', methods=['GET', 'POST'])
@access.authenticated
def anonalias_create():
    user = flask_login.current_user
    form = forms.AnonymousAliasForm()
    
    # Populate domain choices
    available_domains = []
    for d in models.Domain.query.all():
        if user.global_admin or models.has_domain_access(d.name, user=user) or (d.anonmail_enabled and user.domain and d.name == user.domain.name):
            available_domains.append((d.name, d.name))
    
    form.domain.choices = available_domains
    
    if not available_domains:
        flask.flash('You do not have access to any domains for creating anonymous aliases.', 'error')
        return flask.redirect(flask.url_for('.anonalias_list'))
    
    if form.validate_on_submit():
        domain_name = form.domain.data
        hostname = form.hostname.data
        note = form.note.data
        
        # determine destinations (default to user email)
        destination = [user.email]
        
        # generate alias
        max_retries = app.config.get('ANONMAIL_MAX_RETRIES', 10)
        
        localpart = None
        for _ in range(max_retries):
            candidate = utils.generate_anonymous_alias_localpart(hostname=hostname, mode='word')
            email_candidate = f"{candidate}@{domain_name}"
            if not models.Alias.query.filter_by(email=email_candidate).first() and not models.User.query.filter_by(email=email_candidate).first():
                localpart = candidate
                break
        
        if not localpart:
            flask.flash('Unable to find a unique alias after several retries', 'error')
            return flask.redirect(flask.url_for('.anonalias_create'))

        alias_email = f"{localpart}@{domain_name}"
        alias_model = models.Alias(email=alias_email, destination=destination)
        alias_model.comment = note or f'Generated by UI for {user.email}'
        alias_model.hostname = hostname or ""
        alias_model.owner_email = user.email
        
        models.db.session.add(alias_model)
        models.db.session.commit()
        
        flask.flash(f'Created alias {alias_email}')
        return flask.redirect(flask.url_for('.anonalias_list'))

    return flask.render_template('alias/anonaliases_create.html', form=form)


@ui.route('/anonalias/delete/<string:alias_email>', methods=['GET', 'POST'])
@access.authenticated
@access.confirmation_required("delete alias {alias_email}")
def anonalias_delete(alias_email):
    user = flask_login.current_user
    alias_found = models.Alias.query.filter_by(email=alias_email, owner_email=user.email).first()
    if not alias_found:
        flask.abort(404)
    
    models.db.session.delete(alias_found)
    models.db.session.commit()
    flask.flash(f"Alias {alias_email} deleted")
    return flask.redirect(flask.url_for('.anonalias_list'))


@ui.route('/anonalias/enable/<string:alias_email>', methods=['GET', 'POST'])
@access.authenticated
@access.confirmation_required("enable alias {alias_email}")
def anonalias_enable(alias_email):
    user = flask_login.current_user
    alias_found = models.Alias.query.filter_by(email=alias_email, owner_email=user.email).first()
    if not alias_found:
        flask.abort(404)
    
    alias_found.disabled = False
    models.db.session.commit()
    flask.flash(f"Alias {alias_email} enabled")
    return flask.redirect(flask.url_for('.anonalias_list'))


@ui.route('/anonalias/disable/<string:alias_email>', methods=['GET', 'POST'])
@access.authenticated
@access.confirmation_required("disable alias {alias_email}")
def anonalias_disable(alias_email):
    user = flask_login.current_user
    alias_found = models.Alias.query.filter_by(email=alias_email, owner_email=user.email).first()
    if not alias_found:
        flask.abort(404)
    
    alias_found.disabled = True
    models.db.session.commit()
    flask.flash(f"Alias {alias_email} disabled")
    return flask.redirect(flask.url_for('.anonalias_list'))


@ui.route('/anonalias/generate', methods=['POST'])
@access.authenticated
def alias_generate():
    """Generate an anonmail alias on behalf of the logged-in user (session-based).
    This avoids requiring a token in the browser UI and respects per-user domain grants.
    """
    user = flask_login.current_user
    data = flask.request.get_json() or {}
    domain_name = data.get('domain')
    hostname = data.get('hostname')
    note = data.get('note')
    destination = data.get('destination')

    if not domain_name or not validators.domain(domain_name):
        return flask.jsonify({'code': 400, 'message': 'A valid domain must be provided'}), 400
    domain_found = models.Domain.query.get(domain_name)
    if not domain_found:
        return flask.jsonify({'code': 404, 'message': f'Domain {domain_name} does not exist'}), 404

    # permission check: user-level
    # A user has access if:
    # 1. They are a global admin
    # 2. They have explicit access (DomainAccess or manager)
    # 3. The domain is enabled AND they belong to it
    if not (user.global_admin or models.has_domain_access(domain_name, user=user) or (domain_found.anonmail_enabled and user.domain and domain_name == user.domain.name)):
        return flask.jsonify({'code': 403, 'message': f'You do not have access to domain {domain_name}'}), 403

    # determine destinations (default to user email)
    if not destination:
        destination = [user.email]
    elif isinstance(destination, str):
        destination = [destination]

    for dest in destination:
        if not validators.email(dest):
            return flask.jsonify({'code': 400, 'message': f'Provided destination email address {dest} is not a valid email address'}), 400
        elif models.User.query.filter_by(email=dest).first() is None:
            return flask.jsonify({'code': 404, 'message': f'Provided destination email address {dest} does not exist'}), 404

    # generate alias
    max_retries = app.config.get('ANONMAIL_MAX_RETRIES', 10)
    
    localpart = None
    for _ in range(max_retries):
        candidate = utils.generate_anonymous_alias_localpart(hostname=hostname, mode='word')
        email_candidate = f"{candidate}@{domain_name}"
        if not models.Alias.query.filter_by(email=email_candidate).first() and not models.User.query.filter_by(email=email_candidate).first():
            localpart = candidate
            break
    if not localpart:
        return flask.jsonify({'code': 409, 'message': 'Unable to find a unique alias after several retries'}), 409

    alias_email = f"{localpart}@{domain_name}"
    alias_model = models.Alias(email=alias_email, destination=destination)
    alias_model.comment = note or f'Generated by UI for {user.email}'
    alias_model.hostname = hostname or ""
    alias_model.owner_email = user.email
    db = models.db
    db.session.add(alias_model)
    db.session.commit()

    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    app.logger.info(f'Anonmail UI alias created user={user.email} alias={alias_email} domain={domain_name} ip={client_ip} hostname={hostname!r}')

    return flask.jsonify({'code': 201, 'alias': alias_email, 'note': alias_model.comment, 'hostname': alias_model.hostname}), 201
