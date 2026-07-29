import hashlib
import json
import re
import secrets
import urllib.parse

import flask
import sqlalchemy
import validators
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.http import parse_etags, unquote_etag

from . import common
from .. import models, utils


SCIM_USER_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:User'
SCIM_GROUP_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Group'
SCIM_LIST_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:ListResponse'
SCIM_PATCH_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:PatchOp'
SCIM_ERROR_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:Error'
SCIM_BULK_REQUEST_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:BulkRequest'
SCIM_BULK_RESPONSE_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:BulkResponse'
SCIM_SCHEMA_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Schema'

blueprint = flask.Blueprint('scim', __name__)
_IF_MATCH_FROM_REQUEST = object()
SCIM_MAX_BULK_OPERATIONS = 100
SCIM_MAX_BULK_PAYLOAD_SIZE = 1048576
_FILTER_PATTERN = re.compile(r'^\s*([A-Za-z][A-Za-z0-9.]*)\s+eq\s+"([^"]*)"\s*$', re.IGNORECASE)
_MEMBER_FILTER_PATTERN = re.compile(
    r'^\s*members\s*\[\s*value\s+eq\s+"([^"]+)"\s*\]\s*$',
    re.IGNORECASE,
)
_PROJECTION_SEGMENT_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')
_INVALID_PERCENT_ESCAPE = re.compile(r'%(?![0-9A-Fa-f]{2})')
_SCIM_KEY_CASES = {
    key.lower(): key
    for key in (
        'Operations',
        'active',
        'bulkId',
        'data',
        'displayName',
        'emails',
        'externalId',
        'failOnErrors',
        'familyName',
        'formatted',
        'givenName',
        'id',
        'members',
        'method',
        'name',
        'op',
        'password',
        'path',
        'primary',
        'schemas',
        'type',
        'userName',
        'value',
        'version',
    )
}
_USER_PROJECTION_PATHS = {
    ('active',),
    ('displayname',),
    ('emails',),
    ('emails', 'primary'),
    ('emails', 'type'),
    ('emails', 'value'),
    ('id',),
    ('meta',),
    ('meta', 'location'),
    ('meta', 'resourcetype'),
    ('meta', 'version'),
    ('name',),
    ('name', 'formatted'),
    ('password',),
    ('schemas',),
    ('username',),
}
_GROUP_PROJECTION_PATHS = {
    ('displayname',),
    ('id',),
    ('members',),
    ('members', 'display'),
    ('members', 'value'),
    ('meta',),
    ('meta', 'location'),
    ('meta', 'resourcetype'),
    ('meta', 'version'),
    ('schemas',),
}
_USER_PROJECTION_ENDPOINTS = {
    'create_user',
    'get_user',
    'list_users',
    'patch_user',
    'replace_user',
}
_GROUP_PROJECTION_ENDPOINTS = {
    'create_group',
    'get_group',
    'list_groups',
    'patch_group',
    'replace_group',
}
_MISSING_PROJECTION_PATH = object()


class _AmbiguousScimKeys(ValueError):
    pass


def _base_url():
    web_api_root = flask.current_app.config.get('WEB_API') or '/api'
    return flask.request.url_root.rstrip('/') + web_api_root.rstrip('/') + '/scim/v2'


def _resource_location(resource, resource_id):
    encoded_id = urllib.parse.quote(str(resource_id), safe='@')
    return f'{_base_url()}/{resource}/{encoded_id}'


def _projection_context():
    endpoint = (flask.request.endpoint or '').rsplit('.', 1)[-1]
    if endpoint in _USER_PROJECTION_ENDPOINTS:
        return SCIM_USER_SCHEMA, _USER_PROJECTION_PATHS
    if endpoint in _GROUP_PROJECTION_ENDPOINTS:
        return SCIM_GROUP_SCHEMA, _GROUP_PROJECTION_PATHS
    return None


def _projection_path(value, schema, allowed_paths):
    path = value.strip()
    prefix = f'{schema}:'
    if path.casefold().startswith('urn:'):
        if not path.casefold().startswith(prefix.casefold()):
            return None
        path = path[len(prefix):]
    elif ':' in path:
        return None
    parts = path.split('.')
    if (
        not path
        or any(not _PROJECTION_SEGMENT_PATTERN.fullmatch(part) for part in parts)
    ):
        return None
    normalized = tuple(
        _SCIM_KEY_CASES.get(part.casefold(), part).casefold()
        for part in parts
    )
    return normalized if normalized in allowed_paths else None


def _projection_parameters():
    context = _projection_context()
    if context is None:
        return None, None, None
    schema, allowed_paths = context
    included_values = flask.request.args.getlist('attributes')
    excluded_values = flask.request.args.getlist('excludedAttributes')
    if included_values and excluded_values:
        return None, None, 'attributes and excludedAttributes are mutually exclusive'
    mode = 'include' if included_values else ('exclude' if excluded_values else None)
    raw_values = included_values or excluded_values
    if not raw_values:
        return None, None, None
    paths = []
    for raw_value in raw_values:
        for raw_path in raw_value.split(','):
            path = _projection_path(raw_path, schema, allowed_paths)
            if path is None:
                return (
                    None,
                    None,
                    'Attribute projection paths must be non-empty attribute paths',
                )
            if path not in paths:
                paths.append(path)
    return mode, paths, None


def _projection_tree(paths):
    tree = {}
    for path in paths:
        node = tree
        for index, part in enumerate(path):
            if part in node and node[part] is None:
                break
            if index == len(path) - 1:
                node[part] = None
            else:
                node = node.setdefault(part, {})
    return tree


def _project_value(value, tree, *, include):
    if not tree:
        return value
    if isinstance(value, list):
        return [
            _project_value(item, tree, include=include)
            for item in value
        ]
    if not isinstance(value, dict):
        return value
    projected = {}
    for key, item in value.items():
        selected = tree.get(key.casefold(), _MISSING_PROJECTION_PATH)
        if include:
            if selected is not _MISSING_PROJECTION_PATH:
                projected[key] = (
                    item
                    if selected is None
                    else _project_value(item, selected, include=True)
                )
        elif selected is _MISSING_PROJECTION_PATH:
            projected[key] = item
        elif selected is not None:
            projected[key] = _project_value(item, selected, include=False)
    return projected


def _always_returned(resource):
    return {'schemas', 'id'}


def _project_resource(resource, mode, paths):
    if not isinstance(resource, dict):
        return resource
    tree = _projection_tree(paths)
    projected = _project_value(resource, tree, include=mode == 'include')
    for key in _always_returned(resource):
        for source_key, value in resource.items():
            if source_key.casefold() == key.casefold():
                projected[source_key] = value
                break
    return projected


