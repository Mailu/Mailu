import validators
from flask import request
from flask_restx import Resource, fields, marshal
from . import api, response_fields, user
from .. import common
from ... import models, utils, passkeys as passkey_utils

db = models.db

dom = api.namespace('domain', description='Domain operations')
alt = api.namespace('alternative', description='Alternative operations')

domain_fields = api.model('Domain', {
    'name': fields.String(description='FQDN (e.g. example.com)', example='example.com', required=True),
    'comment': fields.String(description='a comment'),
    'max_users': fields.Integer(description='maximum number of users', min=-1, default=-1),
    'max_aliases': fields.Integer(description='maximum number of aliases', min=-1, default=-1),
    'max_quota_bytes': fields.Integer(description='maximum quota for mailbox', min=0),
    'signup_enabled': fields.Boolean(description='allow signup'),
    'passkey_enforce_aaguid': fields.Boolean(description='enforce the domain AAGUID policy'),
    'passkey_aaguid_mode': fields.String(description='Whether listed passkey AAGUIDs are allowed or blocked', enum=['allow', 'block']),
    'passkey_aaguids': fields.String(description='Comma or newline separated passkey AAGUID UUIDs'),
    'passkey_require_uv': fields.Boolean(description='require user verification for passkeys'),
    'passkey_backup_eligible_policy': fields.String(description='backup eligibility policy', enum=['optional', 'require', 'deny']),
    'passkey_backup_state_policy': fields.String(description='backup state policy', enum=['optional', 'require', 'deny']),
    'passkey_require_sign_count_increase': fields.Boolean(description='require a strictly increasing signature counter at every login'),
    'passkey_attestation_policy': fields.String(description='authenticator attestation policy', enum=['optional', 'require', 'deny']),
    'passkey_device_bound': fields.Boolean(description='require device-bound passkeys'),
    'passkey_resident_key': fields.String(description='resident passkey preference', enum=['discouraged', 'preferred', 'required']),
    'alternatives': fields.List(fields.String(attribute='name', description='FQDN'), example='["example.com"]'),
})

domain_fields_update = api.model('DomainUpdate', {
    'comment': fields.String(description='a comment'),
    'max_users': fields.Integer(description='maximum number of users', min=-1, default=-1),
    'max_aliases': fields.Integer(description='maximum number of aliases', min=-1, default=-1),
    'max_quota_bytes': fields.Integer(description='maximum quota for mailbox', min=0),
    'signup_enabled': fields.Boolean(description='allow signup'),
    'passkey_enforce_aaguid': fields.Boolean(description='enforce the domain AAGUID policy'),
    'passkey_aaguid_mode': fields.String(description='Whether listed passkey AAGUIDs are allowed or blocked', enum=['allow', 'block']),
    'passkey_aaguids': fields.String(description='Comma or newline separated passkey AAGUID UUIDs'),
    'passkey_require_uv': fields.Boolean(description='require user verification for passkeys'),
    'passkey_backup_eligible_policy': fields.String(description='backup eligibility policy', enum=['optional', 'require', 'deny']),
    'passkey_backup_state_policy': fields.String(description='backup state policy', enum=['optional', 'require', 'deny']),
    'passkey_require_sign_count_increase': fields.Boolean(description='require a strictly increasing signature counter at every login'),
    'passkey_attestation_policy': fields.String(description='authenticator attestation policy', enum=['optional', 'require', 'deny']),
    'passkey_device_bound': fields.Boolean(description='require device-bound passkeys'),
    'passkey_resident_key': fields.String(description='resident passkey preference', enum=['discouraged', 'preferred', 'required']),
    'alternatives': fields.List(fields.String(attribute='name', description='FQDN'), example='["example.com"]'),
})

