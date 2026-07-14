import secrets

import flask
import validators

from . import common
from .. import models


SCIM_USER_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:User'
SCIM_GROUP_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Group'
SCIM_LIST_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:ListResponse'
SCIM_PATCH_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:PatchOp'
SCIM_ERROR_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:Error'

blueprint = flask.Blueprint('scim', __name__)


def _base_url():
    web_api_root = flask.current_app.config.get('WEB_API') or '/api'
    return flask.request.url_root.rstrip('/') + web_api_root.rstrip('/') + '/scim/v2'


def _resource_location(resource, resource_id):
    return f'{_base_url()}/{resource}/{resource_id}'


def _scim_response(payload, status=200):
    response = flask.jsonify(payload)
    response.status_code = status
    response.headers['Content-Type'] = 'application/scim+json'
    return response


def _scim_error(status, detail, scim_type=None):
    payload = {
        'schemas': [SCIM_ERROR_SCHEMA],
        'status': str(status),
        'detail': detail,
    }
    if scim_type:
        payload['scimType'] = scim_type
    return _scim_response(payload, status)


def _payload():
    data = flask.request.get_json(silent=True)
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, _scim_error(400, 'Request body must be a JSON object', 'invalidSyntax')
    return data, None


def _parse_positive_int(value, default, *, minimum=0):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(parsed, minimum)


def _string_value(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


def _active_value(value):
    if isinstance(value, bool):
        return value, None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == 'true':
            return True, None
        if lowered == 'false':
            return False, None
    return None, _scim_error(400, 'active must be a boolean', 'invalidValue')


def _user_email(data):
    user_name = _string_value(data.get('userName')).strip().lower()
    if user_name:
        return user_name
    for email in data.get('emails') or []:
        if not isinstance(email, dict):
            continue
        value = _string_value(email.get('value')).strip().lower()
        if value:
            return value
    return ''


def _display_name(data):
    if data.get('displayName') is not None:
        display_name = _string_value(data.get('displayName')).strip()
        if display_name:
            return display_name
    name = data.get('name') or {}
    if not isinstance(name, dict):
        return ''
    formatted = _string_value(name.get('formatted')).strip()
    if formatted:
        return formatted
    parts = [_string_value(name.get('givenName')).strip(), _string_value(name.get('familyName')).strip()]
    return ' '.join(part for part in parts if part)


def _get_user(user_id):
    return models.db.session.get(models.User, user_id.lower())


def _make_user_resource(user):
    email = user.email
    payload = {
        'schemas': [SCIM_USER_SCHEMA],
        'id': email,
        'externalId': email,
        'userName': email,
        'active': user.enabled,
        'displayName': user.displayed_name or email,
        'name': {
            'formatted': user.displayed_name or email,
        },
        'emails': [{
            'value': email,
            'primary': True,
            'type': 'work',
        }],
        'meta': {
            'resourceType': 'User',
            'location': _resource_location('Users', email),
        },
    }
    return payload


def _validate_user_domain(email):
    if not validators.email(email):
        return None, _scim_error(400, f'{email!r} is not a valid email address', 'invalidValue')
    localpart, domain_name = email.rsplit('@', 1)
    domain = models.db.session.get(models.Domain, domain_name)
    if not domain:
        return None, _scim_error(404, f'Domain {domain_name} does not exist')
    if domain.max_users != -1 and len(domain.users) >= domain.max_users:
        return None, _scim_error(409, f'Too many users for domain {domain_name}', 'uniqueness')
    return (localpart, domain), None


def _apply_user_data(user, data, *, replacing=False):
    if replacing:
        if 'active' in data:
            active, error = _active_value(data['active'])
            if error:
                return error
            user.enabled = active
        else:
            user.enabled = True
    elif 'active' in data:
        active, error = _active_value(data['active'])
        if error:
            return error
        user.enabled = active

    display_name = _display_name(data)
    if display_name:
        user.displayed_name = display_name
    if data.get('password'):
        user.set_password(data['password'])
    return None


def _patch_user(user, data):
    operations = data.get('Operations') or data.get('operations') or []
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax')
    for operation in operations:
        if not isinstance(operation, dict):
            return _scim_error(400, 'Patch operations must be objects', 'invalidSyntax')
        op = _string_value(operation.get('op') or 'replace').lower()
        path = _string_value(operation.get('path')).lower()
        value = operation.get('value')
        if op not in ('add', 'replace'):
            continue
        if path in ('active', '') and (path or isinstance(value, dict)):
            if path == 'active':
                active, error = _active_value(value)
                if error:
                    return error
                user.enabled = active
            elif isinstance(value, dict) and 'active' in value:
                active, error = _active_value(value['active'])
                if error:
                    return error
                user.enabled = active
        if path in ('displayname', '') and (path or isinstance(value, dict)):
            if path == 'displayname' and value is not None:
                user.displayed_name = _string_value(value)
            elif isinstance(value, dict):
                display_name = _display_name(value)
                if display_name:
                    user.displayed_name = display_name
        if path in ('name.formatted', 'name', '') and value:
            if path == 'name.formatted':
                user.displayed_name = _string_value(value)
            elif path == 'name' and isinstance(value, dict) and value.get('formatted'):
                user.displayed_name = value['formatted']
        if path in ('password', ''):
            if path == 'password' and value:
                user.set_password(_string_value(value))
            elif isinstance(value, dict) and value.get('password'):
                user.set_password(value['password'])
    return None


@blueprint.before_request
def authorize():
    if flask.request.method == 'OPTIONS':
        return None

    @common.api_token_authorization
    def _authorized():
        return None

    return _authorized()


@blueprint.route('/ServiceProviderConfig', methods=['GET'])
def service_provider_config():
    return _scim_response({
        'schemas': ['urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig'],
        'patch': {'supported': True},
        'bulk': {'supported': False, 'maxOperations': 0, 'maxPayloadSize': 0},
        'filter': {'supported': True, 'maxResults': 200},
        'changePassword': {'supported': True},
        'sort': {'supported': False},
        'etag': {'supported': False},
        'authenticationSchemes': [{
            'type': 'oauthbearertoken',
            'name': 'Bearer',
            'description': 'Mailu API_TOKEN bearer authentication',
            'primary': True,
        }],
        'meta': {'resourceType': 'ServiceProviderConfig'},
    })


@blueprint.route('/ResourceTypes', methods=['GET'])
def resource_types():
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': 1,
        'startIndex': 1,
        'itemsPerPage': 1,
        'Resources': [{
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:ResourceType'],
            'id': 'User',
            'name': 'User',
            'endpoint': '/Users',
            'schema': SCIM_USER_SCHEMA,
            'meta': {'resourceType': 'ResourceType', 'location': _resource_location('ResourceTypes', 'User')},
        }],
    })


