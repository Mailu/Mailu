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
SCIM_BULK_REQUEST_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:BulkRequest'
SCIM_BULK_RESPONSE_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:BulkResponse'

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


def _response_payload(response):
    if isinstance(response, tuple):
        response = response[0]
    if response.status_code == 204:
        return None
    return response.get_json(silent=True)


def _resource_version(resource):
    value = getattr(resource, 'updated_at', None) or getattr(resource, 'created_at', None)
    if not value:
        return None
    return f'W/"{value.isoformat()}"'


def _resource_meta(resource_type, collection, resource_id, model):
    meta = {
        'resourceType': resource_type,
        'location': _resource_location(collection, resource_id),
    }
    if getattr(model, 'created_at', None):
        meta['created'] = model.created_at.isoformat()
    version = _resource_version(model)
    if version:
        meta['version'] = version
    return meta


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
        if flask.request.get_data(cache=True).strip():
            return None, _scim_error(400, 'Request body must be valid JSON', 'invalidSyntax')
        return {}, None
    if not isinstance(data, dict):
        return None, _scim_error(400, 'Request body must be a JSON object', 'invalidSyntax')
    return data, None


def _parse_positive_int(value, default, *, minimum=0, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _string_value(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


def _password_value(value):
    if value in (None, ''):
        return None, None
    if not isinstance(value, str):
        return None, _scim_error(400, 'password must be a string', 'invalidValue')
    return value, None


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
    user_name = data.get('userName')
    if user_name not in (None, ''):
        if not isinstance(user_name, str):
            return None, _scim_error(400, 'userName must be a string', 'invalidValue')
        user_name = user_name.strip().lower()
        if user_name:
            return user_name, None

    emails = data.get('emails') or []
    if not isinstance(emails, list):
        return None, _scim_error(400, 'emails must be a list', 'invalidValue')
    for email in emails:
        if not isinstance(email, dict):
            continue
        value = email.get('value')
        if value in (None, ''):
            continue
        if not isinstance(value, str):
            return None, _scim_error(400, 'email values must be strings', 'invalidValue')
        value = value.strip().lower()
        if value:
            return value, None
    return '', None


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
        'meta': _resource_meta('User', 'Users', email, user),
    }
    return payload


def _get_group(group_id):
    return models.db.session.get(models.Alias, group_id.lower())


def _member_values(data):
    members = data.get('members', [])
    if members in (None, ''):
        return [], None
    if not isinstance(members, list):
        return None, _scim_error(400, 'members must be a list', 'invalidValue')
    values = []
    for member in members:
        if isinstance(member, str):
            value = member
        elif isinstance(member, dict):
            value = member.get('value')
        else:
            return None, _scim_error(400, 'members must contain strings or objects', 'invalidValue')
        if not isinstance(value, str) or not value.strip():
            return None, _scim_error(400, 'member values must be non-empty strings', 'invalidValue')
        value = value.strip().lower()
        if not validators.email(value):
            return None, _scim_error(400, f'{value!r} is not a valid member email address', 'invalidValue')
        if value not in values:
            values.append(value)
    return values, None


def _group_email(data):
    for key in ('id', 'displayName'):
        value = data.get(key)
        if value not in (None, ''):
            if not isinstance(value, str):
                return None, _scim_error(400, f'{key} must be a string', 'invalidValue')
            return value.strip().lower(), None
    return '', None


def _make_group_resource(group):
    email = group.email
    return {
        'schemas': [SCIM_GROUP_SCHEMA],
        'id': email,
        'displayName': group.comment or email,
        'members': [{
            'value': destination,
            'display': destination,
            '$ref': _resource_location('Users', destination),
        } for destination in group.destination],
        'meta': _resource_meta('Group', 'Groups', email, group),
    }


def _validate_alias_domain(email):
    if not validators.email(email):
        return None, _scim_error(400, f'{email!r} is not a valid email address', 'invalidValue')
    localpart, domain_name = email.rsplit('@', 1)
    domain = models.db.session.get(models.Domain, domain_name)
    if not domain:
        return None, _scim_error(404, f'Domain {domain_name} does not exist')
    if domain.max_aliases != -1 and len(domain.aliases) >= domain.max_aliases:
        return None, _scim_error(409, f'Too many aliases for domain {domain_name}', 'uniqueness')
    return (localpart, domain), None


def _apply_group_data(group, data, *, replacing=False):
    if 'displayName' in data and data.get('displayName') != group.email:
        group.comment = _string_value(data.get('displayName')).strip()
    if replacing or 'members' in data:
        members, error = _member_values(data)
        if error:
            return error
        group.destination = members
    return None


def _patch_group(group, data):
    operations = data['Operations'] if 'Operations' in data else data.get('operations')
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax')
    if not operations:
        return _scim_error(400, 'Operations must not be empty', 'invalidValue')
    for operation in operations:
        if not isinstance(operation, dict):
            return _scim_error(400, 'Patch operations must be objects', 'invalidSyntax')
        op = _string_value(operation.get('op') or 'replace').lower()
        path = _string_value(operation.get('path')).lower()
        value = operation.get('value')
        if op not in ('add', 'replace', 'remove'):
            return _scim_error(400, f'Patch operation {op!r} is not supported', 'mutability')
        if path in ('displayname', '') and op in ('add', 'replace'):
            if path == 'displayname':
                group.comment = _string_value(value).strip()
                continue
            if isinstance(value, dict) and 'displayName' in value:
                group.comment = _string_value(value.get('displayName')).strip()
                continue
        if path in ('members', ''):
            if path == 'members':
                member_data = {'members': value if isinstance(value, list) else [value]}
            elif isinstance(value, dict) and 'members' in value:
                member_data = {'members': value.get('members')}
            else:
                return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath')
            members, error = _member_values(member_data)
            if error:
                return error
            if op == 'remove':
                group.destination = [member for member in group.destination if member not in members]
            elif op == 'add':
                group.destination = group.destination + [member for member in members if member not in group.destination]
            else:
                group.destination = members
            continue
        return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath')
    return None


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
    password, error = _password_value(data.get('password'))
    if error:
        return error
    if password:
        user.set_password(password)
    return None


def _patch_user(user, data):
    if 'Operations' in data:
        operations = data['Operations']
    else:
        operations = data.get('operations')
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax')
    if not operations:
        return _scim_error(400, 'Operations must not be empty', 'invalidValue')
    for operation in operations:
        if not isinstance(operation, dict):
            return _scim_error(400, 'Patch operations must be objects', 'invalidSyntax')
        op = _string_value(operation.get('op') or 'replace').lower()
        path = _string_value(operation.get('path')).lower()
        value = operation.get('value')
        if op not in ('add', 'replace'):
            return _scim_error(400, f'Patch operation {op!r} is not supported', 'mutability')

        handled = False
        if path in ('active', '') and (path or isinstance(value, dict)):
            if path == 'active':
                active, error = _active_value(value)
                if error:
                    return error
                user.enabled = active
                handled = True
            elif isinstance(value, dict) and 'active' in value:
                active, error = _active_value(value['active'])
                if error:
                    return error
                user.enabled = active
                handled = True
        if path in ('displayname', '') and (path or isinstance(value, dict)):
            if path == 'displayname' and value is not None:
                user.displayed_name = _string_value(value)
                handled = True
            elif isinstance(value, dict):
                display_name = _display_name(value)
                if display_name:
                    user.displayed_name = display_name
                    handled = True
        if path in ('name.formatted', 'name', '') and value:
            if path == 'name.formatted':
                user.displayed_name = _string_value(value)
                handled = True
            elif path == 'name' and isinstance(value, dict) and value.get('formatted'):
                user.displayed_name = _string_value(value['formatted'])
                handled = True
        if path in ('password', ''):
            if path == 'password' and value:
                password, error = _password_value(value)
                if error:
                    return error
                user.set_password(password)
                handled = True
            elif isinstance(value, dict) and value.get('password'):
                password, error = _password_value(value['password'])
                if error:
                    return error
                user.set_password(password)
                handled = True
        if not handled:
            return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath')
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
        'bulk': {'supported': True, 'maxOperations': 100, 'maxPayloadSize': 1048576},
        'filter': {'supported': True, 'maxResults': 200},
        'changePassword': {'supported': True},
        'sort': {'supported': False},
        'etag': {'supported': True},
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
    resources = [
        {
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:ResourceType'],
            'id': 'User',
            'name': 'User',
            'endpoint': '/Users',
            'schema': SCIM_USER_SCHEMA,
            'meta': {'resourceType': 'ResourceType', 'location': _resource_location('ResourceTypes', 'User')},
        },
        {
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:ResourceType'],
            'id': 'Group',
            'name': 'Group',
            'endpoint': '/Groups',
            'schema': SCIM_GROUP_SCHEMA,
            'meta': {'resourceType': 'ResourceType', 'location': _resource_location('ResourceTypes', 'Group')},
        },
    ]
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': len(resources),
        'startIndex': 1,
        'itemsPerPage': len(resources),
        'Resources': resources,
    })