domain_fields_get = api.model('DomainGet', {
    'name': fields.String(description='FQDN (e.g. example.com)', example='example.com', required=True),
    'comment': fields.String(description='a comment'),
    'managers': fields.List(fields.String(attribute='email', description='manager of domain')),
    'max_users': fields.Integer(description='maximum number of users', min=-1, default=-1),
    'max_aliases': fields.Integer(description='maximum number of aliases', min=-1, default=-1),
    'max_quota_bytes': fields.Integer(description='maximum quota for mailbox', min=0),
    'signup_enabled': fields.Boolean(description='allow signup'),
    'passkey_enforce_aaguid': fields.Boolean(description='enforce the domain AAGUID policy'),
    'passkey_aaguid_mode': fields.String(description='Whether listed passkey AAGUIDs are allowed or blocked', enum=['allow', 'block']),
    'passkey_aaguids': fields.String(description='Comma or newline separated passkey AAGUID UUIDs'),
    'passkey_require_uv': fields.Boolean(description='require user verification for passkeys'),
    'passkey_backup_eligible_policy': fields.String(description='backup eligibility policy', enum=['optional', 'require', 'deny']),
    'passkey_backup_state_policy': fields.String(description='backup state policy', enum=['optional', 'require', 'deny']),
    'passkey_require_sign_count_increase': fields.Boolean(description='require a strictly increasing signature counter at every login'),
    'passkey_attestation_policy': fields.String(description='authenticator attestation policy', enum=['optional', 'require', 'deny']),
    'passkey_device_bound': fields.Boolean(description='require device-bound passkeys'),
    'passkey_resident_key': fields.String(description='resident passkey preference', enum=['discouraged', 'preferred', 'required']),
    'alternatives': fields.List(fields.String(attribute='name', description='FQDN'), example='["example.com"]'),
    'dns_autoconfig': fields.List(fields.String(description='DNS client auto-configuration entry')),
    'dns_mx': fields.String(Description='MX record for domain'),
    'dns_spf': fields.String(Description='SPF record for domain'),
    'dns_dkim': fields.String(Description='DKIM records for domain'),
    'dns_dmarc': fields.String(Description='DMARC record for domain'),
    'dns_dmarc_report': fields.String(Description='DMARC report record for domain'),
    'dns_tlsa': fields.List(fields.String(Description='TLSA records for domain')),
})

domain_fields_dns = api.model('DomainDNS', {
    'dns_autoconfig': fields.List(fields.String(description='DNS client auto-configuration entry')),
    'dns_mx': fields.String(Description='MX record for domain'),
    'dns_spf': fields.String(Description='SPF record for domain'),
    'dns_dkim': fields.String(Description='DKIM records for domain'),
    'dns_dmarc': fields.String(Description='DMARC record for domain'),
    'dns_dmarc_report': fields.String(Description='DMARC report record for domain'),
    'dns_tlsa': fields.List(fields.String(Description='TLSA records for domain')),
})


def _set_passkey_policy(domain, data):
    updates = {}
    if 'passkey_enforce_aaguid' in data:
        if not isinstance(data['passkey_enforce_aaguid'], bool):
            return 'passkey_enforce_aaguid must be a boolean'
        updates['passkey_enforce_aaguid'] = data['passkey_enforce_aaguid']
    if 'passkey_aaguid_mode' in data:
        if data['passkey_aaguid_mode'] not in ('allow', 'block'):
            return 'passkey_aaguid_mode must be "allow" or "block"'
        updates['passkey_aaguid_mode'] = data['passkey_aaguid_mode']
    if 'passkey_aaguids' in data:
        try:
            updates['passkey_aaguids'] = passkey_utils.normalize_aaguids(data['passkey_aaguids'])
        except (TypeError, ValueError):
            return 'passkey_aaguids must contain valid AAGUID UUIDs'
    for name in (
        'passkey_require_uv', 'passkey_device_bound',
        'passkey_require_sign_count_increase',
    ):
        if name in data:
            if not isinstance(data[name], bool):
                return f'{name} must be a boolean'
            updates[name] = data[name]
    for name in (
        'passkey_backup_eligible_policy', 'passkey_backup_state_policy',
        'passkey_attestation_policy',
    ):
        if name in data:
            if data[name] not in ('optional', 'require', 'deny'):
                return f'{name} must be optional, require, or deny'
            updates[name] = data[name]
    if 'passkey_resident_key' in data:
        if data['passkey_resident_key'] not in ('discouraged', 'preferred', 'required'):
            return 'passkey_resident_key must be discouraged, preferred, or required'
        updates['passkey_resident_key'] = data['passkey_resident_key']
    for name, value in updates.items():
        setattr(domain, name, value)
    return None