def _project_payload(payload):
    if _projection_context() is None or not isinstance(payload, dict):
        return payload
    mode, paths, error = _projection_parameters()
    if error or mode is None:
        return payload
    if isinstance(payload.get('Resources'), list):
        projected = dict(payload)
        projected['Resources'] = [
            _project_resource(resource, mode, paths)
            for resource in payload['Resources']
        ]
        return projected
    return _project_resource(payload, mode, paths)


def _scim_response(payload, status=200):
    original_payload = payload
    if 200 <= status < 300:
        payload = _project_payload(payload)
    response = flask.jsonify(payload)
    response.status_code = status
    response.headers['Content-Type'] = 'application/scim+json'
    if isinstance(original_payload, dict):
        meta = original_payload.get('meta')
        if isinstance(meta, dict):
            version = meta.get('version')
            location = meta.get('location')
            if isinstance(version, str):
                response.headers['ETag'] = version
            if isinstance(location, str):
                response.headers['Content-Location'] = location
                if status == 201:
                    response.headers['Location'] = location
    return response


def _response_payload(response):
    if isinstance(response, tuple):
        response = response[0]
    if response.status_code == 204:
        return None
    return response.get_json(silent=True)


def _not_modified(version):
    response = flask.Response(status=304)
    response.headers['ETag'] = version
    return response


def _resource_version(resource):
    if isinstance(resource, models.User):
        state = {
            'active': resource.enabled,
            'displayName': resource.displayed_name,
            'id': resource.email,
            'password': resource.password,
        }
    elif isinstance(resource, models.Alias):
        state = {
            'displayName': resource.comment,
            'id': resource.email,
            'members': list(resource.destination),
        }
    else:
        state = {
            'created': getattr(resource, 'created_at', None),
            'updated': getattr(resource, 'updated_at', None),
        }
    encoded = json.dumps(state, default=str, separators=(',', ':'), sort_keys=True).encode()
    return f'"{hashlib.sha256(encoded).hexdigest()}"'


def _resource_meta(resource_type, collection, resource_id, model):
    meta = {
        'resourceType': resource_type,
        'location': _resource_location(collection, resource_id),
    }
    version = _resource_version(model)
    if version:
        meta['version'] = version
    return meta


def _get_for_update(model, resource_id):
    session = models.db.session()
    if models.db.engine.dialect.name == 'sqlite':
        session.execute(sqlalchemy.text('BEGIN IMMEDIATE'))
        return session.get(model, resource_id, populate_existing=True)
    return session.get(
        model,
        resource_id,
        populate_existing=True,
        with_for_update=True,
    )


def _locked_resource(model, resource_id):
    try:
        return _get_for_update(model, resource_id), None
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM database lock failed')
        return None, _scim_error(500, 'The SCIM resource could not be locked')


def _if_match_error(resource, value=_IF_MATCH_FROM_REQUEST):
    if value is _IF_MATCH_FROM_REQUEST:
        value = flask.request.headers.get('If-Match')
    if value is None:
        return None
    if not isinstance(value, str):
        return _scim_error(400, 'version must be an entity-tag string', 'invalidValue')
    if resource is None:
        return _scim_error(412, 'If-Match does not match the current resource version')
    candidates = parse_etags(value)
    current = _resource_version(resource)
    current_opaque, current_is_weak = unquote_etag(current)
    if candidates.star_tag or (not current_is_weak and candidates.contains(current_opaque)):
        return None
    return _scim_error(412, 'If-Match does not match the current resource version')


def _conditional_read_response(resource):
    error = _if_match_error(resource)
    if error:
        return error
    value = flask.request.headers.get('If-None-Match')
    if value is None:
        return None
    candidates = parse_etags(value)
    current = _resource_version(resource)
    current_opaque, _ = unquote_etag(current)
    if candidates.star_tag or candidates.contains_weak(current_opaque):
        return _not_modified(current)
    return None


def _if_none_match_error(resource, value=_IF_MATCH_FROM_REQUEST):
    if value is _IF_MATCH_FROM_REQUEST:
        value = flask.request.headers.get('If-None-Match')
    if value is None or resource is None:
        return None
    candidates = parse_etags(value)
    current = _resource_version(resource)
    current_opaque, _ = unquote_etag(current)
    if candidates.star_tag or candidates.contains_weak(current_opaque):
        return _scim_error(412, 'If-None-Match matches the current resource version')
    return None


def _scim_error(status, detail, scim_type=None):
    payload = {
        'schemas': [SCIM_ERROR_SCHEMA],
        'status': str(status),
        'detail': detail,
    }
    if scim_type:
        payload['scimType'] = scim_type
    return _scim_response(payload, status)


def _commit_error():
    try:
        models.db.session.commit()
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM database commit failed')
        return _scim_error(500, 'The SCIM resource change could not be committed')
    return None


def _commit_user_change(user, *, prune_sessions):
    if prune_sessions:
        try:
            utils.MailuSessionExtension.prune_sessions(uid=user.email)
        except Exception:
            models.db.session.rollback()
            flask.current_app.logger.exception('SCIM session revocation failed')
            return _scim_error(500, 'Existing sessions could not be revoked')
    return _commit_error()


@blueprint.errorhandler(HTTPException)
def _http_error(error):
    detail = getattr(error, 'description', None) or str(error)
    return _scim_error(error.code or 500, detail)


@blueprint.errorhandler(SQLAlchemyError)
def _database_error(_error):
    models.db.session.rollback()
    flask.current_app.logger.exception('Unhandled SCIM database error')
    return _scim_error(500, 'The SCIM database operation failed')


def _payload():
    data = flask.request.get_json(silent=True)
    if data is None:
        if flask.request.get_data(cache=True).strip():
            return None, _scim_error(400, 'Request body must be valid JSON', 'invalidSyntax')
        return {}, None
    if not isinstance(data, dict):
        return None, _scim_error(400, 'Request body must be a JSON object', 'invalidSyntax')
    try:
        return _normalize_scim_keys(data), None
    except _AmbiguousScimKeys as error:
        return None, _scim_error(400, str(error), 'invalidSyntax')


def _normalize_scim_keys(value):
    if isinstance(value, list):
        return [_normalize_scim_keys(item) for item in value]
    if isinstance(value, dict):
        normalized = {}
        source_keys = {}
        for key, item in value.items():
            normalized_key = (
                _SCIM_KEY_CASES.get(key.casefold(), key)
                if isinstance(key, str)
                else key
            )
            collision_key = (
                normalized_key.casefold()
                if isinstance(normalized_key, str)
                else normalized_key
            )
            if collision_key in source_keys:
                raise _AmbiguousScimKeys(
                    f'Attributes {source_keys[collision_key]!r} and {key!r} '
                    'are case-equivalent'
                )
            source_keys[collision_key] = key
            normalized[normalized_key] = _normalize_scim_keys(item)
        return normalized
    return value


