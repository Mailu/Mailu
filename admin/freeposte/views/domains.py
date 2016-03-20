from freeposte import app, db, models, forms, utils
from flask.ext import login as flask_login

import os
import flask


@app.route('/domain', methods=['GET'])
@flask_login.login_required
def domain_list():
    return flask.render_template('domain/list.html')


@app.route('/domain/create', methods=['GET', 'POST'])
@flask_login.login_required
def domain_create():
    utils.require_global_admin()
    form = forms.DomainCreateForm()
    if form.validate_on_submit():
        if models.Domain.query.filter_by(name=form.name.data).first():
            flask.flash('Domain %s is already used' % form.name.data, 'error')
        else:
            domain = models.Domain(name=form.name.data)
            db.session.add(domain)
            db.session.commit()
            flask.flash('Domain %s created' % domain)
            return flask.redirect(flask.url_for('domain_list'))
    return flask.render_template('domain/create.html', form=form)


@app.route('/domain/edit/<domain_name>', methods=['GET', 'POST'])
@flask_login.login_required
def domain_edit(domain_name):
    utils.require_global_admin()
    domain = utils.get_domain_admin(domain_name)
    form = forms.DomainEditForm(obj=domain)
    if form.validate_on_submit():
        domain.max_users = form.max_users.data
        domain.max_aliases = form.max_aliases.data
        db.session.add(domain)
        db.session.commit()
        flask.flash('Domain %s saved' % domain)
        return flask.redirect(flask.url_for('domain_list'))
    return flask.render_template('domain/edit.html', form=form,
        domain=domain)


@app.route('/domain/delete/<domain_name>', methods=['GET'])
@flask_login.login_required
def domain_delete(domain_name):
    utils.require_global_admin()
    domain = utils.get_domain_admin(domain_name)
    db.session.delete(domain)
    db.session.commit()
    flask.flash('Domain %s deleted' % domain)
    return flask.redirect(flask.url_for('domain_list'))


@app.route('/domain/admins/<domain_name>', methods=['GET'])
@flask_login.login_required
def domain_admins(domain_name):
    domain = utils.get_domain_admin(domain_name)