manager_fields = api.model('Manager', {
    'managers': fields.List(fields.String(attribute='email', description='manager of domain')),
})

manager_fields_create = api.model('ManagerCreate', {
    'user_email': fields.String(description='email address of manager', required=True),
})

alternative_fields_update = api.model('AlternativeDomainUpdate', {
    'domain': fields.String(description='domain FQDN', example='example.com', required=False),
})

alternative_fields = api.model('AlternativeDomain', {
    'name': fields.String(description='alternative FQDN', example='example2.com', required=True),
    'domain': fields.String(description='domain FQDN', example='example.com', required=True),
})

dkim_key_fields = api.model('DkimKey', {
    'id': fields.Integer(readOnly=True),
    'selector': fields.String(readOnly=True),
    'algorithm': fields.String(readOnly=True),
    'active': fields.Boolean(description='Whether Rspamd signs with this key'),
    'retired': fields.Boolean(description='Whether this key has been stopped and cannot be promoted again'),
    'dns_record': fields.String(readOnly=True),
})

dkim_key_create_fields = api.model('DkimKeyCreate', {
    'algorithm': fields.String(enum=['rsa', 'ed25519'], default='rsa'),
})

dkim_key_update_fields = api.model('DkimKeyUpdate', {
    'active': fields.Boolean(required=True, description='Enable or disable signing with this key'),
})


@dom.route('')
class Domains(Resource):
    @dom.doc('list_domain')
    @dom.marshal_with(domain_fields_get, as_list=True, skip_none=True, mask=None)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def get(self):
        """ List all domains """
        return models.Domain.query.all()

    @dom.doc('create_domain')
    @dom.expect(domain_fields)
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(409, 'Duplicate domain/alternative name', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def post(self):
        """ Create a new domain """
        data = api.payload
        if not validators.domain(data['name']):
            return { 'code': 400, 'message': f'Domain {data["name"]} is not a valid domain'}, 400

        if common.fqdn_in_use(data['name']):
            return { 'code': 409, 'message': f'Duplicate domain name {data["name"]}'}, 409
        if 'alternatives' in data:
            #check if duplicate alternatives are supplied
            if [x for x in data['alternatives'] if data['alternatives'].count(x) >= 2]:
                return { 'code': 409, 'message': f'Duplicate alternative domain names in request' }, 409
            for item in data['alternatives']:
                if common.fqdn_in_use(item):
                    return { 'code': 409, 'message': f'Duplicate alternative domain name {item}' }, 409
                if not validators.domain(item):
                    return { 'code': 400, 'message': f'Alternative domain {item} is not a valid domain'}, 400
            for item in data['alternatives']:
                alternative = models.Alternative(name=item, domain_name=data['name'])
                models.db.session.add(alternative)
        domain_new = models.Domain(name=data['name'])
        if error := _set_passkey_policy(domain_new, data):
            return {'code': 400, 'message': error}, 400
        if 'comment' in data:
            domain_new.comment = data['comment']
        if 'max_users' in data:
            domain_new.max_users = data['max_users']
        if 'max_aliases' in data:
            domain_new.max_aliases = data['max_aliases']
        if 'max_quota_bytes' in data:
            domain_new.max_quota_bytes = data['max_quota_bytes']
        if 'signup_enabled' in data:
            domain_new.signup_enabled = data['signup_enabled']
        models.db.session.add(domain_new)
        #apply the changes
        db.session.commit()
        return  {'code': 200, 'message': f'Domain {data["name"]} has been created'}, 200

@dom.route('/<domain>')
class Domain(Resource):

    @dom.doc('find_domain')
    @dom.response(200, 'Success', domain_fields_get)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'Domain not found', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, domain):
        """ Look up the specified domain """
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 200
        domain_found = models.db.session.get(models.Domain, domain)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        return marshal(domain_found, domain_fields_get), 200

    @dom.doc('update_domain')
    @dom.expect(domain_fields_update)
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'Domain not found', response_fields)
    @dom.response(409, 'Duplicate domain/alternative name', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def patch(self, domain):
        """ Update the specified domain """
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain_found = models.db.session.get(models.Domain, domain)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        data = api.payload

        if 'alternatives' in data:
            #check if duplicate alternatives are supplied
            if [x for x in data['alternatives'] if data['alternatives'].count(x) >= 2]:
                return { 'code': 409, 'message': f'Duplicate alternative domain names in request' }, 409
            for item in data['alternatives']:
                if common.fqdn_in_use(item):
                    return { 'code': 409, 'message': f'Duplicate alternative domain name {item}' }, 409
                if not validators.domain(item):
                    return { 'code': 400, 'message': f'Alternative domain {item} is not a valid domain'}, 400
            for item in data['alternatives']:
                alternative = models.Alternative(name=item, domain_name=domain)
                models.db.session.add(alternative)

        if 'comment' in data:
            domain_found.comment = data['comment']
        if 'max_users' in data:
            domain_found.max_users = data['max_users']
        if 'max_aliases' in data:
            domain_found.max_aliases = data['max_aliases']
        if 'max_quota_bytes' in data:
            domain_found.max_quota_bytes = data['max_quota_bytes']
        if 'signup_enabled' in data:
            domain_found.signup_enabled = data['signup_enabled']
        if error := _set_passkey_policy(domain_found, data):
            return {'code': 400, 'message': error}, 400
        models.db.session.add(domain_found)

        #apply the changes
        db.session.commit()
        return  {'code': 200, 'message': f'Domain {domain} has been updated'}, 200

    @dom.doc('delete_domain')
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'Domain not found', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, domain):
        """ Delete the specified domain """
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain_found = models.db.session.get(models.Domain, domain)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        db.session.delete(domain_found)
        db.session.commit()
        return {'code': 200, 'message': f'Domain {domain} has been deleted'}, 200

