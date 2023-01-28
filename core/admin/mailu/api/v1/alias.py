from flask_restx import Resource, fields, marshal
from . import api, response_fields
from .. import common
from ... import models

db = models.db

alias = api.namespace('alias', description='Alias operations')

alias_fields_update = alias.model('AliasUpdate', {
    'comment': fields.String(description='a comment'),
    'destination': fields.List(fields.String(description='alias email address', example='user@example.com')),
    'wildcard': fields.Boolean(description='enable SQL Like wildcard syntax')
})

alias_fields = alias.inherit('Alias',alias_fields_update, {
  'email': fields.String(description='the alias email address', example='user@example.com', required=True),
  'destination': fields.List(fields.String(description='alias email address', example='user@example.com', required=True)),

})


@alias.route('')
class Aliases(Resource):
    @alias.doc('list_alias')
    @alias.marshal_with(alias_fields, as_list=True, skip_none=True, mask=None)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def get(self):
        """ List aliases """
        return models.Alias.query.all()

    @alias.doc('create_alias')
    @alias.expect(alias_fields)
    @alias.response(200, 'Success', response_fields)
    @alias.response(400, 'Input validation exception', response_fields)
    @alias.response(409, 'Duplicate alias', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def post(self):
        """ Create a new alias """
        data = api.payload

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

        return {'code': 200, 'message': f'Alias {data["email"]} to destination {data["destination"]} has been created'}, 200

@alias.route('/<string:alias>')
class Alias(Resource):
    @alias.doc('find_alias')
    @alias.response(200, 'Success', alias_fields)
    @alias.response(404, 'Alias not found', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, alias):
        """ Find alias """
        alias_found = models.Alias.query.filter_by(email = alias).first()
        if alias_found is None:
          return { 'code': 404, 'message': f'Alias {alias} cannot be found'}, 404
        else:
          return marshal(alias_found,alias_fields), 200

    @alias.doc('update_alias')
    @alias.expect(alias_fields_update)
    @alias.response(200, 'Success', response_fields)
    @alias.response(404, 'Alias not found', response_fields)
    @alias.response(400, 'Input validation exception', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def patch(self, alias):
      """ Update alias """
      data = api.payload
      alias_found = models.Alias.query.filter_by(email = alias).first()
      if alias_found is None:
        return { 'code': 404, 'message': f'Alias {alias} cannot be found'}, 404
      if 'comment' in data:
        alias_found.comment = data['comment']
      if 'destination' in data:
        alias_found.destination = data['destination']
      if 'wildcard' in data:
        alias_found.wildcard = data['wildcard']
      db.session.add(alias_found)
      db.session.commit()
      return {'code': 200, 'message': f'Alias {alias} has been updated'}

    @alias.doc('delete_alias')
    @alias.response(200, 'Success', response_fields)
    @alias.response(404, 'Alias not found', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, alias):
      """ Delete alias """
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
    @alias.response(404, 'Alias or domain not found', response_fields)
    @alias.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, domain):
        """ Find aliases of domain """
        domain_found = models.Domain.query.filter_by(name=domain).first()
        if domain_found is None:
          return { 'code': 404, 'message': f'Domain {domain} cannot be found'}, 404
        aliases_found = domain_found.aliases
        if aliases_found.count == 0:
          return { 'code': 404, 'message': f'No alias can be found for domain {domain}'}, 404
        else:
          return marshal(aliases_found, alias_fields), 200