def _parse_positive_int(value, default, *, minimum=0, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _equality_filter(value, supported_attribute):
    match = _FILTER_PATTERN.fullmatch(value)
    if not match or match.group(1).lower() != supported_attribute.lower():
        return None, _scim_error(
            400,
            f'Only {supported_attribute} eq filters with a quoted value are supported',
            'invalidFilter',
        )
    return match.group(2), None


def _schema_error(data, expected):
    schemas = data.get('schemas')
    if (
        not isinstance(schemas, list)
        or len(schemas) != 1
        or not isinstance(schemas[0], str)
        or schemas[0].casefold() != expected.casefold()
    ):
        return _scim_error(
            400,
            f'schemas must contain exactly {expected}',
            'invalidValue',
        )
    return None


def _string_value(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


def _schema_path(path, schema):
    prefix = f'{schema}:'
    if path.lower().startswith(prefix.lower()):
        return path[len(prefix):]
    return path


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


def _user_email(data, *, require_user_name=False, conflict_scim_type='invalidValue'):
    values = []
    user_name = data.get('userName')
    if require_user_name and (
        not isinstance(user_name, str)
        or not user_name.strip()
    ):
        return None, _scim_error(400, 'userName is required', 'invalidValue')
    if user_name not in (None, ''):
        if not isinstance(user_name, str):
            return None, _scim_error(400, 'userName must be a string', 'invalidValue')
        user_name = user_name.strip().lower()
        if user_name:
            values.append(user_name)

    emails = data.get('emails') or []
    if not isinstance(emails, list):
        return None, _scim_error(400, 'emails must be a list', 'invalidValue')
    for email in emails:
        if not isinstance(email, dict):
            return None, _scim_error(400, 'emails must contain objects', 'invalidValue')
        value = email.get('value')
        if value in (None, ''):
            continue
        if not isinstance(value, str):
            return None, _scim_error(400, 'email values must be strings', 'invalidValue')
        value = value.strip().lower()
        if value:
            values.append(value)
    unique_values = list(dict.fromkeys(values))
    if len(unique_values) > 1:
        return None, _scim_error(
            400,
            'userName and emails must identify the same mailbox',
            conflict_scim_type,
        )
    return (unique_values[0] if unique_values else ''), None


def _display_name(data):
    if data.get('displayName') is not None:
        if not isinstance(data['displayName'], str):
            return None, _scim_error(400, 'displayName must be a string', 'invalidValue')
        display_name = data['displayName'].strip()
        if display_name:
            return display_name, None
    name = data.get('name') or {}
    if not isinstance(name, dict):
        return None, _scim_error(400, 'name must be an object', 'invalidValue')
    for attribute in ('formatted', 'givenName', 'familyName'):
        if name.get(attribute) is not None and not isinstance(name[attribute], str):
            return None, _scim_error(400, f'name.{attribute} must be a string', 'invalidValue')
    formatted = (name.get('formatted') or '').strip()
    if formatted:
        return formatted, None
    parts = [(name.get('givenName') or '').strip(), (name.get('familyName') or '').strip()]
    return ' '.join(part for part in parts if part), None


def _resource_id(value, resource_type):
    if not isinstance(value, str) or not validators.email(value):
        return None, _scim_error(
            400,
            f'{resource_type} id must be a valid email address',
            'invalidValue',
        )
    return value.lower(), None


def _get_user(user_id):
    if not isinstance(user_id, str) or not validators.email(user_id):
        return None
    user_id = user_id.lower()
    return models.db.session.get(models.User, user_id)


def _make_user_resource(user):
    email = user.email
    payload = {
        'schemas': [SCIM_USER_SCHEMA],
        'id': email,
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
    if not isinstance(group_id, str) or not validators.email(group_id):
        return None
    group_id = group_id.lower()
    return models.db.session.get(models.Alias, group_id)


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
        } for destination in group.destination],
        'meta': _resource_meta('Group', 'Groups', email, group),
    }


def _validate_alias_domain(email, *, for_update=False):
    if not validators.email(email):
        return None, _scim_error(400, f'{email!r} is not a valid email address', 'invalidValue')
    localpart, domain_name = email.rsplit('@', 1)
    if for_update:
        domain, error = _locked_resource(models.Domain, domain_name)
        if error:
            return None, error
    else:
        domain = models.db.session.get(models.Domain, domain_name)
    if not domain:
        return None, _scim_error(404, f'Domain {domain_name} does not exist')
    if domain.max_aliases != -1 and len(domain.aliases) >= domain.max_aliases:
        return None, _scim_error(409, f'Too many aliases for domain {domain_name}', 'uniqueness')
    return (localpart, domain), None


def _apply_group_data(group, data, *, replacing=False):
    if 'displayName' in data:
        if not isinstance(data['displayName'], str):
            return _scim_error(400, 'displayName must be a string', 'invalidValue')
        group.comment = '' if data['displayName'].strip().lower() == group.email else data['displayName'].strip()
    elif replacing:
        group.comment = ''
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
    comment = group.comment or ''
    members = list(group.destination)
    for operation in operations:
        if not isinstance(operation, dict):
            return _scim_error(400, 'Patch operations must be objects', 'invalidSyntax')
        op_value = operation.get('op')
        if not isinstance(op_value, str) or not op_value:
            return _scim_error(400, 'Patch op must be a non-empty string', 'invalidSyntax')
        op = op_value.lower()
        path_value = operation.get('path')
        if path_value is not None and not isinstance(path_value, str):
            return _scim_error(400, 'Patch path must be a string', 'invalidPath')
        path = _schema_path((path_value or '').strip(), SCIM_GROUP_SCHEMA)
        path_lower = path.lower()
        value = operation.get('value')
        if op not in ('add', 'replace', 'remove'):
            return _scim_error(400, f'Patch operation {op!r} is not supported', 'mutability')

        member_filter = _MEMBER_FILTER_PATTERN.fullmatch(path)
        if member_filter:
            if op != 'remove' or value is not None:
                return _scim_error(
                    400,
                    'Filtered members paths are supported only for remove without a value',
                    'invalidPath',
                )
            filtered_members, error = _member_values({'members': [member_filter.group(1)]})
            if error:
                return error
            members = [member for member in members if member not in filtered_members]
            continue

        if path_lower == 'displayname':
            if op == 'remove':
                return _scim_error(400, 'Group displayName is required', 'mutability')
            elif not isinstance(value, str):
                return _scim_error(400, 'displayName must be a string', 'invalidValue')
            else:
                comment = '' if value.strip().lower() == group.email else value.strip()
            continue

        if path_lower == 'members':
            if op == 'remove' and value is None:
                members = []
                continue
            member_data = {'members': value if isinstance(value, list) else [value]}
            patch_members, error = _member_values(member_data)
            if error:
                return error
            if op == 'remove':
                members = [member for member in members if member not in patch_members]
            elif op == 'add':
                members = members + [member for member in patch_members if member not in members]
            else:
                members = patch_members
            continue

        if not path:
            if op not in ('add', 'replace') or not isinstance(value, dict):
                return _scim_error(400, 'Pathless Group PATCH values must be objects', 'invalidPath')
            handled = False
            if 'displayName' in value:
                if not isinstance(value['displayName'], str):
                    return _scim_error(400, 'displayName must be a string', 'invalidValue')
                display_name = value['displayName'].strip()
                comment = '' if display_name.lower() == group.email else display_name
                handled = True
            if 'members' in value:
                patch_members, error = _member_values({'members': value['members']})
                if error:
                    return error
                if op == 'add':
                    members = members + [member for member in patch_members if member not in members]
                else:
                    members = patch_members
                handled = True
            if not handled:
                return _scim_error(400, 'Pathless Group PATCH has no supported attributes', 'invalidPath')
            continue

        return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath')
    group.comment = comment
    group.destination = members
    return None