@dom.route('/<domain>/dkim')
class Domain(Resource):
    @dom.doc('list_dkim_keys')
    @dom.marshal_with(dkim_key_fields, as_list=True)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, domain):
        """List signing and staged DKIM keys."""
        if not validators.domain(domain):
            return {'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain_found = models.db.session.get(models.Domain, domain)
        if not domain_found:
            return {'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        return [{'id': key.id, 'selector': key.selector, 'algorithm': key.algorithm,
            'active': key.active, 'retired': key.retired, 'dns_record': key.dns_record(domain_found.name)}
            for key in domain_found.dkim_keys]

    @dom.doc('generate_dkim')
    @dom.expect(dkim_key_create_fields, validate=False)
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'Domain not found', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def post(self, domain):
        """ Generate new DKIM/DMARC keys for the specified domain """
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain_found = models.db.session.get(models.Domain, domain)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        payload = request.get_data(cache=True)
        if payload and not request.is_json:
            return {'code': 415, 'message': 'A JSON request body is required'}, 415
        data = request.get_json() if payload else {}
        algorithm = data.get('algorithm', 'rsa')
        if algorithm not in ('rsa', 'ed25519'):
            return {'code': 400, 'message': 'algorithm must be rsa or ed25519'}, 400
        domain_found.generate_dkim_key(algorithm=algorithm, active=False)
        models.db.session.commit()
        return {'code': 200, 'message': f'Staged {algorithm} DKIM key for domain {domain}'}, 200


