from flask_restx import Resource, fields, marshal
import validators, datetime
import os
import tempfile
from flask import request, send_file, current_app as app
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest

from . import api, response_fields
from .. import common
from ... import models
from ...utils.avatar import (
    allowed_file, validate_image_file, process_avatar_image, 
    generate_avatar_filename, get_avatar_storage_path,
    generate_initials_avatar, get_avatar_info, delete_avatar_file
)
from ...utils.vcard import generate_user_vcard, get_user_vcard_headers

db = models.db

user = api.namespace('user', description='User operations')

user_fields_get = api.model('UserGet', {
    'email': fields.String(description='The email address of the user', example='John.Doe@example.com', attribute='_email'),
    'password': fields.String(description="Hash of the user's password; Example='$bcrypt-sha256$v=2,t=2b,r=12$fmsAdJbYAD1gGQIE5nfJq.$zLkQUEs2XZfTpAEpcix/1k5UTNPm0jO'"),
    'comment': fields.String(description='A description for the user. This description is shown on the Users page', example='my comment'),
    'quota_bytes': fields.Integer(description='The maximum quota for the user\'s email box in bytes', example='1000000000'),
    'quota_bytes_used': fields.Integer(description='The size of the user\'s email box in bytes', example='5000000'),
    'global_admin': fields.Boolean(description='Make the user a global administrator'),
    'enabled': fields.Boolean(description='Enable the user. When an user is disabled, the user is unable to login to the Admin GUI or webmail or access his email via IMAP/POP3 or send mail'),
    'change_pw_next_login': fields.Boolean(description='Force the user to change their password at next login'),
    'enable_imap': fields.Boolean(description='Allow email retrieval via IMAP'),
    'enable_pop': fields.Boolean(description='Allow email retrieval via POP3'),
    'allow_spoofing': fields.Boolean(description='Allow the user to spoof the sender (send email as anyone)'),
    'forward_enabled': fields.Boolean(description='Enable auto forwarding'),
    'forward_destination': fields.List(fields.String(description='Email address to forward emails to'), example='["Other@example.com"]'),
    'forward_keep': fields.Boolean(description='Keep a copy of the forwarded email in the inbox'),
    'reply_enabled': fields.Boolean(description='Enable automatic replies. This is also known as out of office (ooo) or out of facility (oof) replies'),
    'reply_subject': fields.String(description='Optional subject for the automatic reply', example='Out of office'),
    'reply_body': fields.String(description='The body of the automatic reply email', example='Hello, I am out of office. I will respond when I am back.'),
    'reply_startdate': fields.Date(description='Start date for automatic replies in YYYY-MM-DD format.', example='2022-02-10'),
    'reply_enddate': fields.Date(description='End date for automatic replies in YYYY-MM-DD format.', example='2022-02-22'),
    'displayed_name': fields.String(description='The display name of the user within the Admin GUI', example='John Doe'),
    'spam_enabled': fields.Boolean(description='Enable the spam filter'),
    'spam_mark_as_read': fields.Boolean(description='Enable marking spam mails as read'),
    'spam_threshold': fields.Integer(description='The user defined spam filter tolerance', example='80'),
    'avatar_filename': fields.String(description='Filename of the user avatar image', example='avatar_12345678_abcd1234.jpg'),
    'avatar_url': fields.String(description='URL to access the user avatar', example='/admin/api/v1/user/john.doe@example.com/avatar'),
})