def _validate_user_domain(email, *, for_update=False):
    if not validators.email(email):
        return None, _scim_error(400, f'{email!r} is not a valid email address', 'invalidValue')
    localpart, domain_name = email.rsplit('@', 1)
    if for_update:
        domain, error = _locked_resource(models.Domain, domain_name)
        if error:
            return None, error
    else:
        domain = models.db.session.get(models.Domain, domain_name)
    if not domain:
        return None, _scim_error(404, f'Domain {domain_name} does not exist')
    if domain.max_users != -1 and len(domain.users) >= domain.max_users:
        return None, _scim_error(409, f'Too many users for domain {domain_name}', 'uniqueness')
    return (localpart, domain), None


def _user_data_changes(data, *, replacing=False):
    changes = []
    if replacing:
        if 'active' in data:
            active, error = _active_value(data['active'])
            if error:
                return None, error
            changes.append(('active', active))
        else:
            changes.append(('active', True))
    elif 'active' in data:
        active, error = _active_value(data['active'])
        if error:
            return None, error
        changes.append(('active', active))

    display_name, error = _display_name(data)
    if error:
        return None, error
    if display_name:
        changes.append(('displayName', display_name))
    elif replacing:
        changes.append(('displayName', ''))
    password, error = _password_value(data.get('password'))
    if error:
        return None, error
    if password:
        changes.append(('password', password))
    return changes, None


def _apply_user_changes(user, changes):
    password_changed = False
    deactivated = False
    for attribute, value in changes:
        if attribute == 'active':
            user.enabled = value
            deactivated = deactivated or not value
        elif attribute == 'displayName':
            user.displayed_name = value
        elif attribute == 'password':
            user.set_password(value, keep_sessions=True)
            password_changed = True
    return password_changed, deactivated


def _apply_user_data(user, data, *, replacing=False):
    changes, error = _user_data_changes(data, replacing=replacing)
    if error:
        return error, False, False
    password_changed, deactivated = _apply_user_changes(user, changes)
    return None, password_changed, deactivated


def _patch_user(user, data):
    if 'Operations' in data:
        operations = data['Operations']
    else:
        operations = data.get('operations')
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax'), False
    if not operations:
        return _scim_error(400, 'Operations must not be empty', 'invalidValue'), False
    changes = []
    for operation in operations:
        if not isinstance(operation, dict):
            return _scim_error(400, 'Patch operations must be objects', 'invalidSyntax'), False
        op_value = operation.get('op')
        path_value = operation.get('path')
        if not isinstance(op_value, str) or not op_value:
            return _scim_error(400, 'Patch op must be a non-empty string', 'invalidSyntax'), False
        if path_value is not None and not isinstance(path_value, str):
            return _scim_error(400, 'Patch path must be a string', 'invalidPath'), False
        op = op_value.lower()
        path = _schema_path(path_value or '', SCIM_USER_SCHEMA).lower()
        value = operation.get('value')
        if op not in ('add', 'replace', 'remove'):
            return _scim_error(400, f'Patch operation {op!r} is not supported', 'mutability'), False
        if path == 'password' or (
            not path
            and isinstance(value, dict)
            and 'password' in value
        ):
            return _scim_error(
                400,
                'Changing an existing password through SCIM is not supported',
                'mutability',
            ), False
        if op == 'remove':
            if path in ('displayname', 'name', 'name.formatted'):
                changes.append(('displayName', ''))
                continue
            if path == 'active':
                changes.append(('active', True))
                continue
            return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath'), False

        handled = False
        if path in ('active', '') and (path or isinstance(value, dict)):
            if path == 'active':
                active, error = _active_value(value)
                if error:
                    return error, False
                changes.append(('active', active))
                handled = True
            elif isinstance(value, dict) and 'active' in value:
                active, error = _active_value(value['active'])
                if error:
                    return error, False
                changes.append(('active', active))
                handled = True
        if path in ('displayname', '') and (path or isinstance(value, dict)):
            if path == 'displayname' and value is not None:
                if not isinstance(value, str):
                    return _scim_error(400, 'displayName must be a string', 'invalidValue'), False
                changes.append(('displayName', value))
                handled = True
            elif isinstance(value, dict):
                display_name, error = _display_name(value)
                if error:
                    return error, False
                if display_name:
                    changes.append(('displayName', display_name))
                    handled = True
        if path in ('name.formatted', 'name', '') and value:
            if path == 'name.formatted':
                if not isinstance(value, str):
                    return _scim_error(400, 'name.formatted must be a string', 'invalidValue'), False
                changes.append(('displayName', value))
                handled = True
            elif path == 'name':
                if not isinstance(value, dict):
                    return _scim_error(400, 'name must be an object', 'invalidValue'), False
                display_name, error = _display_name({'name': value})
                if error:
                    return error, False
                if display_name:
                    changes.append(('displayName', display_name))
                    handled = True
        if not handled:
            return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath'), False
    password_changed, deactivated = _apply_user_changes(user, changes)
    return None, password_changed or deactivated

@blueprint.before_request
def authorize():
    if flask.request.method == 'OPTIONS':
        return None

    @common.api_token_authorization
    def _authorized():
        return None

    return _authorized()


