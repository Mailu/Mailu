from mailu import models
from mailu.ui import ui, forms, access, user_picker

import flask
import flask_login
import datetime


@ui.route('/manager/list/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def manager_list(domain_name):
    domain = models.db.session.get(models.Domain, domain_name) or flask.abort(404)
    return flask.render_template('manager/list.html', domain=domain)


@ui.route('/manager/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def manager_create(domain_name):
    domain = models.db.session.get(models.Domain, domain_name) or flask.abort(404)
    form = forms.ManagerForm()
    user_picker.configure(form, 'manager', 'manager', domain.name)
    if form.validate_on_submit():
        users = user_picker.selected_users(form, 'manager', 'manager', domain.name)
        if users is not None:
            existing = {user.email for user in domain.managers}
            additions = [user for user in users if user.email not in existing]
            domain.managers.extend(additions)
            models.db.session.commit()
            flask.flash(user_picker._('Added %(count)s domain managers.', count=len(additions)), 'success')
            return flask.redirect(flask.url_for('.manager_list', domain_name=domain.name))
    return flask.render_template('manager/create.html',
        domain=domain, form=form)


@ui.route('/manager/delete/<domain_name>/<path:user_email>', methods=['GET', 'POST'])
@access.confirmation_required("remove manager {user_email}")
@access.domain_admin(models.Domain, 'domain_name')
def manager_delete(domain_name, user_email):
    domain = models.db.session.get(models.Domain, domain_name) or flask.abort(404)
    user = models.db.session.get(models.User, user_email) or flask.abort(404)
    if user in domain.managers:
        domain.managers.remove(user)
        models.db.session.commit()
        flask.flash('User %s can no longer manager %s' % (user, domain))
    else:
        flask.flash('User %s is not manager' % user, 'error')
    return flask.redirect(
        flask.url_for('.manager_list', domain_name=domain_name))


@ui.route('/domain/access/list/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def domain_access_list(domain_name):
    domain = models.db.session.get(models.Domain, domain_name) or flask.abort(404)
    return flask.render_template('manager/access_list.html', domain=domain)


@ui.route('/domain/access/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def domain_access_create(domain_name):
    domain = models.db.session.get(models.Domain, domain_name) or flask.abort(404)
    # JSON API path for AJAX
    if flask.request.is_json:
        data = flask.request.get_json() or {}
        user_email = data.get('user')
        if not user_email:
            return flask.jsonify({'code':400, 'message':'Missing user email'}), 400
        user = models.db.session.get(models.User, user_email)
        if user is None:
            return flask.jsonify({'code':404, 'message':'User not found'}), 404
        existing = models.DomainAccess.query.filter_by(domain_name=domain.name, user_email=user.email).first()
        if existing:
            return flask.jsonify({'code':409, 'message':f'User {user.email} already has access to {domain.name}'}), 409
        da = models.DomainAccess(domain_name=domain.name, user_email=user.email)
        models.db.session.add(da)
        models.db.session.commit()
        return flask.jsonify({'id': da.id, 'user_email': da.user_email}), 201

    form = forms.DomainAccessForm()
    user_picker.configure(form, 'user', 'anonmail', domain.name)
    if form.validate_on_submit():
        users = user_picker.selected_users(form, 'user', 'anonmail', domain.name)
        if users is not None:
            existing = {row.user_email for row in models.DomainAccess.query.filter_by(domain_name=domain.name).filter(models.DomainAccess.user_email.in_([user.email for user in users])).all()}
            additions = [user for user in users if user.email not in existing]
            for user in additions:
                models.db.session.add(models.DomainAccess(domain_name=domain.name, user_email=user.email))
            try:
                models.db.session.commit()
            except models.sqlalchemy.exc.IntegrityError:
                models.db.session.rollback()
                flask.flash(user_picker._('Access changed while you were editing. Review the selected accounts and try again.'), 'warning')
            else:
                flask.flash(user_picker._('Granted access to %(count)s accounts.', count=len(additions)), 'success')
                return flask.redirect(flask.url_for('.domain_access_list', domain_name=domain.name))
    return flask.render_template('manager/access_create.html', domain=domain, form=form)


@ui.route('/domain/access/delete/<domain_name>/<int:access_id>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
@access.confirmation_required("revoke access for this user on {domain_name}")
def domain_access_delete(domain_name, access_id):
    domain = models.db.session.get(models.Domain, domain_name) or flask.abort(404)
    access_row = models.db.session.get(models.DomainAccess, access_id) or flask.abort(404)
    if access_row.domain_name != domain.name:
        flask.abort(403)

    # Delete the record
    models.db.session.delete(access_row)
    models.db.session.commit()
    flask.flash('Access revoked')
    return flask.redirect(flask.url_for('.domain_access_list', domain_name=domain.name))
