from mailu import models
from mailu.ui import ui, forms, access

import flask
import wtforms_components


@ui.route('/relay', methods=['GET'])
@access.global_admin
def relay_list():
    relays = models.Relay.query.all()
    return flask.render_template('relay/list.html', relays=relays)


@ui.route('/relay/create', methods=['GET', 'POST'])
@access.global_admin
def relay_create():
    form = forms.RelayForm()
    if form.validate_on_submit():
        conflicting_domain = models.Domain.query.get(form.name.data)
        conflicting_alternative = models.Alternative.query.get(form.name.data)
        conflicting_relay = models.Relay.query.get(form.name.data)
        if conflicting_domain or conflicting_alternative or conflicting_relay:
            flask.flash('Domain %s is already used' % form.name.data, 'error')
        else:
            relay = models.Relay()
            form.populate_obj(relay)
            models.db.session.add(relay)
            models.db.session.commit()
            flask.flash('Relayed domain %s created' % relay)
            return flask.redirect(flask.url_for('.relay_list'))
    return flask.render_template('relay/create.html', form=form)


@ui.route('/relay/edit/<relay_name>', methods=['GET', 'POST'])
@access.global_admin
def relay_edit(relay_name):
    relay = models.Relay.query.get(relay_name) or flask.abort(404)
    form = forms.RelayForm(obj=relay)
    wtforms_components.read_only(form.name)
    form.name.validators = []
    if form.validate_on_submit():
        form.populate_obj(relay)
        models.db.session.commit()
        flask.flash('Relayed domain %s saved' % relay)
        return flask.redirect(flask.url_for('.relay_list'))
    return flask.render_template('relay/edit.html', form=form,
        relay=relay)


@ui.route('/relay/delete/<relay_name>', methods=['GET', 'POST'])
@access.global_admin
@access.confirmation_required("delete {relay_name}")
def relay_delete(relay_name):
    relay = models.Relay.query.get(relay_name) or flask.abort(404)
    models.db.session.delete(relay)
    models.db.session.commit()
    flask.flash('Relayed domain %s deleted' % relay)
    return flask.redirect(flask.url_for('.relay_list'))