@blueprint.route('/Schemas', methods=['GET'])
def schemas():
    resources = [
        {
            'id': SCIM_USER_SCHEMA,
            'name': 'User',
            'description': 'Mailu SCIM user schema subset',
            'attributes': [],
            'meta': {'resourceType': 'Schema', 'location': _resource_location('Schemas', SCIM_USER_SCHEMA)},
        },
        {
            'id': SCIM_GROUP_SCHEMA,
            'name': 'Group',
            'description': 'Mailu SCIM group schema subset backed by aliases',
            'attributes': [],
            'meta': {'resourceType': 'Schema', 'location': _resource_location('Schemas', SCIM_GROUP_SCHEMA)},
        },
    ]
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': len(resources),
        'startIndex': 1,
        'itemsPerPage': len(resources),
        'Resources': resources,
    })


def _list_groups_response():
    start_index = _parse_positive_int(flask.request.args.get('startIndex', 1), 1, minimum=1)
    count = _parse_positive_int(flask.request.args.get('count', 100), 100, minimum=0, maximum=200)
    if start_index is None or count is None:
        return _scim_error(400, 'startIndex and count must be integers', 'invalidValue')
    query = models.Alias.query.order_by(models.Alias._email)

    filter_value = flask.request.args.get('filter')
    if filter_value:
        prefix = 'displayName eq '
        if not filter_value.startswith(prefix):
            return _scim_error(400, 'Only displayName eq filters are supported', 'invalidFilter')
        email = filter_value[len(prefix):].strip().strip('"').lower()
        query = query.filter_by(email=email)

    total = query.count()
    groups = query.offset(start_index - 1).limit(count).all() if count else []
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': total,
        'startIndex': start_index,
        'itemsPerPage': len(groups),
        'Resources': [_make_group_resource(group) for group in groups],
    })


