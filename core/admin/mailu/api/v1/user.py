from flask_restx import Resource, fields, marshal
import validators, datetime

from . import api, response_fields
from .. import common
from ... import models

db = models.db

user = api.namespace('user', description='User operations')

user_fields_get = api.model('UserGet', {
    'email': fields.String(description='The email address of the user', example='John.Doe@example.com', attribute='_email'),
    'password': fields.String(description="Hash of the user's password; Example='$bcrypt-sha256$v=2,t=2b,r=12$fmsAdJbYAD1gGQIE5nfJq.$zLkQUEs2XZfTpAEpcix/1k5UTNPm0jO'"),
    'comment': fields.String(description='A description for the user. This description is shown on the Users page', example='my comment'),
    'quota_bytes': fields.Integer(description='The maximum quota for the user’s email box in bytes', example='1000000000'),
    'quota_bytes_used': fields.Integer(description='The size of the user’s email box in bytes', example='5000000'),
    'global_admin': fields.Boolean(description='Make the user a global administrator'),
    'enabled': fields.Boolean(description='Enable the user. When an user is disabled, the user is unable to login to the Admin GUI or webmail or access his email via IMAP/POP3 or send mail'),
    'change_pw_next_login': fields.Boolean(description='Force the user to change their password at next login'),
    'enable_imap': fields.Boolean(description='Allow email retrieval via IMAP'),
    'enable_pop': fields.Boolean(description='Allow email retrieval via POP3'),
    'allow_spoofing': fields.Boolean(description='Allow the user to spoof the sender (send email as anyone)'),
    'forward_enabled': fields.Boolean(description='Enable auto forwarding'),
    'forward_destination': fields.List(fields.String(description='Email address to forward emails to'), example='Other@example.com'),
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
    'forward_destination': fields.List(fields.String(description='Email address to forward emails to'), example='Other@example.com'),
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
    'forward_destination': fields.List(fields.String(description='Email address to forward emails to'), example='Other@example.com'),
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
    @user.doc('list_users')
    @user.marshal_with(user_fields_get, as_list=True, skip_none=True, mask=None)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def get(self):
        "List users"
        return models.User.query.all()

    @user.doc('create_user')
    @user.expect(user_fields_post)
    @user.response(200, 'Success', response_fields)
    @user.response(400, 'Input validation exception')
    @user.response(409, 'Duplicate user', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def post(self):
        """ Create user """
        data = api.payload
        if not validators.email(data['email']):
            return { 'code': 400, 'message': f'Provided email address {data["email"]} is not a valid email address'}, 400
        localpart, domain_name = data['email'].lower().rsplit('@', 1)
        domain_found = models.Domain.query.get(domain_name)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain_name} does not exist'}, 404

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
        if 'forward_destination' in data:
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
    @user.response(400, 'Input validation exception', response_fields)
    @user.response(404, 'User not found', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, email):
        """ Find user """
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
    @user.response(404, 'User not found', response_fields)
    @user.response(409, 'Duplicate user', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def patch(self, email):
        """ Update user """
        data = api.payload
        if not validators.email(email):
            return { 'code': 400, 'message': f'Provided email address {data["email"]} is not a valid email address'}, 400
        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404

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
        if 'forward_destination' in data:
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
    @user.response(404, 'User not found', response_fields)
    @user.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, email):
        """ Delete user """
        if not validators.email(email):
            return { 'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400

        email_found = models.User.query.filter_by(email=email).first()
        if email_found is None:
            return { 'code': 404, 'message': f'User {email} cannot be found'}, 404
        db.session.delete(email_found)
        db.session.commit()
        return { 'code': 200, 'message': f'User {email} has been deleted'}, 200
