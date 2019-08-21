from mailu import models
from mailu.ui import ui, forms, access

import flask
import flask_login


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
