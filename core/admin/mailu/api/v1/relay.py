from flask_restx import Resource, fields, marshal
import validators

from . import api, response_fields
from .. import common
from ... import models

db = models.db

relay = api.namespace('relay', description='Relay operations')

relay_fields = api.model('Relay', {
    'name': fields.String(description='relayed domain name', example='example.com', required=True),
    'smtp': fields.String(description='remote host', example='example.com', required=False),
    'comment': fields.String(description='a comment', required=False)
})

relay_fields_update = api.model('RelayUpdate', {
    'smtp': fields.String(description='remote host', example='example.com', required=False),
    'comment': fields.String(description='a comment', required=False)
})

@relay.route('')
class Relays(Resource):
    @relay.doc('list_relays')
    @relay.marshal_with(relay_fields, as_list=True, skip_none=True, mask=None)
    @relay.doc(security='Bearer')
    @common.api_token_authorization
    def get(self):
        "List relays"
        return models.Relay.query.all()

    @relay.doc('create_relay')
    @relay.expect(relay_fields)
    @relay.response(200, 'Success', response_fields)
    @relay.response(400, 'Input validation exception')
    @relay.response(409, 'Duplicate relay', response_fields)
    @relay.doc(security='Bearer')
    @common.api_token_authorization
    def post(self):
        """ Create relay """
        data = api.payload

        if not validators.domain(name):
            return { 'code': 400, 'message': f'Relayed domain {name} is not a valid domain'}, 400

        if common.fqdn_in_use(data['name']):
            return { 'code': 409, 'message': f'Duplicate domain {data["name"]}'}, 409
        relay_model = models.Relay(name=data['name'])
        if 'smtp' in data:
            relay_model.smtp = data['smtp']
        if 'comment' in data:
            relay_model.comment = data['comment']
        db.session.add(relay_model)
        db.session.commit()
        return {'code': 200, 'message': f'Relayed domain {data["name"]} has been created'}, 200

@relay.route('/<string:name>')
class Relay(Resource):
    @relay.doc('find_relay')
    @relay.response(400, 'Input validation exception', response_fields)
    @relay.response(404, 'Relay not found', response_fields)
    @relay.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, name):
        """ Find relay """
        if not validators.domain(name):
            return { 'code': 400, 'message': f'Relayed domain {name} is not a valid domain'}, 400

        relay_found = models.Relay.query.filter_by(name=name).first()
        if relay_found is None:
            return { 'code': 404, 'message': f'Relayed domain {name} cannot be found'}, 404
        return  marshal(relay_found, relay_fields), 200

    @relay.doc('update_relay')
    @relay.expect(relay_fields_update)
    @relay.response(200, 'Success', response_fields)
    @relay.response(400, 'Input validation exception', response_fields)
    @relay.response(404, 'Relay not found', response_fields)
    @relay.response(409, 'Duplicate relay', response_fields)
    @relay.doc(security='Bearer')
    @common.api_token_authorization
    def patch(self, name):
        """ Update relay """
        data = api.payload

        if not validators.domain(name):
            return { 'code': 400, 'message': f'Relayed domain {name} is not a valid domain'}, 400

        relay_found = models.Relay.query.filter_by(name=name).first()
        if relay_found is None:
            return { 'code': 404, 'message': f'Relayed domain {name} cannot be found'}, 404

        if 'smtp' in data:
            relay_found.smtp = data['smtp']
        if 'comment' in data:
            relay_found.comment = data['comment']
        db.session.add(relay_found)
        db.session.commit()
        return { 'code': 200, 'message': f'Relayed domain {name} has been updated'}, 200


    @relay.doc('delete_relay')
    @relay.response(200, 'Success', response_fields)
    @relay.response(400, 'Input validation exception', response_fields)
    @relay.response(404, 'Relay not found', response_fields)
    @relay.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, name):
        """ Delete relay """
        if not validators.domain(name):
            return { 'code': 400, 'message': f'Relayed domain {name} is not a valid domain'}, 400
        relay_found = models.Relay.query.filter_by(name=name).first()
        if relay_found is None:
            return { 'code': 404, 'message': f'Relayed domain {name} cannot be found'}, 404
        db.session.delete(relay_found)
        db.session.commit()
        return { 'code': 200, 'message': f'Relayed domain {name} has been deleted'}, 200
