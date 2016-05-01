from freeposte.admin import app, db, models, forms, utils
from flask.ext import login as flask_login

import os
import flask
import wtforms_components


@app.route('/domain', methods=['GET'])
@flask_login.login_required
def domain_list():
    return flask.render_template('domain/list.html')


@app.route('/domain/create', methods=['GET', 'POST'])
@flask_login.login_required
def domain_create():
    utils.require_global_admin()
    form = forms.DomainForm()
    if form.validate_on_submit():
        if models.Domain.query.get(form.name.data):
            flask.flash('Domain %s is already used' % form.name.data, 'error')
        else:
            domain = models.Domain()
            form.populate_obj(domain)
            db.session.add(domain)
            db.session.commit()
            flask.flash('Domain %s created' % domain)
            return flask.redirect(flask.url_for('.domain_list'))
    return flask.render_template('domain/create.html', form=form)


@app.route('/domain/edit/<domain_name>', methods=['GET', 'POST'])
@flask_login.login_required
def domain_edit(domain_name):
    utils.require_global_admin()
    domain = utils.get_domain_admin(domain_name)
    form = forms.DomainForm(obj=domain)
    wtforms_components.read_only(form.name)
    if form.validate_on_submit():
        form.populate_obj(domain)
        db.session.add(domain)
        db.session.commit()
        flask.flash('Domain %s saved' % domain)
        return flask.redirect(flask.url_for('.domain_list'))
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
    return flask.redirect(flask.url_for('.domain_list'))
