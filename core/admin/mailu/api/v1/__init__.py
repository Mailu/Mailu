from flask import Blueprint
from flask_restx import Api, fields


VERSION = 1.0
api_token = None

blueprint = Blueprint(f'api_v{int(VERSION)}', __name__)

authorization = {
    'Bearer': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization'
    }
}

api = Api(
    blueprint, version=f'{VERSION:.1f}',
    title='Mailu API', default_label='Mailu',
    validate=True,
    authorizations=authorization,
    security='Bearer',
    doc='/'
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

from . import domain
from . import alias
from . import relay
from . import user
from . import token
