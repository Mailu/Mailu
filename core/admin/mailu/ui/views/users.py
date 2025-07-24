from mailu import models, utils
from mailu.ui import ui, access, forms
from mailu.utils import avatar
from flask import current_app as app

import flask
import flask_login
import wtforms
import wtforms_components
import tempfile
import os
from werkzeug.utils import secure_filename

@ui.route('/user/list/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def user_list(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.render_template('user/list.html', domain=domain)


@ui.route('/user/create/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
def user_create(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    if not domain.max_users == -1 and len(domain.users) >= domain.max_users:
        flask.flash('Too many users for domain %s' % domain, 'error')
        return flask.redirect(
            flask.url_for('.user_list', domain_name=domain.name))
    form = forms.UserForm()
    form.pw.validators = [wtforms.validators.DataRequired()]
    form.quota_bytes.default = int(app.config['DEFAULT_QUOTA'])
    if domain.max_quota_bytes:
        form.quota_bytes.validators = [
            wtforms.validators.NumberRange(max=domain.max_quota_bytes)]
        if form.quota_bytes.default > domain.max_quota_bytes:
            form.quota_bytes.default = domain.max_quota_bytes
    if form.validate_on_submit():
        if msg := utils.isBadOrPwned(form):
            flask.flash(msg, "error")
            return flask.render_template('user/create.html',
                domain=domain, form=form)
        if domain.has_email(form.localpart.data):
            flask.flash('Email is already used', 'error')
        else:
            user = models.User(domain=domain)
            form.populate_obj(user)
            user.set_password(form.pw.data)
            models.db.session.add(user)
            models.db.session.commit()
            user.send_welcome()
            flask.flash('User %s created' % user)
            return flask.redirect(
                flask.url_for('.user_list', domain_name=domain.name))
    form.process()
    return flask.render_template('user/create.html',
        domain=domain, form=form)


@ui.route('/user/edit/<path:user_email>', methods=['GET', 'POST'])
@access.domain_admin(models.User, 'user_email')
def user_edit(user_email):
    user = models.User.query.get(user_email) or flask.abort(404)
    # Handle the case where user quota is more than allowed
    max_quota_bytes = user.domain.max_quota_bytes
    if max_quota_bytes and user.quota_bytes > max_quota_bytes:
        max_quota_bytes = user.quota_bytes
    # Create the form
    form = forms.UserForm(obj=user)
    wtforms_components.read_only(form.localpart)
    form.localpart.validators = []
    if max_quota_bytes:
        form.quota_bytes.validators = [
            wtforms.validators.NumberRange(max=max_quota_bytes)]
    if form.validate_on_submit():
        if form.pw.data:
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
                return flask.render_template('user/edit.html', form=form, user=user,
                    domain=user.domain, max_quota_bytes=max_quota_bytes)
        form.populate_obj(user)
        if form.pw.data:
            user.set_password(form.pw.data, keep_sessions=set(flask.session))
        models.db.session.commit()
        flask.flash('User %s updated' % user)
        return flask.redirect(
            flask.url_for('.user_list', domain_name=user.domain.name))
    return flask.render_template('user/edit.html', form=form, user=user,
        domain=user.domain, max_quota_bytes=max_quota_bytes)


@ui.route('/user/settings', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user/usersettings/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_settings(user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email_or_current) or flask.abort(404)
    form = forms.UserSettingsForm(obj=user)
    utils.formatCSVField(form.forward_destination)
    if form.validate_on_submit():
        user.forward_enabled = bool(flask.request.form.get('forward_enabled', False))
        if user.forward_enabled and not form.forward_destination.data:
            flask.flash('Destination email address is missing', 'error')
            return flask.redirect(
                flask.url_for('.user_settings', user_email=user_email))
        form.forward_destination.data = form.forward_destination.data.replace(" ","").split(",")
        form.populate_obj(user)
        models.db.session.commit()
        form.forward_destination.data = ", ".join(form.forward_destination.data)
        flask.flash('Settings updated for %s' % user)
        if user_email:
            return flask.redirect(
                flask.url_for('.user_list', domain_name=user.domain.name))
    elif form.is_submitted() and not form.validate():
            flask.flash('Error validating the form', 'error')
            return flask.redirect(
                flask.url_for('.user_settings', user_email=user_email))
    return flask.render_template('user/settings.html', form=form, user=user)

def _process_password_change(form, user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email_or_current) or flask.abort(404)
    if form.validate_on_submit():
        if form.pw.data != form.pw2.data:
            flask.flash('Passwords do not match', 'error')
        elif user_email or models.User.login(user_email_or_current, form.current_pw.data):
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
                return flask.render_template('user/password.html', form=form, user=user)
            flask.session.regenerate()
            user.set_password(form.pw.data, keep_sessions=set(flask.session))
            models.db.session.commit()
            flask.flash('Password updated for %s' % user)
            if user_email:
                return flask.redirect(flask.url_for('.user_list',
                    domain_name=user.domain.name))
        else:
            flask.flash('Wrong current password', 'error')
    return flask.render_template('user/password.html', form=form, user=user)

@ui.route('/user/password', methods=['GET', 'POST'], defaults={'user_email': None})
@access.owner(models.User, 'user_email')
def user_password_change(user_email):
    return _process_password_change(forms.UserPasswordChangeForm(), user_email)

@ui.route('/user/password/<path:user_email>', methods=['GET', 'POST'])
@access.domain_admin(models.User, 'user_email')
def user_password(user_email):
    return _process_password_change(forms.UserPasswordForm(), user_email)

@ui.route('/user/reply', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user/reply/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_reply(user_email):
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email_or_current) or flask.abort(404)
    form = forms.UserReplyForm(obj=user)
    if form.validate_on_submit():
        form.populate_obj(user)
        models.db.session.commit()
        flask.flash('Auto-reply message updated for %s' % user)
        if user_email:
            return flask.redirect(
                flask.url_for('.user_list', domain_name=user.domain.name))
    return flask.render_template('user/reply.html', form=form, user=user)


@ui.route('/user/signup', methods=['GET', 'POST'])
@ui.route('/user/signup/<domain_name>', methods=['GET', 'POST'])
def user_signup(domain_name=None):
    available_domains = {
        domain.name: domain
        for domain in models.Domain.query.filter_by(signup_enabled=True).all()
        if domain.max_users == -1 or len(domain.users) < domain.max_users
    }
    if not available_domains:
        flask.flash('No domain available for registration')
    if not domain_name:
        return flask.render_template('user/signup_domain.html',
            available_domains=available_domains)
    domain = available_domains.get(domain_name) or flask.abort(404)
    quota_bytes = domain.max_quota_bytes or app.config['DEFAULT_QUOTA']
    if app.config['RECAPTCHA_PUBLIC_KEY'] == "" or app.config['RECAPTCHA_PRIVATE_KEY'] == "":
        form = forms.UserSignupForm()
    else:
        form = forms.UserSignupFormCaptcha()

    if form.validate_on_submit():
        if domain.has_email(form.localpart.data) or models.Alias.resolve(form.localpart.data, domain_name):
            flask.flash('Email is already used', 'error')
        else:
            if msg := utils.isBadOrPwned(form):
                flask.flash(msg, "error")
                return flask.render_template('user/signup.html', domain=domain, form=form)
            flask.session.regenerate()
            user = models.User(domain=domain)
            form.populate_obj(user)
            user.change_pw_next_login = True
            user.set_password(form.pw.data)
            user.quota_bytes = quota_bytes
            models.db.session.add(user)
            models.db.session.commit()
            user.send_welcome()
            flask.flash('Successfully signed up %s' % user)
            return flask.redirect(flask.url_for('.index'))
    return flask.render_template('user/signup.html', domain=domain, form=form)


@ui.route('/user/avatar', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/user/avatar/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def user_avatar(user_email):
    """ Handle user avatar upload and display """
    user_email_or_current = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email_or_current) or flask.abort(404)
    
    upload_form = forms.UserAvatarForm()
    delete_form = forms.UserAvatarDeleteForm()
    
    if upload_form.validate_on_submit() and upload_form.avatar.data:
        file = upload_form.avatar.data
        
        if not avatar.allowed_file(file.filename):
            flask.flash('Invalid file type. Allowed: PNG, JPG, JPEG, WebP', 'error')
        else:
            # Save to temporary file for validation
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            file.save(temp_file.name)
            
            try:
                # Validate the uploaded file
                is_valid, error_msg = avatar.validate_image_file(temp_file.name)
                if not is_valid:
                    flask.flash(error_msg, 'error')
                else:
                    # Generate filename and storage path
                    storage_path = avatar.get_avatar_storage_path()
                    avatar_filename = avatar.generate_avatar_filename(user.email, file.filename)
                    avatar_path = os.path.join(storage_path, avatar_filename)
                    
                    # Process and save avatar
                    success, error_msg = avatar.process_avatar_image(temp_file.name, avatar_path)
                    if success:
                        # Delete old avatar if exists
                        if user.avatar_filename:
                            user.delete_avatar()
                        
                        # Update user record
                        user.avatar_filename = avatar_filename
                        models.db.session.commit()
                        flask.flash('Avatar uploaded successfully', 'success')
                    else:
                        flask.flash(error_msg, 'error')
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass
    
    elif delete_form.validate_on_submit():
        if user.avatar_filename:
            user.delete_avatar()
            models.db.session.commit()
            flask.flash('Avatar deleted successfully', 'success')
        else:
            flask.flash('No avatar to delete', 'warning')
    
    # Get avatar info for display
    avatar_info = avatar.get_avatar_info(user)
    
    return flask.render_template('user/avatar.html', 
                               user=user, 
                               upload_form=upload_form,
                               delete_form=delete_form,
                               avatar_info=avatar_info)


@ui.route('/user/<path:user_email>/avatar/image')
def user_avatar_image(user_email):
    """ Serve user avatar image """
    user = models.User.query.get(user_email) or flask.abort(404)
    
    # Check if user has uploaded avatar
    if user.avatar_filename:
        avatar_path = user.avatar_path
        if avatar_path and os.path.exists(avatar_path):
            return flask.send_file(avatar_path, mimetype='image/jpeg')
    
    # Generate initials-based avatar
    initials = user.get_avatar_initials()
    avatar_img = avatar.generate_initials_avatar(initials)
    
    # Save to temporary file and return
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    avatar_img.save(temp_file.name, 'PNG')
    temp_file.close()
    
    def cleanup_temp_file():
        try:
            os.unlink(temp_file.name)
        except OSError:
            pass
    
    # Return file and clean up after response
    response = flask.send_file(temp_file.name, mimetype='image/png', as_attachment=False)
    response.call_on_close(cleanup_temp_file)
    return response
