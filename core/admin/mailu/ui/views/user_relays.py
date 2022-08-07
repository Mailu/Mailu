from mailu import models, utils
from mailu.ui import ui, forms, access

import flask
import flask_login
import wtforms


@ui.route('/user_relay/list', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user_relay/list/<path:user_email>', methods=['GET'])
@access.owner(models.User, 'user_email')
def user_relay_list(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    return flask.render_template('user_relay/list.html', user=user)


@ui.route('/user_relay/create', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user_relay/create/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_relay_create(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    form = forms.UserRelayForm()
    form.password.validators = [wtforms.validators.DataRequired()]
    if form.validate_on_submit():
        conflicting_relay = models.UserRelay.query.filter_by(relay_mail=form.relay_mail.data).first()
        if conflicting_relay:
            flask.flash('Relay mail %s is already used' % form.relay_mail.data, 'error')
        else:
            user_relay = models.UserRelay(user=user)
            form.populate_obj(user_relay)
            login_successful, login_message = utils.login_to_mailserver(form.host.data, form.port.data,
                                                                        form.tls.data, form.username.data,
                                                                        form.password.data)
            if login_successful:
                models.db.session.add(user_relay)
                models.db.session.commit()
                flask.flash('Login successfull. User relay configuration created')
                return flask.redirect(
                    flask.url_for('.user_relay_list', user_email=user.email))
            else:
                flask.flash('Error validating server and login: %s' % str(login_message), 'error')
    return flask.render_template('user_relay/create.html', form=form)


@ui.route('/user_relay/edit/<user_relay_id>', methods=['GET', 'POST'])
@access.owner(models.UserRelay, 'user_relay_id')
def user_relay_edit(user_relay_id):
    user_relay = models.UserRelay.query.get(user_relay_id) or flask.abort(404)
    form = forms.UserRelayForm(obj=user_relay)
    if form.validate_on_submit():
        conflicting_relay = models.UserRelay.query.filter_by(relay_mail=form.relay_mail.data).first()
        if conflicting_relay and user_relay_id != str(conflicting_relay.id):
            flask.flash('Relay mail %s is already used' % form.relay_mail.data, 'error')
        else:
            if not form.password.data:
                form.password.data = user_relay.password
            login_successful, login_message = utils.login_to_mailserver(form.host.data, form.port.data,
                                                                        form.tls.data, form.username.data,
                                                                        form.password.data)
            if login_successful:
                form.populate_obj(user_relay)
                models.db.session.commit()
                flask.flash('Login successfull. User relay configuration updated')
                return flask.redirect(
                    flask.url_for('.user_relay_list', user_email=user_relay.user.email))
            else:
                flask.flash('Error validating server and login: %s' % str(login_message), 'error')
    return flask.render_template('user_relay/edit.html',
        form=form, user_relay=user_relay)


@ui.route('/user_relay/delete/<user_relay_id>', methods=['GET', 'POST'])
@access.confirmation_required("delete a user relay account")
@access.owner(models.UserRelay, 'user_relay_id')
def user_relay_delete(user_relay_id):
    user_relay = models.UserRelay.query.get(user_relay_id) or flask.abort(404)
    user = user_relay.user
    models.db.session.delete(user_relay)
    models.db.session.commit()
    flask.flash('User relay configuration delete')
    return flask.redirect(
        flask.url_for('.user_relay_list', user_email=user.email))
