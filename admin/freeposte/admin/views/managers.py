from freeposte.admin import app, db, models, forms, utils

import os
import flask
import flask_login
import wtforms_components


@app.route('/manager/list/<domain_name>', methods=['GET'])
@flask_login.login_required
def manager_list(domain_name):
    domain = utils.get_domain_admin(domain_name)
    return flask.render_template('manager/list.html', domain=domain)


@app.route('/manager/create/<domain_name>', methods=['GET', 'POST'])
@flask_login.login_required
def manager_create(domain_name):
    domain = utils.get_domain_admin(domain_name)
    form = forms.ManagerForm()
    form.manager.choices = [
        (user.email, user.email) for user in
        flask_login.current_user.get_managed_emails(include_aliases=False)
    ]
    if form.validate_on_submit():
        user = utils.get_user(form.manager.data, admin=True)
        if user in domain.managers:
            flask.flash('User %s is already manager' % user, 'error')
        else:
            domain.managers.append(user)
            db.session.commit()
            flask.flash('User %s can now manage %s' % (user, domain.name))
            return flask.redirect(
                flask.url_for('.manager_list', domain_name=domain.name))
    return flask.render_template('manager/create.html',
        domain=domain, form=form)


@app.route('/manager/delete/<manager>', methods=['GET'])
@flask_login.login_required
def manager_delete(manager):
    user = utils.get_user(manager, admin=True)
    domain = utils.get_domain_admin(user.domain_name)
    if user in domain.managers:
        domain.managers.remove(user)
        db.session.commit()
        flask.flash('User %s can no longer manager %s' % (user, domain))
    else:
        flask.flash('User %s is not manager' % user, 'error')
    return flask.redirect(
        flask.url_for('.manager_list', domain_name=domain.name))
