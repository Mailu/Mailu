from mailu import models
from mailu.ui import ui, forms, access

import flask

db = models.db


@ui.route('/alternative/list/<domain_name>', methods=['GET'])
@access.global_admin
def alternative_list(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
    return flask.render_template('alternative/list.html', domain=domain)


@ui.route('/alternative/create/<domain_name>', methods=['GET', 'POST'])
@access.global_admin
def alternative_create(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
    form = forms.AlternativeForm()
    if form.validate_on_submit():
        conflicting_domain = db.session.get(models.Domain, form.name.data)
        conflicting_alternative = db.session.get(models.Alternative, form.name.data)
        conflicting_relay = db.session.get(models.Relay, form.name.data)
        if conflicting_domain or conflicting_alternative or conflicting_relay:
            flask.flash('Domain %s is already used' % form.name.data, 'error')
        else:
            alternative = models.Alternative(domain=domain)
            form.populate_obj(alternative)
            db.session.add(alternative)
            db.session.commit()
            flask.flash('Alternative domain %s created' % alternative)
            return flask.redirect(
                flask.url_for('.alternative_list', domain_name=domain.name))
    return flask.render_template('alternative/create.html',
        domain=domain, form=form)


@ui.route('/alternative/delete/<alternative>', methods=['GET', 'POST'])
@access.global_admin
@access.confirmation_required("delete {alternative}")
def alternative_delete(alternative):
    alternative = db.get_or_404(models.Alternative, alternative)
    domain = alternative.domain
    db.session.delete(alternative)
    db.session.commit()
    flask.flash('Alternative %s deleted' % alternative)
    return flask.redirect(
        flask.url_for('.alternative_list', domain_name=domain.name))
