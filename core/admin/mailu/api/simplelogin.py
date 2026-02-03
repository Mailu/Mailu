"""SimpleLogin-compatible API endpoints for Bitwarden integration.

These endpoints are registered at /api/ (non-versioned) to match SimpleLogin's API structure,
allowing Bitwarden password manager to use Mailu for anonymous email alias generation.
"""

from flask import Blueprint, request, g
from flask_restx import Api, Resource, fields
from datetime import datetime as dt
from . import common
from mailu import models, utils
import flask
import secrets

blueprint = Blueprint('simplelogin', __name__)

authorization = {
    'Authentication': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authentication'
    }
}

api = Api(
    blueprint,
    title='SimpleLogin-compatible API',
    version='1.0',
    validate=True,
    authorizations=authorization,
    security=['Authentication'],
    doc=False  # Disable docs for this compatibility endpoint
)

alias_ns = api.namespace('alias', description='Alias operations')

@alias_ns.route('/random/new')
class RandomAlias(Resource):
    @api.response(201, 'Success', api.model('RandomAliasResponse', {
        'email': fields.String(description='created alias email address'),
        'enabled': fields.Boolean(description='whether alias is enabled'),
        'note': fields.String(description='alias note/comment'),
        'creation_date': fields.String(description='creation date'),
        'creation_timestamp': fields.Integer(description='creation timestamp'),
        'nb_forward': fields.Integer(description='number of forwarded emails'),
        'nb_block': fields.Integer(description='number of blocked emails'),
        'nb_reply': fields.Integer(description='number of replies'),
    }))
    @api.response(400, 'Input validation exception')
    @api.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @common.user_token_authorization
    def post(self):
        """Create a random alias (SimpleLogin/Bitwarden compatible).
        
        Query params: hostname (optional)
        Request body: note (optional)
        
        This endpoint matches SimpleLogin's API: POST /api/alias/random/new
        """
        
        data = api.payload or {}
        note = data.get('note')
        hostname = request.args.get('hostname')

        # Find all domains with anonmail access
        accessible_domains = []
        for d in models.Domain.query.all():
            if (g.user.global_admin or models.has_domain_access(d.name, user=g.user) or 
                (d.anonmail_enabled and g.user.domain and d.name == g.user.domain.name)):
                accessible_domains.append(d.name)

        if not accessible_domains:
            return {'code': 403, 'message': 'You do not have access to any domains for creating aliases'}, 403

        # Select random domain from accessible domains
        domain_name = secrets.choice(accessible_domains)

        if hostname and not note:
            note = f'Website: {hostname}'

        # Generate unique alias localpart
        localpart = None
        for _ in range(flask.current_app.config.get('ANONMAIL_MAX_RETRIES', 10)):
            candidate = utils.generate_anonymous_alias_localpart(hostname=hostname)
            email_candidate = f"{candidate}@{domain_name}"
            if not models.Alias.query.filter_by(email=email_candidate).first() and not models.User.query.filter_by(email=email_candidate).first():
                localpart = candidate
                break
        
        if not localpart:
            return {'code': 409, 'message': 'Unable to find a unique alias after several retries'}, 409

        alias_email = f"{localpart}@{domain_name}"

        alias_model = models.Alias(
            email=alias_email,
            destination=[g.user.email],
            owner_email=g.user.email,
            wildcard=False
        )
        
        # Store hostname (empty string if not provided)
        alias_model.hostname = hostname if hostname else ""
        if note:
            alias_model.comment = note

        models.db.session.add(alias_model)
        models.db.session.commit()

        # Return SimpleLogin-compatible response
        return {
            'email': alias_model.email,
            'enabled': not alias_model.disabled,
            'note': alias_model.comment or '',
            'creation_date': alias_model.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'creation_timestamp': int(dt.combine(alias_model.created_at, dt.min.time()).timestamp()),
            # These stats are not tracked, return 0
            'nb_forward': 0,
            'nb_block': 0,
            'nb_reply': 0
        }, 201