@dom.route('/<domain>/dkim/<int:key_id>')
class DomainDkimKey(Resource):
    @dom.doc('update_dkim_key')
    @dom.expect(dkim_key_update_fields)
    @dom.response(200, 'Success', response_fields)
    @dom.response(404, 'Domain or key not found', response_fields)
    @dom.response(409, 'A retired key cannot be promoted again', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def patch(self, domain, key_id):
        """Promote a staged key or retire an active key."""
        domain_found = models.db.session.get(models.Domain, domain)
        key = models.db.session.get(models.DkimKey, key_id)
        if not domain_found or not key or key.domain_name != domain_found.name:
            return {'code': 404, 'message': 'Domain or DKIM key not found'}, 404
        active = bool(api.payload['active'])
        if active and key.retired:
            return {'code': 409, 'message': 'A retired DKIM key cannot be promoted again'}, 409
        key.active = active
        if not active:
            key.retired = True
        models.db.session.commit()
        action = 'enabled' if key.active else 'disabled'
        return {'code': 200, 'message': f'DKIM signing {action} for selector {key.selector}'}, 200

    @dom.doc('delete_dkim_key')
    @dom.response(200, 'Success', response_fields)
    @dom.response(404, 'Domain or key not found', response_fields)
    @dom.response(409, 'An active key cannot be deleted', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, domain, key_id):
        """Delete an inactive DKIM key and its DNS record."""
        domain_found = models.db.session.get(models.Domain, domain)
        key = models.db.session.get(models.DkimKey, key_id)
        if not domain_found or not key or key.domain_name != domain_found.name:
            return {'code': 404, 'message': 'Domain or DKIM key not found'}, 404
        if key.active:
            return {'code': 409, 'message': 'Stop signing with this key before deleting it'}, 409
        models.db.session.delete(key)
        models.db.session.commit()
        return {'code': 200, 'message': f'DKIM key {key_id} has been deleted'}, 200

@dom.route('/<domain>/manager')
class Manager(Resource):
    @dom.doc('list_managers')
    @dom.response(200, 'Success', manager_fields)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'domain not found', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, domain):
        """ List all managers of the specified domain """
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain_found = models.db.session.get(models.Domain, domain)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        return marshal(domain_found, manager_fields), 200

    @dom.doc('create_manager')
    @dom.expect(manager_fields_create)
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'User or domain not found', response_fields)
    @dom.response(409, 'Duplicate domain manager', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def post(self, domain):
        """ Create a new domain manager for the specified domain """
        data = api.payload
        if not utils.is_valid_email(data['user_email']):
            return {'code': 400, 'message': f'Invalid email address {data["user_email"]}'}, 400
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain = models.db.session.get(models.Domain, domain)
        if not domain:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        user = models.db.session.get(models.User, data['user_email'])
        if not user:
            return { 'code': 404, 'message': f'User {data["user_email"]} does not exist'}, 404
        if user in domain.managers:
            return {'code': 409, 'message': f'User {data["user_email"]} is already a manager of the domain {domain} '}, 409
        domain.managers.append(user)
        models.db.session.commit()
        return {'code': 200, 'message': f'User {data["user_email"]} has been added as manager of the domain {domain} '},200

@dom.route('/<domain>/manager/<email>')
class Domain(Resource):
    @dom.doc('find_manager')
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'Manager not found', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, domain, email):
        """ Check if the specified user is a manager of the specified domain """
        if not utils.is_valid_email(email):
            return {'code': 400, 'message': f'Invalid email address {email}'}, 400
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain = models.db.session.get(models.Domain, domain)
        if not domain:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        user = models.db.session.get(models.User, email)
        if not user:
            return { 'code': 404, 'message': f'User {email} does not exist'}, 404
        if user in domain.managers:
            for manager in domain.managers:
                if manager.email == email:
                    return { 'code': 200, 'message': f'User {email} is a manager of the domain {domain}'}, 200
        else:
            return { 'code': 404, 'message': f'User {email} is not a manager of the domain {domain}'}, 404


    @dom.doc('delete_manager')
    @dom.response(200, 'Success', response_fields)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'Manager not found', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, domain, email):
        """ Delete the specified manager of the specified domain """
        if not utils.is_valid_email(email):
            return {'code': 400, 'message': f'Invalid email address {email}'}, 400
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain = models.db.session.get(models.Domain, domain)
        if not domain:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        user = models.db.session.get(models.User, email)
        if not user:
            return { 'code': 404, 'message': f'User {email} does not exist'}, 404
        if user in domain.managers:
            domain.managers.remove(user)
            models.db.session.commit()
            return {'code': 200, 'message': f'User {email} has been removed as a manager of the domain {domain} '},200
        else:
            return { 'code': 404, 'message': f'User {email} is not a manager of the domain {domain}'}, 404