user_fields_post = api.model('UserCreate', {
    'email': fields.String(description='The email address of the user', example='John.Doe@example.com', attribute='_email', required=True),
    'raw_password': fields.String(description='The raw (plain text) password of the user. Mailu will hash the password using BCRYPT-SHA256', example='secret', required=True),
    'comment': fields.String(description='A description for the user. This description is shown on the Users page', example='my comment'),
    'quota_bytes': fields.Integer(description='The maximum quota for the user’s email box in bytes', example='1000000000'),
    'global_admin': fields.Boolean(description='Make the user a global administrator'),
    'enabled': fields.Boolean(description='Enable the user. When an user is disabled, the user is unable to login to the Admin GUI or webmail or access his email via IMAP/POP3 or send mail'),
    'change_pw_next_login': fields.Boolean(description='Force the user to change their password at next login'),
    'enable_imap': fields.Boolean(description='Allow email retrieval via IMAP'),
    'enable_pop': fields.Boolean(description='Allow email retrieval via POP3'),
    'allow_spoofing': fields.Boolean(description='Allow the user to spoof the sender (send email as anyone)'),
    'forward_enabled': fields.Boolean(description='Enable auto forwarding'),
    'forward_destination': fields.List(fields.String(description='Email address to forward emails to'), example='["Other@example.com"]'),
    'forward_keep': fields.Boolean(description='Keep a copy of the forwarded email in the inbox'),
    'reply_enabled': fields.Boolean(description='Enable automatic replies. This is also known as out of office (ooo) or out of facility (oof) replies'),
    'reply_subject': fields.String(description='Optional subject for the automatic reply', example='Out of office'),
    'reply_body': fields.String(description='The body of the automatic reply email', example='Hello, I am out of office. I will respond when I am back.'),
    'reply_startdate': fields.Date(description='Start date for automatic replies in YYYY-MM-DD format.', example='2022-02-10'),
    'reply_enddate': fields.Date(description='End date for automatic replies in YYYY-MM-DD format.', example='2022-02-22'),
    'displayed_name': fields.String(description='The display name of the user within the Admin GUI', example='John Doe'),
    'spam_enabled': fields.Boolean(description='Enable the spam filter'),
    'spam_mark_as_read': fields.Boolean(description='Enable marking spam mails as read'),
    'spam_threshold': fields.Integer(description='The user defined spam filter tolerance', example='80'),
})

user_fields_put = api.model('UserUpdate', {
    'raw_password': fields.String(description='The raw (plain text) password of the user. Mailu will hash the password using BCRYPT-SHA256', example='secret'),
    'comment': fields.String(description='A description for the user. This description is shown on the Users page', example='my comment'),
    'quota_bytes': fields.Integer(description='The maximum quota for the user’s email box in bytes', example='1000000000'),
    'global_admin': fields.Boolean(description='Make the user a global administrator'),
    'enabled': fields.Boolean(description='Enable the user. When an user is disabled, the user is unable to login to the Admin GUI or webmail or access his email via IMAP/POP3 or send mail'),
    'change_pw_next_login': fields.Boolean(description='Force the user to change their password at next login'),
    'enable_imap': fields.Boolean(description='Allow email retrieval via IMAP'),
    'enable_pop': fields.Boolean(description='Allow email retrieval via POP3'),
    'allow_spoofing': fields.Boolean(description='Allow the user to spoof the sender (send email as anyone)'),
    'forward_enabled': fields.Boolean(description='Enable auto forwarding'),
    'forward_destination': fields.List(fields.String(description='Email address to forward emails to'), example='["Other@example.com"]'),
    'forward_keep': fields.Boolean(description='Keep a copy of the forwarded email in the inbox'),
    'reply_enabled': fields.Boolean(description='Enable automatic replies. This is also known as out of office (ooo) or out of facility (oof) replies'),
    'reply_subject': fields.String(description='Optional subject for the automatic reply', example='Out of office'),
    'reply_body': fields.String(description='The body of the automatic reply email', example='Hello, I am out of office. I will respond when I am back.'),
    'reply_startdate': fields.Date(description='Start date for automatic replies in YYYY-MM-DD format.', example='2022-02-10'),
    'reply_enddate': fields.Date(description='End date for automatic replies in YYYY-MM-DD format.', example='2022-02-22'),
    'displayed_name': fields.String(description='The display name of the user within the Admin GUI', example='John Doe'),
    'spam_enabled': fields.Boolean(description='Enable the spam filter'),
    'spam_mark_as_read': fields.Boolean(description='Enable marking spam mails as read'),
    'spam_threshold': fields.Integer(description='The user defined spam filter tolerance', example='80'),
})


