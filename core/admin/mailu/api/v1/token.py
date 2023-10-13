from flask_restx import Resource, fields, marshal
import validators, datetime
import flask
from passlib import pwd

from . import api, response_fields
from .. import common
from ... import models

db = models.db

token = api.namespace('token', description='Token operations')

token_user_fields = api.model('TokenGetResponse', {
    'id': fields.String(description='The record id of the token (unique identifier)', example='1'),
    'email': fields.String(description='The email address of the user', example='John.Doe@example.com', attribute='user_email'),
    'comment': fields.String(description='A description for the token. This description is shown on the Authentication tokens page', example='my comment'),
    'AuthorizedIP': fields.String(description='Comma separated list of white listed IP addresses or networks that may use this token.', example="['203.0.113.0/24']", attribute='ip'),
    'Created': fields.String(description='The date when the token was created', example='John.Doe@example.com', attribute='created_at'),
    'Last edit': fields.String(description='The date when the token was last modifified', example='John.Doe@example.com', attribute='updated_at')
})

token_user_fields_post = api.model('TokenPost', {
    'email': fields.String(description='The email address of the user', example='John.Doe@example.com', attribute='user_email'),
    'comment': fields.String(description='A description for the token. This description is shown on the Authentication tokens page', example='my comment'),
    'AuthorizedIP': fields.String(description='Comma separated list of white listed IP addresses or networks that may use this token.', example="['203.0.113.0/24']", attribute='ip'),
})

token_user_fields_post2 = api.model('TokenPost2', {
    'comment': fields.String(description='A description for the token. This description is shown on the Authentication tokens page', example='my comment'),
    'AuthorizedIP': fields.String(description='Comma separated list of white listed IP addresses or networks that may use this token.', example="['203.0.113.0/24']", attribute='ip'),
})

token_user_post_response = api.model('TokenPostResponse', {
    'id': fields.String(description='The record id of the token (unique identifier)', example='1'),
    'token': fields.String(description='The created authentication token for the user.', example='2caf6607de5129e4748a2c061aee56f2', attribute='password'),
    'email': fields.String(description='The email address of the user', example='John.Doe@example.com', attribute='user_email'),
    'comment': fields.String(description='A description for the token. This description is shown on the Authentication tokens page', example='my comment'),
    'AuthorizedIP': fields.String(description='Comma separated list of white listed IP addresses or networks that may use this token.', example="['203.0.113.0/24']", attribute='ip'),
    'Created': fields.String(description='The date when the token was created', example='John.Doe@example.com', attribute='created_at')
})

@token.route('')
class Tokens(Resource):
    @token.doc('list_tokens')
    @token.marshal_with(token_user_fields, as_list=True, skip_none=True, mask=None)
    @token.doc(security='Bearer')
    @common.api_token_authorization
    def get(self):
        """List tokens"""
        return models.Token.query.all()

    @token.doc('create_token')
    @token.expect(token_user_fields_post)
    @token.response(200, 'Success', token_user_post_response)
    @token.response(400, 'Input validation exception')
    @token.response(409, 'Duplicate relay', response_fields)
    @token.doc(security='Bearer')
    @common.api_token_authorization
    def post(self):
        """ Create a new token"""
        data = api.payload
        email = data['email']
        if not validators.email(email):
            return { 'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400
        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404
        tokens = user_found.tokens

        token_new = models.Token(user_email=data['email'])
        if 'comment' in data:
            token_new.comment = data['comment']
        if 'AuthorizedIP' in data:
            token_new.ip = data['AuthorizedIP'].replace(' ','').split(',')
        raw_password = pwd.genword(entropy=128, length=32, charset="hex")
        token_new.set_password(raw_password)
        models.db.session.add(token_new)
        #apply the changes
        db.session.commit()
        response_dict  = {
            'id' : token_new.id,
            'token' : raw_password,
            'email' : token_new.user_email,
            'comment' : token_new.comment,
            'AuthorizedIP' : token_new.ip,
            'Created': str(token_new.created_at),
            }

        return  response_dict

@token.route('user/<string:email>')
class Token(Resource):
    @token.doc('find_tokens_of_user')
    @token.marshal_with(token_user_fields, as_list=True, skip_none=True, mask=None)
    @token.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, email):
        "Find tokens of user"
        if not validators.email(email):
            return { 'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400
        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404
        tokens = user_found.tokens
        return tokens

    @token.doc('create_token')
    @token.expect(token_user_fields_post2)
    @token.response(200, 'Success', token_user_post_response)
    @token.response(400, 'Input validation exception')
    @token.response(409, 'Duplicate relay', response_fields)
    @token.doc(security='Bearer')
    @common.api_token_authorization
    def post(self, email):
        """ Create a new token for user"""
        data = api.payload
        if not validators.email(email):
            return { 'code': 400, 'message': f'Provided email address {email} is not a valid email address'}, 400
        user_found = models.User.query.get(email)
        if not user_found:
            return {'code': 404, 'message': f'User {email} cannot be found'}, 404

        token_new = models.Token(user_email=email)
        if 'comment' in data:
            token_new.comment = data['comment']
        if 'AuthorizedIP' in data:
            token_new.ip = token_new.ip = data['AuthorizedIP'].replace(' ','').split(',')
        raw_password = pwd.genword(entropy=128, length=32, charset="hex")
        token_new.set_password(raw_password)
        models.db.session.add(token_new)
        #apply the changes
        db.session.commit()
        response_dict  = {
            'id' : token_new.id,
            'token' : raw_password,
            'email' : token_new.user_email,
            'comment' : token_new.comment,
            'AuthorizedIP' : token_new.ip,
            'Created': str(token_new.created_at),
            }
        return  response_dict

@token.route('/<string:token_id>')
class Token(Resource):
    @token.doc('find_token')
    @token.marshal_with(token_user_fields, as_list=True, skip_none=True, mask=None)
    @token.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, token_id):
        "Find token"
        token = models.Token.query.get(token_id)
        if not token:
            return { 'code' : 404, 'message' : f'Record cannot be found for id {token_id} or invalid id provided'}, 404
        return token

    @token.doc('delete_token')
    @token.response(200, 'Success', response_fields)
    @token.response(400, 'Input validation exception', response_fields)
    @token.response(404, 'Token not found', response_fields)
    @token.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, token_id):
        """ Delete token """
        token = models.Token.query.get(token_id)
        if not token:
            return { 'code' : 404, 'message' : f'Record cannot be found for id {token_id} or invalid id provided'}, 404
        db.session.delete(token)
        db.session.commit()
        return {'code': 200, 'message': f'Token with id {token_id} has been deleted'}, 200
