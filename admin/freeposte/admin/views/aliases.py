from freeposte.admin import app, db, models, forms, utils

import os
import flask
import flask_login
import wtforms_components


@app.route('/alias/list/<domain_name>', methods=['GET'])
@flask_login.login_required
def alias_list(domain_name):
    domain = utils.get_domain_admin(domain_name)
    return flask.render_template('alias/list.html', domain=domain)


@app.route('/alias/create/<domain_name>', methods=['GET', 'POST'])
@flask_login.login_required
def alias_create(domain_name):
    domain = utils.get_domain_admin(domain_name)
    if domain.max_aliases and len(domain.aliases) >= domain.max_aliases:
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


@app.route('/alias/edit/<alias>', methods=['GET', 'POST'])
@flask_login.login_required
def alias_edit(alias):
    alias = utils.get_alias(alias)
    form = forms.AliasForm(obj=alias)
    wtforms_components.read_only(form.localpart)
    if form.validate_on_submit():
        form.populate_obj(alias)
        db.session.commit()
        flask.flash('Alias %s updated' % alias)
        return flask.redirect(
            flask.url_for('.alias_list', domain_name=alias.domain.name))
    return flask.render_template('alias/edit.html',
        form=form, alias=alias, domain=alias.domain)


@app.route('/alias/delete/<alias>', methods=['GET', 'POST'])
@utils.confirmation_required("delete {alias}")
@flask_login.login_required
def alias_delete(alias):
    alias = utils.get_alias(alias)
    db.session.delete(alias)
    db.session.commit()
    flask.flash('Alias %s deleted' % alias)
    return flask.redirect(
        flask.url_for('.alias_list', domain_name=alias.domain.name))