def _create_group_response(data):
    email, error = _group_email(data)
    if error:
        return error
    if not email:
        return _scim_error(400, 'displayName is required', 'invalidValue')
    if _get_group(email):
        return _scim_error(409, f'Group {email} already exists', 'uniqueness')
    domain_data, error = _validate_alias_domain(email)
    if error:
        return error
    localpart, domain = domain_data
    group = models.Alias(localpart=localpart, domain=domain, destination=[])
    error = _apply_group_data(group, data, replacing=True)
    if error:
        return error
    models.db.session.add(group)
    models.db.session.commit()
    return _scim_response(_make_group_resource(group), 201)


def _get_group_response(group_id):
    group = _get_group(group_id)
    if not group:
        return _scim_error(404, f'Group {group_id} cannot be found')
    return _scim_response(_make_group_resource(group))


def _replace_group_response(group_id, data):
    group = _get_group(group_id)
    if not group:
        return _scim_error(404, f'Group {group_id} cannot be found')
    new_email, error = _group_email(data)
    if error:
        return error
    if new_email and new_email != group.email:
        return _scim_error(400, 'Changing group id/displayName is not supported', 'mutability')
    error = _apply_group_data(group, data, replacing=True)
    if error:
        return error
    models.db.session.add(group)
    models.db.session.commit()
    return _scim_response(_make_group_resource(group))


