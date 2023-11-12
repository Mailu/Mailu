from mailu import models
from mailu.ui import ui, forms, access

import flask
import wtforms_components

db = models.db


@ui.route('/alias/list/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def alias_list(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
    return flask.render_template('alias/list.html', domain=domain)


@ui.route('/alias/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def alias_create(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
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
            db.session.add(alias)
            db.session.commit()
            flask.flash('Alias %s created' % alias)
            return flask.redirect(
                flask.url_for('.alias_list', domain_name=domain.name))
    return flask.render_template('alias/create.html',
        domain=domain, form=form)


@ui.route('/alias/edit/<path:alias>', methods=['GET', 'POST'])
@access.domain_admin(models.Alias, 'alias')
def alias_edit(alias):
    alias = db.get_or_404(models.Alias, alias)
    form = forms.AliasForm(obj=alias)
    wtforms_components.read_only(form.localpart)
    form.localpart.validators = []
    if form.validate_on_submit():
        form.populate_obj(alias)
        db.session.commit()
        flask.flash('Alias %s updated' % alias)
        return flask.redirect(
            flask.url_for('.alias_list', domain_name=alias.domain.name))
    return flask.render_template('alias/edit.html',
        form=form, alias=alias, domain=alias.domain)


@ui.route('/alias/delete/<path:alias>', methods=['GET', 'POST'])
@access.domain_admin(models.Alias, 'alias')
@access.confirmation_required("delete {alias}")
def alias_delete(alias):
    alias = db.get_or_404(models.Alias, alias)
    domain = alias.domain
    db.session.delete(alias)
    db.session.commit()
    flask.flash('Alias %s deleted' % alias)
    return flask.redirect(
        flask.url_for('.alias_list', domain_name=domain.name))
