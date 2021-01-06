from flask_restx import Resource, fields, abort

from . import api, response_fields, error_fields
from .. import common
from ... import models

db = models.db

dom = api.namespace('domain', description='Domain operations')
alt = api.namespace('alternative', description='Alternative operations')

domain_fields = api.model('Domain', {
    'name': fields.String(description='FQDN', example='example.com', required=True),
    'comment': fields.String(description='a comment'),
    'max_users': fields.Integer(description='maximum number of users', min=-1, default=-1),
    'max_aliases': fields.Integer(description='maximum number of aliases', min=-1, default=-1),
    'max_quota_bytes': fields.Integer(description='maximum quota for mailbox', min=0),
    'signup_enabled': fields.Boolean(description='allow signup'),
#    'dkim_key': fields.String,
    'alternatives': fields.List(fields.String(attribute='name', description='FQDN', example='example.com')),
})
# TODO - name ist required on creation but immutable on change
# TODO - name and alteranatives need to be checked to be a fqdn (regex)

domain_parser = api.parser()
domain_parser.add_argument('max_users', type=int, help='maximum number of users')
# TODO ... add more (or use marshmallow)

alternative_fields = api.model('Domain', {
    'name': fields.String(description='alternative FQDN', example='example.com', required=True),
    'domain': fields.String(description='domain FQDN', example='example.com', required=True),
    'dkim_key': fields.String,
})
# TODO: domain and name are not always required and can't be changed


@dom.route('')
class Domains(Resource):

    @dom.doc('list_domain')
    @dom.marshal_with(domain_fields, as_list=True, skip_none=True, mask=['dkim_key'])
    def get(self):
        """ List domains """
        return models.Domain.query.all()

    @dom.doc('create_domain')
    @dom.expect(domain_fields)
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', error_fields)
    @dom.response(409, 'Duplicate domain name', error_fields)
    def post(self):
        """ Create a new domain """
        data = api.payload
        if common.fqdn_in_use(data['name']):
            abort(409, f'Duplicate domain name {data["name"]!r}', errors={
                'name': data['name'],
            })
        for item, created in models.Domain.from_dict(data):
            if not created:
                abort(409, f'Duplicate domain name {item.name!r}', errors={
                        'alternatives': item.name,
                    })
            db.session.add(item)
        db.session.commit()

@dom.route('/<name>')
class Domain(Resource):
    
    @dom.doc('get_domain')
    @dom.response(200, 'Success', domain_fields)
    @dom.response(404, 'Domain not found')
    @dom.marshal_with(domain_fields)
    def get(self, name):
        """ Find domain by name """
        domain = models.Domain.query.get(name)
        if not domain:
            abort(404)
        return domain
           
    @dom.doc('update_domain')
    @dom.expect(domain_fields)
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', error_fields)
    @dom.response(404, 'Domain not found')
    def put(self, name):
        """ Update an existing domain """
        domain = models.Domain.query.get(name)
        if not domain:
            abort(404)
        data = api.payload
        data['name'] = name
        for item, created in models.Domain.from_dict(data):
            if created is True:
                db.session.add(item)
        db.session.commit()

    @dom.doc('modify_domain')
    @dom.expect(domain_parser)
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', error_fields)
    @dom.response(404, 'Domain not found')
    def post(self, name=None):
        """ Updates domain with form data """
        domain = models.Domain.query.get(name)
        if not domain:
            abort(404)
        data = dict(domain_parser.parse_args())
        data['name'] = name
        for item, created in models.Domain.from_dict(data):
            if created is True:
                db.session.add(item)
                # TODO: flush? 
        db.session.commit()

    @dom.doc('delete_domain')
    @dom.response(200, 'Success', response_fields)
    @dom.response(404, 'Domain not found')
    def delete(self, name=None):
        """ Delete domain """
        domain = models.Domain.query.get(name)
        if not domain:
            abort(404)
        db.session.delete(domain)
        db.session.commit()

                               
# @dom.route('/<name>/alternative')
# @alt.route('')
# class Alternatives(Resource):
    
#     @alt.doc('alternatives_list')
#     @alt.marshal_with(alternative_fields, as_list=True, skip_none=True, mask=['dkim_key'])
#     def get(self, name=None):
#         """ List alternatives (of domain) """
#         if name is None:
#             return models.Alternative.query.all()
#         else:
#             return models.Alternative.query.filter_by(domain_name = name).all()
        
#     @alt.doc('alternative_create')
#     @alt.expect(alternative_fields)
#     @alt.response(200, 'Success', response_fields)
#     @alt.response(400, 'Input validation exception', error_fields)
#     @alt.response(404, 'Domain not found')
#     @alt.response(409, 'Duplicate domain name', error_fields)
#     def post(self, name=None):
#         """ Create new alternative (for domain) """
#  #       abort(501)
#         data = api.payload
#         if name is not None:
#             data['name'] = name
#         domain = models.Domain.query.get(name)
#         if not domain:
#             abort(404)
#         if common.fqdn_in_use(data['name']):
#             abort(409, f'Duplicate domain name {data["name"]!r}', errors={
#                 'name': data['name'],
#             })
#         for item, created in models.Alternative.from_dict(data):
# # TODO: handle creation of domain
#             if not created:
#                 abort(409, f'Duplicate domain name {item.name!r}', errors={
#                         'alternatives': item.name,
#                     })
#         #     db.session.add(item)
#         # db.session.commit()

# @dom.route('/<name>/alternative/<alt>')
# @alt.route('/<name>')
# class Alternative(Resource):
#     def get(self, name, alt=None):
#         """ Find alternative (of domain) """
#         abort(501)
#     def put(self, name, alt=None):
#         """ Update alternative (of domain) """
#         abort(501)
#     def post(self, name, alt=None):
#         """ Update alternative (of domain) with form data """
#         abort(501)
#     def delete(self, name, alt=None):
#         """ Delete alternative (for domain) """
#         abort(501)

