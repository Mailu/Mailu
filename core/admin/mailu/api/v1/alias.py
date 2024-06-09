from flask_restx import Resource, fields, marshal
from . import api, response_fields
from .. import common
from ... import models
import validators

db = models.db

alias = api.namespace('alias', description='Alias operations')

alias_fields_update = alias.model('AliasUpdate', {
    'comment': fields.String(description='a comment'),
    'destination': fields.List(fields.String(description='alias email address', example='user@example.com')),
    'wildcard': fields.Boolean(description='enable SQL Like wildcard syntax')
})

alias_fields = alias.inherit('Alias',alias_fields_update, {
  'email': fields.String(description='the alias email address', example='user@example.com', required=True),
  'destination': fields.List(fields.String(description='destination email address', example='user@example.com', required=True)),

})


@alias.route('')
class Aliases(Resource):
    @alias.doc('list_alias')
    @alias.marshal_with(alias_fields, as_list=True, skip_none=True, mask=None)
    @alias.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def get(self):
        """ List all aliases """
        return models.Alias.query.all()

    @alias.doc('create_alias')
    @alias.expect(alias_fields)
    @alias.response(200, 'Success', response_fields)
    @alias.response(400, 'Input validation exception', response_fields)
    @alias.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alias.response(404, 'Not found', response_fields)
    @alias.response(409, 'Duplicate alias', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def post(self):
        """ Create a new alias """
        data = api.payload

        if not validators.email(data['email']):
            return { 'code': 400, 'message': f'Provided alias {data["email"]} is not a valid email address'}, 400
        localpart, domain_name = data['email'].lower().rsplit('@', 1)
        domain_found = models.Domain.query.get(domain_name)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain_name} does not exist ({data["email"]})'}, 404
        if not domain_found.max_aliases == -1 and len(domain_found.aliases) >= domain_found.max_aliases:
            return { 'code': 409, 'message': f'Too many aliases for domain {domain_name}'}, 409
        for dest in data['destination']:
            if not validators.email(dest):
                return { 'code': 400, 'message': f'Provided destination email address {dest} is not a valid email address'}, 400
            elif models.User.query.filter_by(email=dest).first() is None:
                return { 'code': 404, 'message': f'Provided destination email address {dest} does not exist'}, 404

        alias_found = models.Alias.query.filter_by(email = data['email']).first()
        if alias_found:
          return { 'code': 409, 'message': f'Duplicate alias {data["email"]}'}, 409

        alias_model = models.Alias(email=data["email"],destination=data['destination'])
        if 'comment' in data:
          alias_model.comment = data['comment']
        if 'wildcard' in data:
          alias_model.wildcard = data['wildcard']
        db.session.add(alias_model)
        db.session.commit()

        return {'code': 200, 'message': f'Alias {data["email"]} to destination(s) {data["destination"]} has been created'}, 200

@alias.route('/<string:alias>')
class Alias(Resource):
    @alias.doc('find_alias')
    @alias.response(200, 'Success', alias_fields)
    @alias.response(400, 'Input validation exception', response_fields)
    @alias.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alias.response(404, 'Alias not found', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, alias):
        """ Look up the specified alias """
        if not validators.email(alias):
            return { 'code': 400, 'message': f'Provided alias (email address) {alias} is not a valid email address'}, 400
        alias_found = models.Alias.query.filter_by(email = alias).first()
        if alias_found is None:
          return { 'code': 404, 'message': f'Alias {alias} cannot be found'}, 404
        else:
          return marshal(alias_found,alias_fields), 200

    @alias.doc('update_alias')
    @alias.expect(alias_fields_update)
    @alias.response(200, 'Success', response_fields)
    @alias.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alias.response(404, 'Alias not found', response_fields)
    @alias.response(400, 'Input validation exception', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def patch(self, alias):
      """ Update the specfied alias """
      data = api.payload

      if not validators.email(alias):
          return { 'code': 400, 'message': f'Provided alias (email address) {alias} is not a valid email address'}, 400
      alias_found = models.Alias.query.filter_by(email = alias).first()
      if alias_found is None:
        return { 'code': 404, 'message': f'Alias {alias} cannot be found'}, 404
      if 'comment' in data:
        alias_found.comment = data['comment']
      if 'destination' in data:
        alias_found.destination = data['destination']
        for dest in data['destination']:
            if not validators.email(dest):
                return { 'code': 400, 'message': f'Provided destination email address {dest} is not a valid email address'}, 400
            elif models.User.query.filter_by(email=dest).first() is None:
                return { 'code': 404, 'message': f'Provided destination email address {dest} does not exist'}, 404
      if 'wildcard' in data:
        alias_found.wildcard = data['wildcard']
      db.session.add(alias_found)
      db.session.commit()
      return {'code': 200, 'message': f'Alias {alias} has been updated'}

    @alias.doc('delete_alias')
    @alias.response(200, 'Success', response_fields)
    @alias.response(400, 'Input validation exception', response_fields)
    @alias.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alias.response(404, 'Alias not found', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, alias):
      """ Delete the specified alias """
      if not validators.email(alias):
          return { 'code': 400, 'message': f'Provided alias (email address) {alias} is not a valid email address'}, 400
      alias_found = models.Alias.query.filter_by(email = alias).first()
      if alias_found is None:
        return { 'code': 404, 'message': f'Alias {alias} cannot be found'}, 404
      db.session.delete(alias_found)
      db.session.commit()
      return {'code': 200, 'message': f'Alias {alias} has been deleted'}, 200

@alias.route('/destination/<string:domain>')
class AliasWithDest(Resource):
    @alias.doc('find_alias_filter_domain')
    @alias.response(200, 'Success', alias_fields)
    @alias.response(400, 'Input validation exception', response_fields)
    @alias.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alias.response(404, 'Alias or domain not found', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, domain):
        """ Look up the aliases of the specified domain """
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain_found = models.Domain.query.filter_by(name=domain).first()
        if domain_found is None:
          return { 'code': 404, 'message': f'Domain {domain} cannot be found'}, 404
        aliases_found = domain_found.aliases
        if aliases_found.count == 0:
          return { 'code': 404, 'message': f'No alias can be found for domain {domain}'}, 404
        else:
          return marshal(aliases_found, alias_fields), 200
