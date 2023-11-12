from mailu import models
from mailu.ui import ui, forms, access

import flask
import wtforms_components

db = models.db


@ui.route('/relay', methods=['GET'])
@access.global_admin
def relay_list():
    relays = db.session.scalars(db.select(models.Relay)).all()
    return flask.render_template('relay/list.html', relays=relays)


@ui.route('/relay/create', methods=['GET', 'POST'])
@access.global_admin
def relay_create():
    form = forms.RelayForm()
    if form.validate_on_submit():
        conflicting_domain = db.session.get(models.Domain, form.name.data)
        conflicting_alternative = db.session.get(models.Alternative, form.name.data)
        conflicting_relay = db.session.get(models.Relay, form.name.data)
        if conflicting_domain or conflicting_alternative or conflicting_relay:
            flask.flash('Domain %s is already used' % form.name.data, 'error')
        else:
            relay = models.Relay()
            form.populate_obj(relay)
            db.session.add(relay)
            db.session.commit()
            flask.flash('Relayed domain %s created' % relay)
            return flask.redirect(flask.url_for('.relay_list'))
    return flask.render_template('relay/create.html', form=form)


@ui.route('/relay/edit/<relay_name>', methods=['GET', 'POST'])
@access.global_admin
def relay_edit(relay_name):
    relay = db.get_or_404(models.Relay, relay_name)
    form = forms.RelayForm(obj=relay)
    wtforms_components.read_only(form.name)
    form.name.validators = []
    if form.validate_on_submit():
        form.populate_obj(relay)
        db.session.commit()
        flask.flash('Relayed domain %s saved' % relay)
        return flask.redirect(flask.url_for('.relay_list'))
    return flask.render_template('relay/edit.html', form=form,
        relay=relay)


@ui.route('/relay/delete/<relay_name>', methods=['GET', 'POST'])
@access.global_admin
@access.confirmation_required("delete {relay_name}")
def relay_delete(relay_name):
    relay = db.get_or_404(models.Relay, relay_name)
    db.session.delete(relay)
    db.session.commit()
    flask.flash('Relayed domain %s deleted' % relay)
    return flask.redirect(flask.url_for('.relay_list'))