@blueprint.before_request
def validate_projection():
    _, _, error = _projection_parameters()
    if error:
        return _scim_error(400, error, 'invalidValue')
    return None


@blueprint.route('/ServiceProviderConfig', methods=['GET'])
def service_provider_config():
    return _scim_response({
        'schemas': ['urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig'],
        'patch': {'supported': True},
        'bulk': {
            'supported': True,
            'maxOperations': SCIM_MAX_BULK_OPERATIONS,
            'maxPayloadSize': SCIM_MAX_BULK_PAYLOAD_SIZE,
        },
        'filter': {'supported': False, 'maxResults': 200},
        'changePassword': {'supported': False},
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


def _resource_type_resources():
    return [
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


@blueprint.route('/ResourceTypes', methods=['GET'])
def resource_types():
    resources = _resource_type_resources()
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': len(resources),
        'startIndex': 1,
        'itemsPerPage': len(resources),
        'Resources': resources,
    })


@blueprint.route('/ResourceTypes/<resource_type>', methods=['GET'])
def resource_type(resource_type):
    for resource in _resource_type_resources():
        if resource['id'] == resource_type:
            return _scim_response(resource)
    return _scim_error(404, f'ResourceType {resource_type} cannot be found')


def _schema_resources():
    return [
        {
            'schemas': [SCIM_SCHEMA_SCHEMA],
            'id': SCIM_USER_SCHEMA,
            'name': 'User',
            'description': 'Mailu SCIM user schema subset',
            'attributes': [
                {
                    'name': 'userName',
                    'type': 'string',
                    'multiValued': False,
                    'required': True,
                    'caseExact': False,
                    'mutability': 'immutable',
                    'returned': 'default',
                    'uniqueness': 'server',
                },
                {
                    'name': 'name',
                    'type': 'complex',
                    'multiValued': False,
                    'required': False,
                    'mutability': 'readWrite',
                    'returned': 'default',
                    'subAttributes': [
                        {
                            'name': attribute,
                            'type': 'string',
                            'multiValued': False,
                            'required': False,
                            'caseExact': False,
                            'mutability': 'readWrite',
                            'returned': 'default',
                            'uniqueness': 'none',
                        }
                        for attribute in ('formatted',)
                    ],
                },
                {
                    'name': 'displayName',
                    'type': 'string',
                    'multiValued': False,
                    'required': False,
                    'caseExact': False,
                    'mutability': 'readWrite',
                    'returned': 'default',
                    'uniqueness': 'none',
                },
                {
                    'name': 'active',
                    'type': 'boolean',
                    'multiValued': False,
                    'required': False,
                    'mutability': 'readWrite',
                    'returned': 'default',
                },
                {
                    'name': 'password',
                    'type': 'string',
                    'multiValued': False,
                    'required': False,
                    'caseExact': True,
                    'mutability': 'immutable',
                    'returned': 'never',
                    'uniqueness': 'none',
                },
                {
                    'name': 'emails',
                    'type': 'complex',
                    'multiValued': True,
                    'required': False,
                    'mutability': 'immutable',
                    'returned': 'default',
                    'subAttributes': [
                        {
                            'name': 'value',
                            'type': 'string',
                            'multiValued': False,
                            'required': True,
                            'caseExact': False,
                            'mutability': 'immutable',
                            'returned': 'default',
                            'uniqueness': 'none',
                        },
                        {
                            'name': 'type',
                            'type': 'string',
                            'multiValued': False,
                            'required': False,
                            'caseExact': False,
                            'mutability': 'immutable',
                            'returned': 'default',
                            'uniqueness': 'none',
                        },
                        {
                            'name': 'primary',
                            'type': 'boolean',
                            'multiValued': False,
                            'required': False,
                            'mutability': 'immutable',
                            'returned': 'default',
                        },
                    ],
                },
            ],
            'meta': {'resourceType': 'Schema', 'location': _resource_location('Schemas', SCIM_USER_SCHEMA)},
        },
        {
            'schemas': [SCIM_SCHEMA_SCHEMA],
            'id': SCIM_GROUP_SCHEMA,
            'name': 'Group',
            'description': 'Mailu SCIM group schema subset backed by aliases',
            'attributes': [
                {
                    'name': 'displayName',
                    'type': 'string',
                    'multiValued': False,
                    'required': True,
                    'caseExact': False,
                    'mutability': 'readWrite',
                    'returned': 'default',
                    'uniqueness': 'none',
                },
                {
                    'name': 'members',
                    'type': 'complex',
                    'multiValued': True,
                    'required': False,
                    'mutability': 'readWrite',
                    'returned': 'default',
                    'subAttributes': [
                        {
                            'name': 'value',
                            'type': 'string',
                            'multiValued': False,
                            'required': True,
                            'caseExact': False,
                            'mutability': 'immutable',
                            'returned': 'default',
                            'uniqueness': 'none',
                        },
                        {
                            'name': 'display',
                            'type': 'string',
                            'multiValued': False,
                            'required': False,
                            'caseExact': False,
                            'mutability': 'readOnly',
                            'returned': 'default',
                            'uniqueness': 'none',
                        },
                    ],
                },
            ],
            'meta': {'resourceType': 'Schema', 'location': _resource_location('Schemas', SCIM_GROUP_SCHEMA)},
        },
    ]


@blueprint.route('/Schemas', methods=['GET'])
def schemas():
    resources = _schema_resources()
    return _scim_response({
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': len(resources),
        'startIndex': 1,
        'itemsPerPage': len(resources),
        'Resources': resources,
    })


@blueprint.route('/Schemas/<path:schema_id>', methods=['GET'])
def schema(schema_id):
    for resource in _schema_resources():
        if resource['id'] == schema_id:
            return _scim_response(resource)
    return _scim_error(404, f'Schema {schema_id} cannot be found')


def _list_groups_response():
    start_index = _parse_positive_int(flask.request.args.get('startIndex', 1), 1, minimum=1)
    count = _parse_positive_int(flask.request.args.get('count', 100), 100, minimum=0, maximum=200)
    if start_index is None or count is None:
        return _scim_error(400, 'startIndex and count must be integers', 'invalidValue')
    query = models.Alias.query.order_by(models.Alias._email)

    filter_value = flask.request.args.get('filter')
    if filter_value:
        display_name, error = _equality_filter(filter_value, 'displayName')
        if error:
            return error
        normalized = display_name.lower()
        predicates = [sqlalchemy.func.lower(models.Alias.comment) == normalized]
        if validators.email(display_name):
            predicates.append(sqlalchemy.and_(
                sqlalchemy.or_(models.Alias.comment.is_(None), models.Alias.comment == ''),
                models.Alias._email == normalized,
            ))
        query = query.filter(sqlalchemy.or_(*predicates))

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
    error = _schema_error(data, SCIM_GROUP_SCHEMA)
    if error:
        return error
    email, error = _group_email(data)
    if error:
        return error
    if not email:
        return _scim_error(400, 'displayName is required', 'invalidValue')
    domain_data, error = _validate_alias_domain(email, for_update=True)
    if error:
        models.db.session.rollback()
        return error
    if _get_group(email) or _get_user(email):
        models.db.session.rollback()
        return _scim_error(409, f'Address {email} already exists', 'uniqueness')
    localpart, domain = domain_data
    group = models.Alias(localpart=localpart, domain=domain, destination=[])
    error = _apply_group_data(group, data, replacing=True)
    if error:
        models.db.session.rollback()
        return error
    models.db.session.add(group)
    try:
        models.db.session.commit()
    except IntegrityError:
        models.db.session.rollback()
        return _scim_error(409, f'Address {email} already exists', 'uniqueness')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM Group creation failed')
        return _scim_error(500, 'The SCIM Group could not be created')
    return _scim_response(_make_group_resource(group), 201)


def _get_group_response(group_id):
    group_id, error = _resource_id(group_id, 'Group')
    if error:
        return error
    group = _get_group(group_id)
    if not group:
        return _scim_error(404, f'Group {group_id} cannot be found')
    conditional = _conditional_read_response(group)
    if conditional:
        return conditional
    return _scim_response(_make_group_resource(group))


def _replace_group_response(
    group_id,
    data,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    error = _schema_error(data, SCIM_GROUP_SCHEMA)
    if error:
        return error
    group_id, error = _resource_id(group_id, 'Group')
    if error:
        return error
    group, error = _locked_resource(models.Alias, group_id)
    if error:
        return error
    error = _if_match_error(group, if_match)
    if error:
        models.db.session.rollback()
        return error
    error = _if_none_match_error(group, if_none_match)
    if error:
        models.db.session.rollback()
        return error
    if not group:
        models.db.session.rollback()
        return _scim_error(404, f'Group {group_id} cannot be found')
    if not isinstance(data.get('displayName'), str) or not data['displayName'].strip():
        models.db.session.rollback()
        return _scim_error(400, 'displayName is required', 'invalidValue')
    supplied_id = data.get('id')
    if supplied_id is not None:
        new_email, error = _resource_id(supplied_id, 'Group')
        if error:
            models.db.session.rollback()
            return error
    else:
        new_email = None
    if new_email and new_email != group.email:
        models.db.session.rollback()
        return _scim_error(400, 'Changing group id is not supported', 'mutability')
    error = _apply_group_data(group, data, replacing=True)
    if error:
        models.db.session.rollback()
        return error
    models.db.session.add(group)
    error = _commit_error()
    if error:
        return error
    return _scim_response(_make_group_resource(group))


def _patch_group_response(
    group_id,
    data,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    error = _schema_error(data, SCIM_PATCH_SCHEMA)
    if error:
        return error
    group_id, error = _resource_id(group_id, 'Group')
    if error:
        return error
    group, error = _locked_resource(models.Alias, group_id)
    if error:
        return error
    error = _if_match_error(group, if_match)
    if error:
        models.db.session.rollback()
        return error
    error = _if_none_match_error(group, if_none_match)
    if error:
        models.db.session.rollback()
        return error
    if not group:
        models.db.session.rollback()
        return _scim_error(404, f'Group {group_id} cannot be found')
    error = _patch_group(group, data)
    if error:
        models.db.session.rollback()
        return error
    models.db.session.add(group)
    error = _commit_error()
    if error:
        return error
    return _scim_response(_make_group_resource(group))


def _delete_group_response(
    group_id,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    group_id, error = _resource_id(group_id, 'Group')
    if error:
        return error
    group, error = _locked_resource(models.Alias, group_id)
    if error:
        return error
    error = _if_match_error(group, if_match)
    if error:
        models.db.session.rollback()
        return error
    error = _if_none_match_error(group, if_none_match)
    if error:
        models.db.session.rollback()
        return error
    if not group:
        models.db.session.rollback()
        return _scim_error(404, f'Group {group_id} cannot be found')
    models.db.session.delete(group)
    error = _commit_error()
    if error:
        return error
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
        email, error = _equality_filter(filter_value, 'userName')
        if error:
            return error
        if not validators.email(email):
            return _scim_error(400, 'userName filter value must be a valid email address', 'invalidFilter')
        email = email.lower()
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
    error = _schema_error(data, SCIM_USER_SCHEMA)
    if error:
        return error
    email, error = _user_email(data, require_user_name=True)
    if error:
        return error
    if not email:
        return _scim_error(400, 'userName or emails[0].value is required', 'invalidValue')
    domain_data, error = _validate_user_domain(email, for_update=True)
    if error:
        models.db.session.rollback()
        return error
    if _get_user(email) or _get_group(email):
        models.db.session.rollback()
        return _scim_error(409, f'Address {email} already exists', 'uniqueness')
    localpart, domain = domain_data
    user = models.User(localpart=localpart, domain=domain)
    error, password_changed, _ = _apply_user_data(user, data, replacing=True)
    if error:
        models.db.session.rollback()
        return error
    if not password_changed:
        user.set_password(secrets.token_urlsafe(), keep_sessions=True)
    models.db.session.add(user)
    try:
        models.db.session.commit()
    except IntegrityError:
        models.db.session.rollback()
        return _scim_error(409, f'Address {email} already exists', 'uniqueness')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM User creation failed')
        return _scim_error(500, 'The SCIM User could not be created')
    return _scim_response(_make_user_resource(user), 201)


@blueprint.route('/Users/<path:user_id>', methods=['GET'])
def get_user(user_id):
    user_id, error = _resource_id(user_id, 'User')
    if error:
        return error
    user = _get_user(user_id)
    if not user:
        return _scim_error(404, f'User {user_id} cannot be found')
    conditional = _conditional_read_response(user)
    if conditional:
        return conditional
    return _scim_response(_make_user_resource(user))


def _replace_user_response(
    user_id,
    data,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    error = _schema_error(data, SCIM_USER_SCHEMA)
    if error:
        return error
    user_id, error = _resource_id(user_id, 'User')
    if error:
        return error
    user, error = _locked_resource(models.User, user_id)
    if error:
        return error
    error = _if_match_error(user, if_match)
    if error:
        models.db.session.rollback()
        return error
    error = _if_none_match_error(user, if_none_match)
    if error:
        models.db.session.rollback()
        return error
    if not user:
        models.db.session.rollback()
        return _scim_error(404, f'User {user_id} cannot be found')
    new_email, error = _user_email(
        data,
        require_user_name=True,
        conflict_scim_type='mutability',
    )
    if error:
        models.db.session.rollback()
        return error
    if not new_email:
        models.db.session.rollback()
        return _scim_error(400, 'userName or emails[0].value is required', 'invalidValue')
    if new_email != user.email:
        models.db.session.rollback()
        return _scim_error(400, 'Changing userName/email is not supported', 'mutability')
    if 'password' in data:
        models.db.session.rollback()
        return _scim_error(400, 'Changing an existing password through SCIM is not supported', 'mutability')
    error, password_changed, deactivated = _apply_user_data(user, data, replacing=True)
    if error:
        models.db.session.rollback()
        return error
    models.db.session.add(user)
    error = _commit_user_change(
        user,
        prune_sessions=password_changed or deactivated,
    )
    if error:
        return error
    return _scim_response(_make_user_resource(user))


def _patch_user_response(
    user_id,
    data,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    error = _schema_error(data, SCIM_PATCH_SCHEMA)
    if error:
        return error
    user_id, error = _resource_id(user_id, 'User')
    if error:
        return error
    user, error = _locked_resource(models.User, user_id)
    if error:
        return error
    error = _if_match_error(user, if_match)
    if error:
        models.db.session.rollback()
        return error
    error = _if_none_match_error(user, if_none_match)
    if error:
        models.db.session.rollback()
        return error
    if not user:
        models.db.session.rollback()
        return _scim_error(404, f'User {user_id} cannot be found')
    error, prune_sessions = _patch_user(user, data)
    if error:
        models.db.session.rollback()
        return error
    models.db.session.add(user)
    error = _commit_user_change(user, prune_sessions=prune_sessions)
    if error:
        return error
    return _scim_response(_make_user_resource(user))


def _delete_user_response(
    user_id,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    user_id, error = _resource_id(user_id, 'User')
    if error:
        return error
    user, error = _locked_resource(models.User, user_id)
    if error:
        return error
    error = _if_match_error(user, if_match)
    if error:
        models.db.session.rollback()
        return error
    error = _if_none_match_error(user, if_none_match)
    if error:
        models.db.session.rollback()
        return error
    if not user:
        models.db.session.rollback()
        return _scim_error(404, f'User {user_id} cannot be found')
    user.enabled = False
    models.db.session.add(user)
    error = _commit_user_change(user, prune_sessions=True)
    if error:
        return error
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


def _resolve_bulk_ids(value, bulk_ids):
    if isinstance(value, str) and value.startswith('bulkId:'):
        return bulk_ids.get(value[7:], value)
    if isinstance(value, list):
        return [_resolve_bulk_ids(item, bulk_ids) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_bulk_ids(item, bulk_ids) for key, item in value.items()}
    return value


def _bulk_id_references(value):
    if isinstance(value, str):
        return {value[7:]} if value.startswith('bulkId:') else set()
    if isinstance(value, list):
        references = set()
        for item in value:
            references.update(_bulk_id_references(item))
        return references
    if isinstance(value, dict):
        references = set()
        for item in value.values():
            references.update(_bulk_id_references(item))
        return references
    return set()


def _operation_bulk_references(operation):
    references = _bulk_id_references(operation.get('data'))
    path = operation.get('path')
    if isinstance(path, str):
        parts = path.lstrip('/').split('/', 1)
        if len(parts) == 2 and parts[1].startswith('bulkId:'):
            references.add(parts[1][7:])
    return references


def _parse_bulk_path(path, bulk_ids):
    if not isinstance(path, str) or not path:
        return None, None, None, 'Bulk operations require method and path', 'invalidValue'
    try:
        parsed = urllib.parse.urlsplit(path)
    except ValueError:
        return None, None, None, f'Unsupported bulk path {path!r}', 'invalidPath'
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None, None, None, f'Unsupported bulk path {path!r}', 'invalidPath'
    normalized_path = parsed.path.lstrip('/')
    parts = normalized_path.split('/')
    if (
        not normalized_path
        or len(parts) > 2
        or parts[0] not in ('Users', 'Groups')
        or (len(parts) == 2 and not parts[1])
    ):
        return None, None, None, f'Unsupported bulk path {path!r}', 'invalidPath'
    collection = parts[0]
    resource_id = parts[1] if len(parts) == 2 else None
    if resource_id is None:
        return collection, None, None, None, None
    if resource_id.startswith('bulkId:'):
        resource_id = bulk_ids.get(resource_id[7:], resource_id)
        if resource_id.startswith('bulkId:'):
            return (
                None,
                None,
                None,
                'Bulk operation path references an unknown bulkId',
                'invalidValue',
            )
    else:
        if _INVALID_PERCENT_ESCAPE.search(resource_id):
            return None, None, None, f'Unsupported bulk path {path!r}', 'invalidPath'
        try:
            resource_id = urllib.parse.unquote(resource_id, errors='strict')
        except UnicodeDecodeError:
            return None, None, None, f'Unsupported bulk path {path!r}', 'invalidPath'
    if '/' in resource_id:
        return None, None, None, f'Unsupported bulk path {path!r}', 'invalidPath'
    return (
        collection,
        resource_id,
        _resource_location(collection, resource_id),
        None,
        None,
    )


def _bulk_operation_location(operation, bulk_ids):
    path = operation.get('path')
    _, _, location, _, _ = _parse_bulk_path(path, bulk_ids)
    return location


def _bulk_error(operation, method, status, detail, scim_type, *, location=None):
    item = {
        'method': method,
        'status': str(status),
        'response': _response_payload(_scim_error(status, detail, scim_type)),
    }
    if operation.get('bulkId'):
        item['bulkId'] = operation['bulkId']
    if location:
        item['location'] = location
    models.db.session.rollback()
    return item, None


def _bulk_response(operation, bulk_ids):
    method = _string_value(operation.get('method')).upper()
    path = operation.get('path')
    data = operation.get('data')
    if data is None:
        data = {}
    version = operation.get('version')
    if not method or not isinstance(path, str) or not path:
        return _bulk_error(
            operation,
            method,
            400,
            'Bulk operations require method and path',
            'invalidValue',
        )
    collection, resource_id, request_location, path_error, path_scim_type = (
        _parse_bulk_path(path, bulk_ids)
    )
    if path_error:
        return _bulk_error(
            operation,
            method,
            400,
            path_error,
            path_scim_type,
            location=request_location,
        )
    if not isinstance(data, dict):
        return _bulk_error(
            operation,
            method,
            400,
            'Bulk operation data must be an object',
            'invalidSyntax',
            location=request_location,
        )
    data = _resolve_bulk_ids(data, bulk_ids)
    if _bulk_id_references(data):
        return _bulk_error(
            operation,
            method,
            400,
            'Bulk operation references an unknown bulkId',
            'invalidValue',
            location=request_location,
        )

    if collection == 'Users':
        if method == 'POST' and resource_id is None:
            response = _create_user_response(data)
        elif method == 'PUT' and resource_id:
            response = _replace_user_response(
                resource_id,
                data,
                if_match=version,
                if_none_match=None,
            )
        elif method == 'PATCH' and resource_id:
            response = _patch_user_response(
                resource_id,
                data,
                if_match=version,
                if_none_match=None,
            )
        elif method == 'DELETE' and resource_id:
            response = _delete_user_response(
                resource_id,
                if_match=version,
                if_none_match=None,
            )
        else:
            response = _scim_error(400, f'Unsupported bulk path {path!r}', 'invalidPath')
    elif collection == 'Groups':
        if method == 'POST' and resource_id is None:
            response = _create_group_response(data)
        elif method == 'PUT' and resource_id:
            response = _replace_group_response(
                resource_id,
                data,
                if_match=version,
                if_none_match=None,
            )
        elif method == 'PATCH' and resource_id:
            response = _patch_group_response(
                resource_id,
                data,
                if_match=version,
                if_none_match=None,
            )
        elif method == 'DELETE' and resource_id:
            response = _delete_group_response(
                resource_id,
                if_match=version,
                if_none_match=None,
            )
        else:
            response = _scim_error(400, f'Unsupported bulk path {path!r}', 'invalidPath')
    else:
        response = _scim_error(400, f'Unsupported bulk path {path!r}', 'invalidPath')

    if isinstance(response, tuple):
        status = response[1]
        payload = None
        location = None
        response_version = None
    else:
        status = response.status_code
        payload = _response_payload(response)
        location = payload.get('meta', {}).get('location') if isinstance(payload, dict) else None
        response_version = response.headers.get('ETag')
    location = location or request_location
    item = {'method': method, 'status': str(status)}
    if operation.get('bulkId'):
        item['bulkId'] = operation['bulkId']
    if location:
        item['location'] = location
    if response_version:
        item['version'] = response_version
    if payload is not None:
        item['response'] = payload
    resource_id = payload.get('id') if isinstance(payload, dict) else None
    if int(status) >= 400:
        models.db.session.rollback()
    return item, resource_id


@blueprint.route('/Bulk', methods=['POST'])
def bulk():
    if (
        flask.request.content_length is not None
        and flask.request.content_length > SCIM_MAX_BULK_PAYLOAD_SIZE
    ):
        return _scim_error(413, 'Bulk request exceeds maxPayloadSize')
    if len(flask.request.get_data(cache=True)) > SCIM_MAX_BULK_PAYLOAD_SIZE:
        return _scim_error(413, 'Bulk request exceeds maxPayloadSize')
    data, error = _payload()
    if error:
        return error
    error = _schema_error(data, SCIM_BULK_REQUEST_SCHEMA)
    if error:
        return error
    operations = data.get('Operations') or data.get('operations')
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax')
    if not operations:
        return _scim_error(400, 'Operations must not be empty', 'invalidValue')
    if len(operations) > SCIM_MAX_BULK_OPERATIONS:
        return _scim_error(413, 'Too many bulk operations', 'tooMany')
    raw_fail_on_errors = data.get('failOnErrors', len(operations))
    try:
        fail_on_errors = int(raw_fail_on_errors)
    except (TypeError, ValueError):
        fail_on_errors = None
    if isinstance(raw_fail_on_errors, bool) or fail_on_errors is None or fail_on_errors < 0:
        return _scim_error(400, 'failOnErrors must be a non-negative integer', 'invalidValue')
    bulk_id_values = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        bulk_id = operation.get('bulkId')
        method = _string_value(operation.get('method')).upper()
        if method == 'POST' and (not isinstance(bulk_id, str) or not bulk_id):
            return _scim_error(400, 'POST bulk operations require a non-empty bulkId', 'invalidValue')
        if bulk_id is not None and (not isinstance(bulk_id, str) or not bulk_id):
            return _scim_error(400, 'bulkId must be a non-empty string', 'invalidValue')
        if bulk_id in bulk_id_values:
            return _scim_error(400, f'Duplicate bulkId {bulk_id!r}', 'invalidValue')
        if bulk_id is not None:
            bulk_id_values.append(bulk_id)
    responses = {}
    errors = 0
    bulk_ids = {}
    declared_bulk_ids = set(bulk_id_values)
    pending = list(enumerate(operations))
    stopped = False
    while pending and not stopped:
        deferred = []
        progressed = False
        for index, operation in pending:
            if not isinstance(operation, dict):
                response = {
                    'status': '400',
                    'response': _response_payload(
                        _scim_error(400, 'Bulk operations must be objects', 'invalidSyntax')
                    ),
                }
                resource_id = None
            else:
                references = _operation_bulk_references(operation)
                unknown = references - declared_bulk_ids
                unresolved = references - bulk_ids.keys()
                if unknown:
                    response, resource_id = _bulk_error(
                        operation,
                        _string_value(operation.get('method')).upper(),
                        400,
                        f'Bulk operation references unknown bulkId {sorted(unknown)[0]!r}',
                        'invalidValue',
                        location=_bulk_operation_location(operation, bulk_ids),
                    )
                elif unresolved:
                    deferred.append((index, operation))
                    continue
                else:
                    response, resource_id = _bulk_response(operation, bulk_ids)
            responses[index] = response
            progressed = True
            if isinstance(operation, dict) and operation.get('bulkId') and resource_id:
                bulk_ids[operation['bulkId']] = resource_id
            if int(response['status']) >= 400:
                errors += 1
            if fail_on_errors and errors >= fail_on_errors:
                stopped = True
                break
        if stopped or not deferred:
            break
        if progressed:
            pending = deferred
            continue
        for index, operation in deferred:
            response, _ = _bulk_error(
                operation,
                _string_value(operation.get('method')).upper(),
                409,
                'Bulk operation has a circular or failed bulkId dependency',
                None,
                location=_bulk_operation_location(operation, bulk_ids),
            )
            responses[index] = response
            errors += 1
            if fail_on_errors and errors >= fail_on_errors:
                break
        break
    return _scim_response({
        'schemas': [SCIM_BULK_RESPONSE_SCHEMA],
        'Operations': [responses[index] for index in sorted(responses)],
    })