def _patch_group_response(group_id, data):
    group = _get_group(group_id)
    if not group:
        return _scim_error(404, f'Group {group_id} cannot be found')
    error = _patch_group(group, data)
    if error:
        return error
    models.db.session.add(group)
    models.db.session.commit()
    return _scim_response(_make_group_resource(group))


def _delete_group_response(group_id):
    group = _get_group(group_id)
    if not group:
        return '', 204
    models.db.session.delete(group)
    models.db.session.commit()
    return '', 204


@blueprint.route('/Groups', methods=['GET'])
def list_groups():
    return _list_groups_response()


@blueprint.route('/Groups', methods=['POST'])
def create_group():
    data, error = _payload()
    if error:
        return error
    return _create_group_response(data)


@blueprint.route('/Groups/<path:group_id>', methods=['GET'])
def get_group(group_id):
    return _get_group_response(group_id)


@blueprint.route('/Groups/<path:group_id>', methods=['PUT'])
def replace_group(group_id):
    data, error = _payload()
    if error:
        return error
    return _replace_group_response(group_id, data)


@blueprint.route('/Groups/<path:group_id>', methods=['PATCH'])
def patch_group(group_id):
    data, error = _payload()
    if error:
        return error
    return _patch_group_response(group_id, data)


@blueprint.route('/Groups/<path:group_id>', methods=['DELETE'])
def delete_group(group_id):
    return _delete_group_response(group_id)


@blueprint.route('/Users', methods=['GET'])
def list_users():
    start_index = _parse_positive_int(flask.request.args.get('startIndex', 1), 1, minimum=1)
    count = _parse_positive_int(flask.request.args.get('count', 100), 100, minimum=0, maximum=200)
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


def _create_user_response(data):
    email, error = _user_email(data)
    if error:
        return error
    if not email:
        return _scim_error(400, 'userName or emails[0].value is required', 'invalidValue')
    if _get_user(email):
        return _scim_error(409, f'User {email} already exists', 'uniqueness')
    domain_data, error = _validate_user_domain(email)
    if error:
        return error
    localpart, domain = domain_data
    password, error = _password_value(data.get('password'))
    if error:
        return error
    user = models.User(localpart=localpart, domain=domain)
    user.set_password(password or secrets.token_urlsafe())
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


def _replace_user_response(user_id, data):
    user = _get_user(user_id)
    if not user:
        return _scim_error(404, f'User {user_id} cannot be found')
    new_email, error = _user_email(data)
    if error:
        return error
    if new_email and new_email != user.email:
        return _scim_error(400, 'Changing userName/email is not supported', 'mutability')
    error = _apply_user_data(user, data, replacing=True)
    if error:
        return error
    models.db.session.add(user)
    models.db.session.commit()
    return _scim_response(_make_user_resource(user))


def _patch_user_response(user_id, data):
    user = _get_user(user_id)
    if not user:
        return _scim_error(404, f'User {user_id} cannot be found')
    error = _patch_user(user, data)
    if error:
        return error
    models.db.session.add(user)
    models.db.session.commit()
    return _scim_response(_make_user_resource(user))


def _delete_user_response(user_id):
    user = _get_user(user_id)
    if not user:
        return '', 204
    user.enabled = False
    models.db.session.add(user)
    models.db.session.commit()
    return '', 204

@blueprint.route('/Users', methods=['POST'])
def create_user():
    data, error = _payload()
    if error:
        return error
    return _create_user_response(data)


@blueprint.route('/Users/<path:user_id>', methods=['PUT'])
def replace_user(user_id):
    data, error = _payload()
    if error:
        return error
    return _replace_user_response(user_id, data)


