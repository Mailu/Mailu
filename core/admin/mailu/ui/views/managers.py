from mailu import models
from mailu.ui import ui, forms, access

import flask
import flask_login
import datetime


@ui.route('/manager/list/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def manager_list(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.render_template('manager/list.html', domain=domain)


@ui.route('/manager/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def manager_create(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    form = forms.ManagerForm()
    available_users = flask_login.current_user.get_managed_emails(
        include_aliases=False)
    form.manager.choices = [
        (user.email, user.email) for user in available_users
    ]
    if form.validate_on_submit():
        user = models.User.query.get(form.manager.data)
        if user.email not in [user.email for user in available_users]:
            flask.abort(403)
        elif user in domain.managers:
            flask.flash('User %s is already manager' % user, 'error')
        else:
            domain.managers.append(user)
            models.db.session.commit()
            flask.flash('User %s can now manage %s' % (user, domain.name))
            return flask.redirect(
                flask.url_for('.manager_list', domain_name=domain.name))
    return flask.render_template('manager/create.html',
        domain=domain, form=form)


@ui.route('/manager/delete/<domain_name>/<path:user_email>', methods=['GET', 'POST'])
@access.confirmation_required("remove manager {user_email}")
@access.domain_admin(models.Domain, 'domain_name')
def manager_delete(domain_name, user_email):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    user = models.User.query.get(user_email) or flask.abort(404)
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
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.render_template('manager/access_list.html', domain=domain)


@ui.route('/domain/access/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def domain_access_create(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    # JSON API path for AJAX
    if flask.request.is_json:
        data = flask.request.get_json() or {}
        user_email = data.get('user')
        if not user_email:
            return flask.jsonify({'code':400, 'message':'Missing user email'}), 400
        user = models.User.query.get(user_email)
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
    # Offer users from the domain as choices
    users = domain.users
    form.user.choices = [(u.email, u.email) for u in users]
    if form.validate_on_submit():
        user = models.User.query.get(form.user.data)
        if user is None:
            flask.abort(404)
        # ensure not duplicate
        existing = models.DomainAccess.query.filter_by(domain_name=domain.name, user_email=user.email).first()
        if existing:
            flask.flash('User %s already has access to %s' % (user, domain.name), 'error')
        else:
            da = models.DomainAccess(domain_name=domain.name, user_email=user.email)
            models.db.session.add(da)
            models.db.session.commit()
            flask.flash('User %s granted anonmail access for %s' % (user, domain.name))
            return flask.redirect(flask.url_for('.domain_access_list', domain_name=domain.name))
    return flask.render_template('manager/access_create.html', domain=domain, form=form)


@ui.route('/domain/access/delete/<domain_name>/<int:access_id>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
@access.confirmation_required("revoke access for this user on {domain_name}")
def domain_access_delete(domain_name, access_id):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    access_row = models.DomainAccess.query.get(access_id) or flask.abort(404)
    if access_row.domain_name != domain.name:
        flask.abort(403)

    # Delete the record
    models.db.session.delete(access_row)
    models.db.session.commit()
    flask.flash('Access revoked')
    return flask.redirect(flask.url_for('.domain_access_list', domain_name=domain.name))
