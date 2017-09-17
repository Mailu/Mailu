from mailu.admin import app, db, models, forms, access
from mailu import app as flask_app

import flask
import wtforms_components


@app.route('/domain', methods=['GET'])
@access.authenticated
def domain_list():
    return flask.render_template('domain/list.html')


@app.route('/domain/create', methods=['GET', 'POST'])
@access.global_admin
def domain_create():
    form = forms.DomainForm()
    if form.validate_on_submit():
        conflicting_domain = models.Domain.query.get(form.name.data)
        conflicting_alternative = models.Alternative.query.get(form.name.data)
        conflicting_relay = models.Relay.query.get(form.name.data)
        if conflicting_domain or conflicting_alternative or conflicting_relay:
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
@access.global_admin
def domain_edit(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    form = forms.DomainForm(obj=domain)
    wtforms_components.read_only(form.name)
    form.name.validators = []
    if form.validate_on_submit():
        form.populate_obj(domain)
        db.session.commit()
        flask.flash('Domain %s saved' % domain)
        return flask.redirect(flask.url_for('.domain_list'))
    return flask.render_template('domain/edit.html', form=form,
        domain=domain)


@app.route('/domain/delete/<domain_name>', methods=['GET', 'POST'])
@access.global_admin
@access.confirmation_required("delete {domain_name}")
def domain_delete(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    db.session.delete(domain)
    db.session.commit()
    flask.flash('Domain %s deleted' % domain)
    return flask.redirect(flask.url_for('.domain_list'))


@app.route('/domain/details/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def domain_details(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.render_template('domain/details.html', domain=domain,
        config=flask_app.config)


@app.route('/domain/genkeys/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
@access.confirmation_required("regenerate keys for {domain_name}")
def domain_genkeys(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    domain.generate_dkim_key()
    return flask.redirect(
        flask.url_for(".domain_details", domain_name=domain_name))