@blueprint.route('/Users/<path:user_id>', methods=['PATCH'])
def patch_user(user_id):
    data, error = _payload()
    if error:
        return error
    return _patch_user_response(user_id, data)


@blueprint.route('/Users/<path:user_id>', methods=['DELETE'])
def delete_user(user_id):
    return _delete_user_response(user_id)


def _bulk_response(operation, bulk_ids):
    method = _string_value(operation.get('method')).upper()
    path = _string_value(operation.get('path')).lstrip('/')
    data = operation.get('data') or {}
    if not method or not path:
        return {'status': '400', 'response': _response_payload(_scim_error(400, 'Bulk operations require method and path', 'invalidValue'))}, None
    if not isinstance(data, dict):
        return {'status': '400', 'response': _response_payload(_scim_error(400, 'Bulk operation data must be an object', 'invalidSyntax'))}, None

    for key, value in list(data.items()):
        if isinstance(value, str) and value.startswith('bulkId:'):
            data[key] = bulk_ids.get(value[7:], value)

    parts = path.split('/', 1)
    collection = parts[0]
    resource_id = parts[1] if len(parts) > 1 else None
    if collection == 'Users':
        if method == 'POST' and resource_id is None:
            response = _create_user_response(data)
        elif method == 'GET' and resource_id:
            response = get_user(resource_id)
        elif method == 'PUT' and resource_id:
            response = _replace_user_response(resource_id, data)
        elif method == 'PATCH' and resource_id:
            response = _patch_user_response(resource_id, data)
        elif method == 'DELETE' and resource_id:
            response = _delete_user_response(resource_id)
        else:
            response = _scim_error(400, f'Unsupported bulk path {path!r}', 'invalidPath')
    elif collection == 'Groups':
        if method == 'POST' and resource_id is None:
            response = _create_group_response(data)
        elif method == 'GET' and resource_id:
            response = _get_group_response(resource_id)
        elif method == 'PUT' and resource_id:
            response = _replace_group_response(resource_id, data)
        elif method == 'PATCH' and resource_id:
            response = _patch_group_response(resource_id, data)
        elif method == 'DELETE' and resource_id:
            response = _delete_group_response(resource_id)
        else:
            response = _scim_error(400, f'Unsupported bulk path {path!r}', 'invalidPath')
    else:
        response = _scim_error(400, f'Unsupported bulk path {path!r}', 'invalidPath')

    if isinstance(response, tuple):
        status = response[1]
        payload = None
        location = None
    else:
        status = response.status_code
        payload = _response_payload(response)
        location = payload.get('meta', {}).get('location') if isinstance(payload, dict) else None
    item = {'status': str(status)}
    if operation.get('bulkId'):
        item['bulkId'] = operation['bulkId']
    if location:
        item['location'] = location
    if payload is not None:
        item['response'] = payload
    resource_id = payload.get('id') if isinstance(payload, dict) else None
    return item, resource_id


@blueprint.route('/Bulk', methods=['POST'])
def bulk():
    data, error = _payload()
    if error:
        return error
    operations = data.get('Operations') or data.get('operations')
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax')
    if len(operations) > 100:
        return _scim_error(413, 'Too many bulk operations', 'tooMany')
    fail_on_errors = _parse_positive_int(data.get('failOnErrors', len(operations)), len(operations), minimum=0)
    responses = []
    errors = 0
    bulk_ids = {}
    for operation in operations:
        if not isinstance(operation, dict):
            responses.append({'status': '400', 'response': _response_payload(_scim_error(400, 'Bulk operations must be objects', 'invalidSyntax'))})
            errors += 1
        else:
            response, resource_id = _bulk_response(operation, bulk_ids)
            responses.append(response)
            if operation.get('bulkId') and resource_id:
                bulk_ids[operation['bulkId']] = resource_id
            if int(response['status']) >= 400:
                errors += 1
        if fail_on_errors and errors >= fail_on_errors:
            break
    return _scim_response({
        'schemas': [SCIM_BULK_RESPONSE_SCHEMA],
        'Operations': responses,
    })
