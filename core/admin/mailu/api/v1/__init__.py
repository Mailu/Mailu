"""
API Blueprint
"""

from flask import Blueprint
from flask_restx import Api, fields

VERSION = 1.0

blueprint = Blueprint(f'api_v{int(VERSION)}', __name__)

api = Api(
    blueprint, version=f'{VERSION:.1f}',
    title='Mailu API', default_label='Mailu',
    validate=True
)

response_fields = api.model('Response', {
    'code': fields.Integer,
    'message': fields.String,
})

error_fields = api.model('Error', {
    'errors': fields.Nested(api.model('Error_Key', {
        'key': fields.String,
        'message':fields.String
    })),
    'message': fields.String,
})

# import api namespaces (below field defs to avoid circular reference)
from . import domains