@user.route('')
class Users(Resource):
    @user.doc('list_user')
    @user.marshal_with(user_fields_get, as_list=True, skip_none=True, mask=None)
    @user.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def get(self):
        "List all users"
        return models.User.query.all()

    @user.doc('create_user')
    @user.expect(user_fields_post)
    @user.response(200, 'Success', response_fields)
    @user.response(400, 'Input validation exception', response_fields)
    @user.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @user.response(409, 'Duplicate user', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def post(self):
        """ Create a new user """
        data = api.payload
        if not validators.email(data['email']):
            return { 'code': 400, 'message': f'Provided email address {data["email"]} is not a valid email address'}, 400
        if 'forward_destination' in data and len(data['forward_destination']) > 0:
            for dest in data['forward_destination']:
                if not validators.email(dest):
                    return { 'code': 400, 'message': f'Provided forward destination email address {dest} is not a valid email address'}, 400
        localpart, domain_name = data['email'].lower().rsplit('@', 1)
        domain_found = models.Domain.query.get(domain_name)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain_name} does not exist'}, 404
        if not domain_found.max_users == -1 and len(domain_found.users) >= domain_found.max_users:
            return { 'code': 409, 'message': f'Too many users for domain {domain_name}'}, 409
        email_found = models.User.query.filter_by(email=data['email']).first()
        if email_found:
            return { 'code': 409, 'message': f'User {data["email"]} already exists'}, 409
        if 'forward_enabled' in data and data['forward_enabled'] is True:
            if ('forward_destination' in data and len(data['forward_destination']) == 0) or 'forward_destination' not in data:
                return { 'code': 400, 'message': f'forward_destination is mandatory when forward_enabled is true'}, 400

        user_new = models.User(email=data['email'])
        if 'raw_password' in data:
            user_new.set_password(data['raw_password'])
        if 'comment' in data:
            user_new.comment = data['comment']
        if 'quota_bytes' in data:
            user_new.quota_bytes = data['quota_bytes']
        if 'global_admin' in data:
            user_new.global_admin = data['global_admin']
        if 'enabled' in data:
            user_new.enabled = data['enabled']
        if 'change_pw_next_login' in data:
            user_new.change_pw_next_login = data['change_pw_next_login']
        if 'enable_imap' in data:
            user_new.enable_imap = data['enable_imap']
        if 'enable_pop' in data:
            user_new.enable_pop = data['enable_pop']
        if 'allow_spoofing' in data:
            user_new.allow_spoofing = data['allow_spoofing']
        if 'forward_enabled' in data:
            user_new.forward_enabled = data['forward_enabled']
        if 'forward_destination' in data and len(data['forward_destination']) > 0:
            user_new.forward_destination = data['forward_destination']
        if 'forward_keep' in data:
            user_new.forward_keep = data['forward_keep']
        if 'reply_enabled' in data:
            user_new.reply_enabled = data['reply_enabled']
        if 'reply_subject' in data:
            user_new.reply_subject = data['reply_subject']
        if 'reply_body' in data:
            user_new.reply_body = data['reply_body']
        if 'reply_startdate' in data:
            year, month, day = data['reply_startdate'].split('-')
            date = datetime.datetime(int(year), int(month), int(day))
            user_new.reply_startdate = date
        if 'reply_enddate' in data:
            year, month, day = data['reply_enddate'].split('-')
            date = datetime.datetime(int(year), int(month), int(day))
            user_new.reply_enddate = date
        if 'displayed_name' in data:
            user_new.displayed_name = data['displayed_name']
        if 'spam_enabled' in data:
            user_new.spam_enabled = data['spam_enabled']
        if 'spam_mark_as_read' in data:
            user_new.spam_mark_as_read = data['spam_mark_as_read']
        if 'spam_threshold' in data:
            user_new.spam_threshold = data['spam_threshold']
        db.session.add(user_new)
        db.session.commit()

        return {'code': 200,'message': f'User {data["email"]} has been created'}, 200

