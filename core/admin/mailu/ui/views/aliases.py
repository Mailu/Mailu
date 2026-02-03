from mailu import models, utils
from mailu.ui import ui, forms, access
from flask import current_app as app

import flask
import flask_login
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
    user = flask_login.current_user
    has_access = user.global_admin
    if not has_access:
        for d in models.Domain.query.all():
            if models.has_domain_access(d.name, user=user) or (d.anonmail_enabled and user.domain and d.name == user.domain.name):
                has_access = True
                break
    
    # Query user's anonymous aliases, standard aliases do not have an owner_email
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
        destination = [user.email]
        max_retries = app.config.get('ANONMAIL_MAX_RETRIES', 10)
        
        localpart = None
        for _ in range(max_retries):
            candidate = utils.generate_anonymous_alias_localpart(hostname=hostname)
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