@dom.route('/<domain>/users')
class User(Resource):
    @dom.doc('list_user_domain')
    @dom.response(200, 'Success', user.user_fields_get)
    @dom.response(400, 'Input validation exception', response_fields)
    @dom.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @dom.response(404, 'Domain not found', response_fields)
    @dom.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, domain):
        """ List all the users from the specified domain """
        if not validators.domain(domain):
            return { 'code': 400, 'message': f'Domain {domain} is not a valid domain'}, 400
        domain_found = models.db.session.get(models.Domain, domain)
        if not domain_found:
            return { 'code': 404, 'message': f'Domain {domain} does not exist'}, 404
        return  marshal(models.User.query.filter_by(domain=domain_found).all(), user.user_fields_get),200

@alt.route('')
class Alternatives(Resource):

    @alt.doc('list_alternative')
    @alt.marshal_with(alternative_fields, as_list=True, skip_none=True, mask=None)
    @alt.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alt.doc(security='Bearer')
    @common.api_token_authorization
    def get(self):
      """ List all alternatives """
      return models.Alternative.query.all()


    @alt.doc('create_alternative')
    @alt.expect(alternative_fields)
    @alt.response(200, 'Success', response_fields)
    @alt.response(400, 'Input validation exception', response_fields)
    @alt.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alt.response(404, 'Domain not found or missing', response_fields)
    @alt.response(409, 'Duplicate alternative domain name', response_fields)
    @alt.doc(security='Bearer')
    @common.api_token_authorization
    def post(self):
        """ Create a new alternative (for domain) """
        data = api.payload
        if not validators.domain(data['name']):
            return { 'code': 400, 'message': f'Alternative domain {data["name"]} is not a valid domain'}, 400
        if not validators.domain(data['domain']):
            return { 'code': 400, 'message': f'Domain {data["domain"]} is not a valid domain'}, 400
        domain = models.db.session.get(models.Domain, data['domain'])
        if not domain:
            return { 'code': 404, 'message': f'Domain {data["domain"]} does not exist'}, 404
        if common.fqdn_in_use(data['name']):
            return { 'code': 409, 'message': f'Duplicate alternative domain name {data["name"]}'}, 409

        alternative = models.Alternative(name=data['name'], domain_name=data['domain'])
        models.db.session.add(alternative)
        db.session.commit()
        return {'code': 200, 'message': f'Alternative {data["name"]} for domain {data["domain"]} has been created'}, 200

@alt.route('/<string:alt>')
class Alternative(Resource):
    @alt.doc('find_alternative')
    @alt.doc(security='Bearer')
    @alt.response(200, 'Success', alternative_fields)
    @alt.response(400, 'Input validation exception', response_fields)
    @alt.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alt.response(404, 'Alternative not found or missing', response_fields)
    @common.api_token_authorization
    def get(self, alt):
        """ Look up the specified alternative (of domain) """
        if not validators.domain(alt):
            return { 'code': 400, 'message': f'Alternative domain {alt} is not a valid domain'}, 400
        alternative = models.Alternative.query.filter_by(name=alt).first()
        if not alternative:
            return{ 'code': 404, 'message': f'Alternative domain {alt} does not exist'}, 404
        return marshal(alternative, alternative_fields), 200

    @alt.doc('delete_alternative')
    @alt.response(200, 'Success', response_fields)
    @alt.response(400, 'Input validation exception', response_fields)
    @alt.doc(responses={401: 'Authorization header missing', 403: 'Invalid authorization header'})
    @alt.response(404, 'Alternative/Domain not found or missing', response_fields)
    @alt.response(409, 'Duplicate domain name', response_fields)
    @alt.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, alt):
        """ Delete the specified alternative (for domain) """
        if not validators.domain(alt):
            return { 'code': 400, 'message': f'Alternative domain {alt} is not a valid domain'}, 400
        alternative = models.Alternative.query.filter_by(name=alt).scalar()
        if not alternative:
            return { 'code': 404, 'message': f'Alternative domain {alt} does not exist'}, 404
        domain = alternative.domain_name
        db.session.delete(alternative)
        db.session.commit()
        return {'code': 200, 'message': f'Alternative {alt} for domain {domain} has been deleted'}, 200


