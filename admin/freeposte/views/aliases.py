from freeposte import app, db, models, forms, utils
from flask.ext import login as flask_login

import os
import flask


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
        return flask.redirect(flask.url_for('alias_list', domain_name=domain.name))
    form = forms.AliasCreateForm()
    if form.validate_on_submit():
        for address in domain.users + domain.aliases:
            if address.localpart == form.localpart.data:
                flask.flash('Address %s is already used' % address, 'error')
                break
        else:
            alias = models.Alias(localpart=form.localpart.data, domain=domain)
            alias.destination = form.destination.data
            alias.comment = form.comment.data
            db.session.add(alias)
            db.session.commit()
            flask.flash('Alias %s created' % alias)
            return flask.redirect(
                flask.url_for('alias_list', domain_name=domain.name))
    return flask.render_template('alias/create.html',
        domain=domain, form=form)


@app.route('/alias/edit/<alias>', methods=['GET', 'POST'])
@flask_login.login_required
def alias_edit(alias):
    alias = utils.get_alias(alias)
    form = forms.AliasEditForm()
    if form.validate_on_submit():
        alias.destination = form.destination.data
        alias.comment = form.comment.data
        db.session.add(alias)
        db.session.commit()
        flask.flash('Alias %s updated' % alias)
        return flask.redirect(
            flask.url_for('alias_list', domain_name=alias.domain.name))
    return flask.render_template('alias/edit.html', form=form, alias=alias)


@app.route('/alias/delete/<alias>', methods=['GET'])
@flask_login.login_required
def alias_delete(alias):
    alias = utils.get_alias(alias)
    db.session.delete(alias)
    db.session.commit()
    flask.flash('Alias %s deleted' % alias)
    return flask.redirect(flask.url_for('alias_list', domain_name=alias.domain.name))