@user.route('/<string:email>')
class User(Resource):
    @user.doc('find_user')
    @user.response(200, 'Success', user_fields_get)
    @user.response(400, 'Input validation exception', response_fields)
    @user.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @user.response(404, 'User not found', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, email):
        """ Look up the specified user """
        if not validators.email(email):
            return { 'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400

        email_found = models.User.query.filter_by(email=email).first()
        if email_found is None:
            return { 'code': 404, 'message': f'User {email} cannot be found'}, 404
        return  marshal(email_found, user_fields_get), 200

    @user.doc('update_user')
    @user.expect(user_fields_put)
    @user.response(200, 'Success', response_fields)
    @user.response(400, 'Input validation exception', response_fields)
    @user.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @user.response(404, 'User not found', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def patch(self, email):
        """ Update the specified user """
        data = api.payload
        if not validators.email(email):
            return { 'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400
        if 'forward_destination' in data and len(data['forward_destination']) > 0:
            for dest in data['forward_destination']:
                if not validators.email(dest):
                    return { 'code': 400, 'message': f'Provided forward destination email address {dest} is not a valid email address'}, 400
        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404
        if ('forward_enabled' in data and data['forward_enabled'] is True) or ('forward_enabled' not in data and user_found.forward_enabled):
            if ('forward_destination' in data and len(data['forward_destination']) == 0):
                return { 'code': 400, 'message': f'forward_destination is mandatory when forward_enabled is true'}, 400

        if 'raw_password' in data:
            user_found.set_password(data['raw_password'])
        if 'comment' in data:
            user_found.comment = data['comment']
        if 'quota_bytes' in data:
            user_found.quota_bytes = data['quota_bytes']
        if 'global_admin' in data:
            user_found.global_admin = data['global_admin']
        if 'enabled' in data:
            user_found.enabled = data['enabled']
        if 'change_pw_next_login' in data:
            user_found.change_pw_next_login = data['change_pw_next_login']
        if 'enable_imap' in data:
            user_found.enable_imap = data['enable_imap']
        if 'enable_pop' in data:
            user_found.enable_pop = data['enable_pop']
        if 'allow_spoofing' in data:
            user_found.allow_spoofing = data['allow_spoofing']
        if 'forward_enabled' in data:
            user_found.forward_enabled = data['forward_enabled']
        if 'forward_destination' in data and len(data['forward_destination']) > 0:
            user_found.forward_destination = data['forward_destination']
        if 'forward_keep' in data:
            user_found.forward_keep = data['forward_keep']
        if 'reply_enabled' in data:
            user_found.reply_enabled = data['reply_enabled']
        if 'reply_subject' in data:
            user_found.reply_subject = data['reply_subject']
        if 'reply_body' in data:
            user_found.reply_body = data['reply_body']
        if 'reply_startdate' in data:
            year, month, day = data['reply_startdate'].split('-')
            date = datetime.datetime(int(year), int(month), int(day))
            user_found.reply_startdate = date
        if 'reply_enddate' in data:
            year, month, day = data['reply_enddate'].split('-')
            date = datetime.datetime(int(year), int(month), int(day))
            user_found.reply_enddate = date
        if 'displayed_name' in data:
            user_found.displayed_name = data['displayed_name']
        if 'spam_enabled' in data:
            user_found.spam_enabled = data['spam_enabled']
        if 'spam_mark_as_read' in data:
            user_found.spam_mark_as_read = data['spam_mark_as_read']
        if 'spam_threshold' in data:
            user_found.spam_threshold = data['spam_threshold']
        db.session.add(user_found)
        db.session.commit()

        return {'code': 200,'message': f'User {email} has been updated'}, 200


    @user.doc('delete_user')
    @user.response(200, 'Success', response_fields)
    @user.response(400, 'Input validation exception', response_fields)
    @user.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @user.response(404, 'User not found', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, email):
        """ Delete the specified user """
        if not validators.email(email):
            return { 'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400

        email_found = models.User.query.filter_by(email=email).first()
        if email_found is None:
            return { 'code': 404, 'message': f'User {email} cannot be found'}, 404
        
        # Delete user's avatar if it exists
        if email_found.avatar_filename:
            email_found.delete_avatar()
        
        db.session.delete(email_found)
        db.session.commit()
        return { 'code': 200, 'message': f'User {email} has been deleted'}, 200


@user.route('/<string:email>/avatar')
class UserAvatar(Resource):
    @user.doc('get_user_avatar')
    @user.response(200, 'Avatar image')
    @user.response(400, 'Input validation exception', response_fields)
    @user.response(404, 'User or avatar not found', response_fields)
    def get(self, email):
        """ Get user's avatar image """
        if not validators.email(email):
            return {'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400

        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404

        # Check if user has uploaded avatar
        if user_found.avatar_filename:
            avatar_path = user_found.avatar_path
            if avatar_path and os.path.exists(avatar_path):
                return send_file(avatar_path, mimetype='image/jpeg')

        # Generate initials-based avatar
        initials = user_found.get_avatar_initials()
        avatar_img = generate_initials_avatar(initials)
        
        # Save to temporary file and return
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        avatar_img.save(temp_file.name, 'PNG')
        temp_file.close()
        
        try:
            return send_file(temp_file.name, mimetype='image/png', as_attachment=False)
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass

    @user.doc('upload_user_avatar')
    @user.response(200, 'Avatar uploaded successfully', response_fields)
    @user.response(400, 'Invalid file or validation error', response_fields)
    @user.response(404, 'User not found', response_fields)
    @user.response(413, 'File too large', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def post(self, email):
        """ Upload avatar for user """
        if not validators.email(email):
            return {'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400

        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404

        # Check if file was uploaded
        if 'avatar' not in request.files:
            return {'code': 400, 'message': 'No avatar file provided'}, 400

        file = request.files['avatar']
        if file.filename == '':
            return {'code': 400, 'message': 'No file selected'}, 400

        if not allowed_file(file.filename):
            return {'code': 400, 'message': 'Invalid file type. Allowed: PNG, JPG, JPEG, WebP'}, 400

        # Save uploaded file to temporary location
        filename = secure_filename(file.filename)
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)

        try:
            # Validate uploaded file
            is_valid, error_msg = validate_image_file(temp_file.name)
            if not is_valid:
                return {'code': 400, 'message': error_msg}, 400

            # Generate avatar filename and storage path
            storage_path = get_avatar_storage_path()
            avatar_filename = generate_avatar_filename(email, filename)
            avatar_path = os.path.join(storage_path, avatar_filename)

            # Process and save avatar
            success, error_msg = process_avatar_image(temp_file.name, avatar_path)
            if not success:
                return {'code': 400, 'message': error_msg}, 400

            # Delete old avatar if exists
            if user_found.avatar_filename:
                user_found.delete_avatar()

            # Update user record
            user_found.avatar_filename = avatar_filename
            db.session.commit()

            return {'code': 200, 'message': f'Avatar uploaded successfully for user {email}'}, 200

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass

    @user.doc('delete_user_avatar')
    @user.response(200, 'Avatar deleted successfully', response_fields)
    @user.response(400, 'Input validation exception', response_fields)
    @user.response(404, 'User not found', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, email):
        """ Delete user's avatar """
        if not validators.email(email):
            return {'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400

        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404

        if user_found.avatar_filename:
            user_found.delete_avatar()
            db.session.commit()
            return {'code': 200, 'message': f'Avatar deleted successfully for user {email}'}, 200
        else:
            return {'code': 404, 'message': f'User {email} has no avatar to delete'}, 404


@user.route('/<string:email>/avatar/info')
class UserAvatarInfo(Resource):
    @user.doc('get_user_avatar_info')
    @user.response(200, 'Avatar information')
    @user.response(400, 'Input validation exception', response_fields)
    @user.response(404, 'User not found', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, email):
        """ Get avatar information for user """
        if not validators.email(email):
            return {'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400

        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404

        avatar_info = get_avatar_info(user_found)
        return {'code': 200, 'data': avatar_info}, 200


@user.route('/<string:email>/vcard')
class UserVCard(Resource):
    @user.doc('get_user_vcard')
    @user.response(200, 'User vCard with avatar')
    @user.response(400, 'Input validation exception', response_fields)
    @user.response(404, 'User not found', response_fields)
    def get(self, email):
        """ Get vCard for user including avatar """
        if not validators.email(email):
            return {'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400

        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404

        vcard_data = generate_user_vcard(user_found)
        headers = get_user_vcard_headers()
        
        return app.response_class(
            vcard_data,
            headers=headers
        )