@alt.route('/<string:alt>/dkim')
class AlternativeDkimKeys(Resource):
    @alt.marshal_with(dkim_key_fields, as_list=True)
    @alt.doc(security='Bearer')
    @common.api_token_authorization
    def get(self, alt):
        """List keys shared by an alternative and its parent domain."""
        alternative = models.db.session.get(models.Alternative, alt)
        if not alternative:
            return {'code': 404, 'message': f'Alternative domain {alt} does not exist'}, 404
        return [{'id': key.id, 'selector': key.selector, 'algorithm': key.algorithm,
            'active': key.active, 'retired': key.retired, 'dns_record': key.dns_record(alternative.name)}
            for key in alternative.domain.dkim_keys]

    @alt.expect(dkim_key_create_fields)
    @alt.response(200, 'Success', response_fields)
    @alt.doc(security='Bearer')
    @common.api_token_authorization
    def post(self, alt):
        """Generate a staged key shared by the alternative and its parent domain."""
        alternative = models.db.session.get(models.Alternative, alt)
        if not alternative:
            return {'code': 404, 'message': f'Alternative domain {alt} does not exist'}, 404
        algorithm = (api.payload or {}).get('algorithm', 'rsa')
        if algorithm not in ('rsa', 'ed25519'):
            return {'code': 400, 'message': 'algorithm must be rsa or ed25519'}, 400
        alternative.domain.generate_dkim_key(algorithm=algorithm, active=False)
        models.db.session.commit()
        return {'code': 200, 'message': f'Staged {algorithm} DKIM key for alternative {alt}'}, 200


@alt.route('/<string:alt>/dkim/<int:key_id>')
class AlternativeDkimKey(Resource):
    @alt.expect(dkim_key_update_fields)
    @alt.response(200, 'Success', response_fields)
    @alt.response(404, 'Alternative or key not found', response_fields)
    @alt.response(409, 'A retired key cannot be promoted again', response_fields)
    @alt.doc(security='Bearer')
    @common.api_token_authorization
    def patch(self, alt, key_id):
        """Promote a staged key or retire an active key shared with the parent domain."""
        alternative = models.db.session.get(models.Alternative, alt)
        key = models.db.session.get(models.DkimKey, key_id)
        if not alternative or not key or key.domain_name != alternative.domain_name:
            return {'code': 404, 'message': 'Alternative or DKIM key not found'}, 404
        active = bool(api.payload['active'])
        if active and key.retired:
            return {'code': 409, 'message': 'A retired DKIM key cannot be promoted again'}, 409
        key.active = active
        if not active:
            key.retired = True
        models.db.session.commit()
        action = 'enabled' if key.active else 'disabled'
        return {'code': 200, 'message': f'DKIM signing {action} for selector {key.selector}'}, 200

    @alt.response(200, 'Success', response_fields)
    @alt.response(404, 'Alternative or key not found', response_fields)
    @alt.response(409, 'An active key cannot be deleted', response_fields)
    @alt.doc(security='Bearer')
    @common.api_token_authorization
    def delete(self, alt, key_id):
        """Delete an inactive key shared with the alternative's parent domain."""
        alternative = models.db.session.get(models.Alternative, alt)
        key = models.db.session.get(models.DkimKey, key_id)
        if not alternative or not key or key.domain_name != alternative.domain_name:
            return {'code': 404, 'message': 'Alternative or DKIM key not found'}, 404
        if key.active:
            return {'code': 409, 'message': 'Stop signing with this key before deleting it'}, 409
        models.db.session.delete(key)
        models.db.session.commit()
        return {'code': 200, 'message': f'DKIM key {key_id} has been deleted'}, 200