@blueprint.route('/Schemas', methods=['GET'])
def schemas():
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': 1,
        'startIndex': 1,
        'itemsPerPage': 1,
        'Resources': [{
            'id': SCIM_USER_SCHEMA,
            'name': 'User',
            'description': 'Mailu SCIM user schema subset',
            'attributes': [],
            'meta': {'resourceType': 'Schema', 'location': _resource_location('Schemas', SCIM_USER_SCHEMA)},
        }],
    })


@blueprint.route('/Groups', methods=['GET'])
def list_groups():
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': 0,
        'startIndex': 1,
        'itemsPerPage': 0,
        'Resources': [],
    })


@blueprint.route('/Groups', methods=['POST'])
@blueprint.route('/Groups/<path:group_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def unsupported_groups(group_id=None):
    return _scim_error(501, 'Mailu SCIM currently provisions users only; groups are not supported')


@blueprint.route('/Users', methods=['GET'])
def list_users():
    start_index = _parse_positive_int(flask.request.args.get('startIndex', 1), 1, minimum=1)
    count = _parse_positive_int(flask.request.args.get('count', 100), 100, minimum=0)
    if start_index is None or count is None:
        return _scim_error(400, 'startIndex and count must be integers', 'invalidValue')
    query = models.User.query.order_by(models.User._email)

    filter_value = flask.request.args.get('filter')
    if filter_value:
        prefix = 'userName eq '
        if not filter_value.startswith(prefix):
            return _scim_error(400, 'Only userName eq filters are supported', 'invalidFilter')
        email = filter_value[len(prefix):].strip().strip('"').lower()
        query = query.filter_by(email=email)

    total = query.count()
    users = query.offset(start_index - 1).limit(count).all() if count else []
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': total,
        'startIndex': start_index,
        'itemsPerPage': len(users),
        'Resources': [_make_user_resource(user) for user in users],
    })


@blueprint.route('/Users', methods=['POST'])
def create_user():
    data, error = _payload()
    if error:
        return error
    email = _user_email(data)
    if not email:
        return _scim_error(400, 'userName or emails[0].value is required', 'invalidValue')
    if _get_user(email):
        return _scim_error(409, f'User {email} already exists', 'uniqueness')
    domain_data, error = _validate_user_domain(email)
    if error:
        return error
    localpart, domain = domain_data
    user = models.User(localpart=localpart, domain=domain)
    user.set_password(data.get('password') or secrets.token_urlsafe())
    error = _apply_user_data(user, data, replacing=True)
    if error:
        return error
    models.db.session.add(user)
    models.db.session.commit()
    return _scim_response(_make_user_resource(user), 201)


@blueprint.route('/Users/<path:user_id>', methods=['GET'])
def get_user(user_id):
    user = _get_user(user_id)
    if not user:
        return _scim_error(404, f'User {user_id} cannot be found')
    return _scim_response(_make_user_resource(user))


@blueprint.route('/Users/<path:user_id>', methods=['PUT'])
def replace_user(user_id):
    user = _get_user(user_id)
    if not user:
        return _scim_error(404, f'User {user_id} cannot be found')
    data, error = _payload()
    if error:
        return error
    new_email = _user_email(data)
    if new_email and new_email != user.email:
        return _scim_error(400, 'Changing userName/email is not supported', 'mutability')
    error = _apply_user_data(user, data, replacing=True)
    if error:
        return error
    models.db.session.add(user)
    models.db.session.commit()
    return _scim_response(_make_user_resource(user))


@blueprint.route('/Users/<path:user_id>', methods=['PATCH'])
def patch_user(user_id):
    user = _get_user(user_id)
    if not user:
        return _scim_error(404, f'User {user_id} cannot be found')
    data, error = _payload()
    if error:
        return error
    error = _patch_user(user, data)
    if error:
        return error
    models.db.session.add(user)
    models.db.session.commit()
    return _scim_response(_make_user_resource(user))


@blueprint.route('/Users/<path:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = _get_user(user_id)
    if not user:
        return '', 204
    user.enabled = False
    models.db.session.add(user)
    models.db.session.commit()
    return '', 204
