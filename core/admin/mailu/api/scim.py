import hashlib
import json
import re
import secrets
import urllib.parse

import flask
import sqlalchemy
import validators
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.datastructures import ETags
from werkzeug.exceptions import HTTPException
from werkzeug.http import unquote_etag

from . import common
from .. import models, utils


SCIM_USER_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:User'
SCIM_GROUP_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Group'
SCIM_GROUP_EXTENSION = 'https://mailu.io/schemas/scim/2.0/Group'
SCIM_LIST_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:ListResponse'
SCIM_PATCH_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:PatchOp'
SCIM_ERROR_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:Error'
SCIM_BULK_REQUEST_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:BulkRequest'
SCIM_BULK_RESPONSE_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:BulkResponse'
SCIM_SCHEMA_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Schema'

blueprint = flask.Blueprint('scim', __name__)
_IF_MATCH_FROM_REQUEST = object()
_UNCHANGED = object()
SCIM_MAX_BULK_OPERATIONS = 100
SCIM_MAX_BULK_PAYLOAD_SIZE = 1048576
_FILTER_PATTERN = re.compile(r'^\s*([A-Za-z][A-Za-z0-9.]*)\s+eq\s+"([^"]*)"\s*$', re.IGNORECASE)
_MEMBER_FILTER_PATTERN = re.compile(
    r'^\s*members\s*\[\s*value\s+eq\s+"([^"]+)"\s*\]\s*$',
    re.IGNORECASE,
)
_PROJECTION_SEGMENT_PATTERN = re.compile(
    r'^(?:[A-Za-z][A-Za-z0-9_-]*|\$ref)$'
)
_INVALID_PERCENT_ESCAPE = re.compile(r'%(?![0-9A-Fa-f]{2})')
_SCIM_KEY_CASES = {
    key.lower(): key
    for key in (
        'Operations',
        '$ref',
        'active',
        'aliasAddress',
        'bulkId',
        'data',
        'displayName',
        'emails',
        'externalId',
        'externalDestinations',
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
        SCIM_GROUP_EXTENSION,
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
    ('externalid',),
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
    ('externalid',),
    ('members',),
    ('members', 'display'),
    ('members', '$ref'),
    ('members', 'type'),
    ('members', 'value'),
    ('meta',),
    ('meta', 'location'),
    ('meta', 'resourcetype'),
    ('meta', 'version'),
    ('schemas',),
    (SCIM_GROUP_EXTENSION.casefold(),),
    (SCIM_GROUP_EXTENSION.casefold(), 'aliasaddress'),
    (SCIM_GROUP_EXTENSION.casefold(), 'externaldestinations'),
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
    extension_prefix = f'{SCIM_GROUP_EXTENSION}:'
    if path.casefold().startswith(extension_prefix.casefold()):
        path = path[len(extension_prefix):]
        parts = path.split('.')
        if (
            not path
            or any(
                not _PROJECTION_SEGMENT_PATTERN.fullmatch(part)
                for part in parts
            )
        ):
            return None
        normalized = (
            SCIM_GROUP_EXTENSION.casefold(),
            *(
                _SCIM_KEY_CASES.get(part.casefold(), part).casefold()
                for part in parts
            ),
        )
        return normalized if normalized in allowed_paths else None
    if path.casefold() == SCIM_GROUP_EXTENSION.casefold():
        normalized = (SCIM_GROUP_EXTENSION.casefold(),)
        return normalized if normalized in allowed_paths else None
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
    always = {'schemas', 'id'}
    schemas = resource.get('schemas', [])
    if SCIM_USER_SCHEMA in schemas:
        always.add('username')
    if SCIM_GROUP_SCHEMA in schemas:
        always.add('displayname')
    return always


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
    if isinstance(resource, models.ScimResource):
        state = {
            'externalId': resource.external_id,
            'id': resource.id,
            'resourceType': resource.resource_type,
            'subjectAddress': resource.subject_address,
        }
        if resource.resource_type == 'User' and resource.user is not None:
            state.update({
                'active': resource.user.enabled,
                'displayName': resource.user.displayed_name,
                'userName': resource.user.email,
            })
        elif resource.resource_type == 'Group' and resource.alias is not None:
            state.update({
                'aliasAddress': resource.alias.email,
                'displayName': resource.alias.comment or resource.alias.email,
                'externalDestinations': sorted(
                    destination.destination
                    for destination in resource.destinations
                ),
                'members': sorted(
                    edge.member_id
                    for edge in resource.member_edges
                ),
            })
    elif isinstance(resource, models.User):
        state = {
            'active': resource.enabled,
            'displayName': resource.displayed_name,
            'id': resource.email,
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


def _parse_entity_tags(value, field_name):
    if not isinstance(value, str):
        return None, _scim_error(
            400,
            f'{field_name} must be an entity-tag string',
            'invalidValue',
        )

    def invalid():
        return None, _scim_error(
            400,
            f'{field_name} must contain valid HTTP entity-tags',
            'invalidValue',
        )

    length = len(value)
    start = 0
    while start < length and value[start] in ' \t':
        start += 1
    end = length
    while end > start and value[end - 1] in ' \t':
        end -= 1
    if end - start == 1 and value[start] == '*':
        return ETags(star_tag=True), None

    strong = []
    weak = []
    position = 0
    while True:
        while position < length and value[position] in ' \t':
            position += 1
        if position == length:
            return ETags(strong, weak), None
        if value[position] == ',':
            position += 1
            continue

        is_weak = value.startswith('W/', position)
        if is_weak:
            position += 2
        if position == length or value[position] != '"':
            return invalid()
        position += 1
        tag_start = position
        while position < length and value[position] != '"':
            codepoint = ord(value[position])
            if not (
                codepoint == 0x21
                or 0x23 <= codepoint <= 0x7e
                or 0x80 <= codepoint <= 0xff
            ):
                return invalid()
            position += 1
        if position == length:
            return invalid()
        tag = value[tag_start:position]
        position += 1
        (weak if is_weak else strong).append(tag)

        while position < length and value[position] in ' \t':
            position += 1
        if position == length:
            return ETags(strong, weak), None
        if value[position] != ',':
            return invalid()
        position += 1


def _if_match_error(resource, value=_IF_MATCH_FROM_REQUEST):
    if value is _IF_MATCH_FROM_REQUEST:
        value = flask.request.headers.get('If-Match')
        field_name = 'If-Match'
    else:
        field_name = 'version'
    if value is None:
        return None
    candidates, error = _parse_entity_tags(value, field_name)
    if error:
        return error
    if resource is None:
        return _scim_error(412, 'If-Match does not match the current resource version')
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
    candidates, error = _parse_entity_tags(value, 'If-None-Match')
    if error:
        return error
    current = _resource_version(resource)
    current_opaque, _ = unquote_etag(current)
    if candidates.star_tag or candidates.contains_weak(current_opaque):
        return _not_modified(current)
    return None


def _if_none_match_error(resource, value=_IF_MATCH_FROM_REQUEST):
    if value is _IF_MATCH_FROM_REQUEST:
        value = flask.request.headers.get('If-None-Match')
    if value is None:
        return None
    candidates, error = _parse_entity_tags(value, 'If-None-Match')
    if error:
        return error
    if resource is None:
        return None
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
    error = _commit_error()
    if error:
        return error
    if prune_sessions:
        try:
            utils.MailuSessionExtension.prune_sessions(uid=user.email)
        except Exception:
            flask.current_app.logger.exception(
                'SCIM post-commit session cleanup failed'
            )
    return None


@blueprint.errorhandler(HTTPException)
def _http_error(error):
    detail = getattr(error, 'description', None) or str(error)
    return _scim_error(error.code or 500, detail)


@blueprint.errorhandler(SQLAlchemyError)
def _database_error(_error):
    models.db.session.rollback()
    flask.current_app.logger.exception('Unhandled SCIM database error')
    return _scim_error(500, 'The SCIM database operation failed')


def _reject_duplicate_json_names(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise _AmbiguousScimKeys(f'Duplicate JSON member name {key!r}')
        value[key] = item
    return value


def _payload():
    raw_data = flask.request.get_data(cache=True)
    if not raw_data.strip():
        return {}, None
    if not flask.request.is_json:
        return None, _scim_error(400, 'Request body must be valid JSON', 'invalidSyntax')
    try:
        data = flask.current_app.json.loads(
            raw_data,
            object_pairs_hook=_reject_duplicate_json_names,
        )
    except _AmbiguousScimKeys as error:
        return None, _scim_error(400, str(error), 'invalidSyntax')
    except (TypeError, ValueError):
        return None, _scim_error(400, 'Request body must be valid JSON', 'invalidSyntax')
    if data is None:
        return None, _scim_error(400, 'Request body must be valid JSON', 'invalidSyntax')
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
    return _schema_set_error(data, [expected])


def _schema_set_error(data, expected):
    schemas = data.get('schemas')
    if (
        not isinstance(schemas, list)
        or len(schemas) != len(expected)
        or any(not isinstance(schema, str) for schema in schemas)
        or len({schema.casefold() for schema in schemas}) != len(schemas)
        or {schema.casefold() for schema in schemas}
        != {schema.casefold() for schema in expected}
    ):
        description = ', '.join(expected)
        return _scim_error(
            400,
            f'schemas must contain exactly {description}',
            'invalidValue',
        )
    return None


def _external_id_value(data, *, replacing=False):
    if 'externalId' not in data:
        return (None if replacing else _UNCHANGED), None
    value = data['externalId']
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, _scim_error(
            400,
            'externalId must be a string',
            'invalidValue',
        )
    try:
        encoded = value.encode('utf-8')
    except UnicodeEncodeError:
        return None, _scim_error(
            400,
            'externalId must contain valid Unicode',
            'invalidValue',
        )
    if len(encoded) > 1024:
        return None, _scim_error(
            400,
            'externalId must not exceed 1024 UTF-8 bytes',
            'invalidValue',
        )
    return value, None


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

    emails = data.get('emails', [])
    if emails is None:
        emails = []
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
    for value in unique_values:
        if not validators.email(value):
            return None, _scim_error(
                400,
                f'{value!r} is not a valid email address',
                'invalidValue',
            )
    if require_user_name:
        # RFC 7643 makes userName independently required. An emails entry is
        # representation data, not an alternate identity input.
        return user_name, None
    return (unique_values[0] if unique_values else ''), None


def _display_name(data):
    if data.get('displayName') is not None:
        if not isinstance(data['displayName'], str):
            return None, _scim_error(400, 'displayName must be a string', 'invalidValue')
        display_name = data['displayName'].strip()
        if display_name:
            return display_name, None
    name = data.get('name', {})
    if name is None:
        name = {}
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
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 255
        or '/' in value
    ):
        return None, _scim_error(
            400,
            f'{resource_type} id must be a non-empty opaque identifier',
            'invalidValue',
        )
    return value, None


def _get_user(user_id):
    return models.ScimResource.get_exact(
        user_id,
        resource_type='User',
        active_only=True,
    )


def _get_scim_for_update(resource_id, resource_type):
    """Lock an exact active mapping and its live Mailu resource."""
    statement = (
        sqlalchemy.select(models.ScimResource)
        .where(models.ScimResource.id == resource_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    resource = models.db.session.execute(statement).scalar_one_or_none()
    if (
        resource is None
        or resource.id != resource_id
        or resource.resource_type != resource_type
        or resource.deleted_at is not None
    ):
        return None
    target_model = (
        models.User
        if resource_type == 'User'
        else models.Alias
    )
    target_id = (
        resource.user_email
        if resource_type == 'User'
        else resource.alias_email
    )
    target = models.db.session.execute(
        sqlalchemy.select(target_model)
        .where(target_model._email == target_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if target is None or target.email != target_id:
        raise models.ScimIdentityError(
            f'Active SCIM {resource_type} {resource_id!r} has no live target'
        )
    return resource


def _make_user_resource(resource):
    user = resource.user
    email = user.email
    payload = {
        'schemas': [SCIM_USER_SCHEMA],
        'id': resource.id,
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
        'meta': _resource_meta(
            'User',
            'Users',
            resource.id,
            resource,
        ),
    }
    if resource.external_id is not None:
        payload['externalId'] = resource.external_id
    return payload


def _get_group(group_id):
    return models.ScimResource.get_exact(
        group_id,
        resource_type='Group',
        active_only=True,
    )


def _member_values(data):
    members = data.get('members', [])
    if members is None:
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
        value = value.strip()
        if value.startswith('bulkId:'):
            return None, _scim_error(
                400,
                f'Member {value!r} references an unresolved bulkId',
                'invalidValue',
            )
        if value not in values:
            values.append(value)
    return values, None


def _external_destinations(value):
    if value is None:
        return [], None
    if not isinstance(value, list):
        return None, _scim_error(
            400,
            'externalDestinations must be a list',
            'invalidValue',
        )
    destinations = []
    for destination in value:
        if not isinstance(destination, str) or not destination.strip():
            return None, _scim_error(
                400,
                'externalDestinations must contain non-empty strings',
                'invalidValue',
            )
        try:
            canonical = models.canonicalize_scim_destination(destination)
        except (
            models.ScimExternalDestinationError,
            models.ScimIdentityError,
        ) as error:
            return None, _scim_error(400, str(error), 'invalidValue')
        if canonical not in destinations:
            destinations.append(canonical)
    return destinations, None


def _make_group_resource(resource):
    group = resource.alias
    members = []
    for edge in sorted(resource.member_edges, key=lambda item: item.member_id):
        member = models.ScimResource.get_exact(
            edge.member_id,
            active_only=True,
        )
        if member is None:
            # The live foreign key and graph lock should make this impossible.
            raise models.ScimGraphError(
                f'Group member {edge.member_id!r} is not active'
            )
        collection = 'Users' if member.resource_type == 'User' else 'Groups'
        members.append({
            'value': member.id,
            '$ref': _resource_location(collection, member.id),
            'display': member.subject_address,
            'type': member.resource_type,
        })
    payload = {
        'schemas': [SCIM_GROUP_SCHEMA, SCIM_GROUP_EXTENSION],
        'id': resource.id,
        'displayName': group.comment or group.email,
        'members': members,
        SCIM_GROUP_EXTENSION: {
            'aliasAddress': group.email,
            'externalDestinations': sorted(
                destination.destination
                for destination in resource.destinations
            ),
        },
        'meta': _resource_meta(
            'Group',
            'Groups',
            resource.id,
            resource,
        ),
    }
    if resource.external_id is not None:
        payload['externalId'] = resource.external_id
    return payload


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


def _group_replacement(data, *, current=None):
    error = _schema_set_error(
        data,
        [SCIM_GROUP_SCHEMA, SCIM_GROUP_EXTENSION],
    )
    if error:
        return None, error
    display_name = data.get('displayName')
    if not isinstance(display_name, str) or not display_name.strip():
        return None, _scim_error(
            400,
            'displayName is required',
            'invalidValue',
        )
    extension = data.get(SCIM_GROUP_EXTENSION)
    if not isinstance(extension, dict):
        return None, _scim_error(
            400,
            f'{SCIM_GROUP_EXTENSION} is required',
            'invalidValue',
        )
    alias_address = extension.get('aliasAddress')
    if not isinstance(alias_address, str) or not alias_address.strip():
        return None, _scim_error(
            400,
            'aliasAddress is required',
            'invalidValue',
        )
    alias_address = alias_address.strip().lower()
    if not validators.email(alias_address):
        return None, _scim_error(
            400,
            f'{alias_address!r} is not a valid aliasAddress',
            'invalidValue',
        )
    if current is not None and alias_address != current.alias.email:
        return None, _scim_error(
            400,
            'aliasAddress is immutable',
            'mutability',
        )
    members, error = _member_values(data)
    if error:
        return None, error
    destinations, error = _external_destinations(
        extension.get('externalDestinations', [])
    )
    if error:
        return None, error
    external_id, error = _external_id_value(data, replacing=True)
    if error:
        return None, error
    return {
        'aliasAddress': alias_address,
        'displayName': display_name.strip(),
        'externalId': external_id,
        'members': members,
        'externalDestinations': destinations,
    }, None


def _patch_group(resource, data):
    operations = data['Operations'] if 'Operations' in data else data.get('operations')
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax')
    if not operations:
        return _scim_error(400, 'Operations must not be empty', 'invalidValue')
    display_name = resource.alias.comment or resource.alias.email
    external_id = resource.external_id
    members = [
        edge.member_id
        for edge in resource.member_edges
    ]
    external_destinations = [
        destination.destination
        for destination in resource.destinations
    ]
    for operation in operations:
        if not isinstance(operation, dict):
            return _scim_error(400, 'Patch operations must be objects', 'invalidSyntax')
        op_value = operation.get('op')
        if not isinstance(op_value, str) or not op_value:
            return _scim_error(400, 'Patch op must be a non-empty string', 'invalidSyntax')
        op = op_value.lower()
        path_present = 'path' in operation
        path_value = operation.get('path')
        if path_present and (
            not isinstance(path_value, str)
            or not path_value.strip()
        ):
            return _scim_error(400, 'Patch path must be a string', 'invalidPath')
        path = _schema_path((path_value or '').strip(), SCIM_GROUP_SCHEMA)
        path_lower = path.lower()
        value = operation.get('value')
        if op not in ('add', 'replace', 'remove'):
            return _scim_error(400, f'Patch operation {op!r} is not supported', 'mutability')
        if op in ('add', 'replace') and 'value' not in operation:
            return _scim_error(400, 'Patch value is required', 'invalidValue')
        if op == 'remove' and not path_present:
            return _scim_error(400, 'Pathless remove has no target', 'noTarget')

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
                display_name = value.strip()
            continue

        if path_lower == 'externalid':
            if op == 'remove':
                external_id = None
            else:
                external_id, error = _external_id_value(
                    {'externalId': value},
                )
                if error:
                    return error
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

        extension_path = _schema_path(
            (path_value or '').strip(),
            SCIM_GROUP_EXTENSION,
        )
        if extension_path.casefold() == 'aliasaddress':
            return _scim_error(
                400,
                'aliasAddress is immutable',
                'mutability',
            )
        if extension_path.casefold() == 'externaldestinations':
            if op == 'remove' and value is None:
                external_destinations = []
                continue
            patch_destinations, error = _external_destinations(
                value if isinstance(value, list) else [value]
            )
            if error:
                return error
            if op == 'remove':
                external_destinations = [
                    item
                    for item in external_destinations
                    if item not in patch_destinations
                ]
            elif op == 'add':
                external_destinations += [
                    item
                    for item in patch_destinations
                    if item not in external_destinations
                ]
            else:
                external_destinations = patch_destinations
            continue

        if not path_present:
            if op not in ('add', 'replace') or not isinstance(value, dict):
                return _scim_error(400, 'Pathless Group PATCH values must be objects', 'invalidPath')
            handled = False
            if 'displayName' in value:
                if not isinstance(value['displayName'], str):
                    return _scim_error(400, 'displayName must be a string', 'invalidValue')
                display_name = value['displayName'].strip()
                handled = True
            if 'externalId' in value:
                external_id, error = _external_id_value(value)
                if error:
                    return error
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
            if SCIM_GROUP_EXTENSION in value:
                extension = value[SCIM_GROUP_EXTENSION]
                if not isinstance(extension, dict):
                    return _scim_error(
                        400,
                        f'{SCIM_GROUP_EXTENSION} must be an object',
                        'invalidValue',
                    )
                if 'aliasAddress' in extension:
                    alias_address = extension['aliasAddress']
                    if (
                        not isinstance(alias_address, str)
                        or alias_address.strip().lower()
                        != resource.alias.email
                    ):
                        return _scim_error(
                            400,
                            'aliasAddress is immutable',
                            'mutability',
                        )
                    handled = True
                if 'externalDestinations' in extension:
                    patch_destinations, error = _external_destinations(
                        extension['externalDestinations']
                    )
                    if error:
                        return error
                    if op == 'add':
                        external_destinations += [
                            item
                            for item in patch_destinations
                            if item not in external_destinations
                        ]
                    else:
                        external_destinations = patch_destinations
                    handled = True
            if not handled:
                return _scim_error(400, 'Pathless Group PATCH has no supported attributes', 'invalidPath')
            continue

        return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath')
    return {
        'displayName': display_name,
        'externalId': external_id,
        'members': members,
        'externalDestinations': external_destinations,
    }


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
    final_changes = {}
    for attribute, value in changes:
        final_changes[attribute] = value
    password_changed = False
    deactivated = False
    for attribute, value in final_changes.items():
        if attribute == 'active':
            deactivated = user.enabled and not value
            user.enabled = value
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


def _patch_user(resource, data):
    user = resource.user
    if 'Operations' in data:
        operations = data['Operations']
    else:
        operations = data.get('operations')
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax'), False
    if not operations:
        return _scim_error(400, 'Operations must not be empty', 'invalidValue'), False
    changes = []
    external_id = resource.external_id
    for operation in operations:
        if not isinstance(operation, dict):
            return _scim_error(400, 'Patch operations must be objects', 'invalidSyntax'), False
        op_value = operation.get('op')
        path_present = 'path' in operation
        path_value = operation.get('path')
        if not isinstance(op_value, str) or not op_value:
            return _scim_error(400, 'Patch op must be a non-empty string', 'invalidSyntax'), False
        if path_present and (
            not isinstance(path_value, str)
            or not path_value.strip()
        ):
            return _scim_error(400, 'Patch path must be a string', 'invalidPath'), False
        op = op_value.lower()
        path = _schema_path(path_value or '', SCIM_USER_SCHEMA).lower()
        value = operation.get('value')
        if op not in ('add', 'replace', 'remove'):
            return _scim_error(400, f'Patch operation {op!r} is not supported', 'mutability'), False
        if op in ('add', 'replace') and 'value' not in operation:
            return _scim_error(400, 'Patch value is required', 'invalidValue'), False
        if op == 'remove' and not path_present:
            return _scim_error(400, 'Pathless remove has no target', 'noTarget'), False
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
            if path == 'externalid':
                external_id = None
                continue
            if path in ('displayname', 'name', 'name.formatted'):
                changes.append(('displayName', ''))
                continue
            if path == 'active':
                changes.append(('active', True))
                continue
            return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath'), False

        handled = False
        if path == 'externalid':
            external_id, error = _external_id_value(
                {'externalId': value},
            )
            if error:
                return error, False
            handled = True
        elif not path_present and isinstance(value, dict) and 'externalId' in value:
            external_id, error = _external_id_value(value)
            if error:
                return error, False
            handled = True
        if path in ('active', '') and (path or isinstance(value, dict)):
            if path == 'active':
                active, error = _active_value(value)
                if error:
                    return error, False
                changes.append(('active', active))
                handled = True
            elif not path_present and isinstance(value, dict) and 'active' in value:
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
            elif not path_present and isinstance(value, dict) and (
                'displayName' in value or 'name' in value
            ):
                display_name, error = _display_name(value)
                if error:
                    return error, False
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
        if not path_present and isinstance(value, dict) and (
            'userName' in value or 'emails' in value
        ):
            email, error = _user_email(value)
            if error:
                return error, False
            if email and email != user.email:
                return _scim_error(
                    400,
                    'userName and emails are immutable',
                    'mutability',
                ), False
            handled = True
        if not handled:
            return _scim_error(400, f'Patch path {path!r} is not supported', 'invalidPath'), False
    resource.external_id = external_id
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
        # Mailu implements only two exact-equality convenience filters per
        # resource. That is not RFC 7644 filter support and must not be
        # advertised as such.
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
            'schemaExtensions': [{
                'schema': SCIM_GROUP_EXTENSION,
                'required': True,
            }],
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
                    'name': 'externalId',
                    'type': 'string',
                    'multiValued': False,
                    'required': False,
                    'caseExact': True,
                    'mutability': 'readWrite',
                    'returned': 'default',
                    'uniqueness': 'none',
                },
                {
                    'name': 'userName',
                    'type': 'string',
                    'multiValued': False,
                    'required': True,
                    'caseExact': False,
                    'mutability': 'immutable',
                    'returned': 'always',
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
                    'name': 'externalId',
                    'type': 'string',
                    'multiValued': False,
                    'required': False,
                    'caseExact': True,
                    'mutability': 'readWrite',
                    'returned': 'default',
                    'uniqueness': 'none',
                },
                {
                    'name': 'displayName',
                    'type': 'string',
                    'multiValued': False,
                    'required': True,
                    'caseExact': False,
                    'mutability': 'readWrite',
                    'returned': 'always',
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
                        {
                            'name': '$ref',
                            'type': 'reference',
                            'multiValued': False,
                            'required': False,
                            'caseExact': True,
                            'mutability': 'readOnly',
                            'returned': 'default',
                            'referenceTypes': ['User', 'Group'],
                        },
                        {
                            'name': 'type',
                            'type': 'string',
                            'multiValued': False,
                            'required': False,
                            'caseExact': True,
                            'mutability': 'readOnly',
                            'returned': 'default',
                            'uniqueness': 'none',
                        },
                    ],
                },
            ],
            'meta': {'resourceType': 'Schema', 'location': _resource_location('Schemas', SCIM_GROUP_SCHEMA)},
        },
        {
            'schemas': [SCIM_SCHEMA_SCHEMA],
            'id': SCIM_GROUP_EXTENSION,
            'name': 'MailuGroup',
            'description': (
                'Mailu alias routing attributes for SCIM Groups'
            ),
            'attributes': [
                {
                    'name': 'aliasAddress',
                    'type': 'string',
                    'multiValued': False,
                    'required': True,
                    'caseExact': False,
                    'mutability': 'immutable',
                    'returned': 'default',
                    'uniqueness': 'server',
                },
                {
                    'name': 'externalDestinations',
                    'type': 'string',
                    'multiValued': True,
                    'required': False,
                    'caseExact': False,
                    'mutability': 'readWrite',
                    'returned': 'default',
                    'uniqueness': 'none',
                },
            ],
            'meta': {
                'resourceType': 'Schema',
                'location': _resource_location(
                    'Schemas',
                    SCIM_GROUP_EXTENSION,
                ),
            },
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
    query = (
        models.ScimResource.query
        .filter(
            models.ScimResource.resource_type == 'Group',
            models.ScimResource.deleted_at.is_(None),
            models.ScimResource.alias_email.is_not(None),
        )
        .join(
            models.Alias,
            models.ScimResource.alias_email == models.Alias._email,
        )
        .order_by(models.ScimResource.id)
    )

    filter_value = flask.request.args.get('filter')
    if filter_value:
        match = _FILTER_PATTERN.fullmatch(filter_value)
        if not match:
            return _scim_error(
                400,
                'Only displayName or externalId eq filters are supported',
                'invalidFilter',
            )
        attribute, value = match.groups()
        if attribute.casefold() == 'displayname':
            normalized = value.lower()
            query = query.filter(sqlalchemy.or_(
                sqlalchemy.func.lower(models.Alias.comment) == normalized,
                sqlalchemy.and_(
                    sqlalchemy.or_(
                        models.Alias.comment.is_(None),
                        models.Alias.comment == '',
                    ),
                    sqlalchemy.func.lower(models.Alias._email) == normalized,
                ),
            ))
        elif attribute.casefold() == 'externalid':
            try:
                encoded = value.encode('utf-8')
            except UnicodeEncodeError:
                encoded = None
            query = query.filter(
                models.ScimResource.external_id_bytes == encoded
            )
        else:
            return _scim_error(
                400,
                'Only displayName or externalId eq filters are supported',
                'invalidFilter',
            )

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
    replacement, error = _group_replacement(data)
    if error:
        return error
    email = replacement['aliasAddress']
    try:
        models.lock_scim_graph()
        domain_data, error = _validate_alias_domain(email)
        if error:
            models.db.session.rollback()
            return error
        if models.db.session.get(models.MailAddress, email):
            models.db.session.rollback()
            return _scim_error(
                409,
                f'Address {email} already exists',
                'uniqueness',
            )
        localpart, domain = domain_data
        group = models.Alias(
            localpart=localpart,
            domain=domain,
            destination=[],
            comment=replacement['displayName'],
            disabled=False,
            wildcard=False,
            owner=None,
        )
        models.db.session.add(group)
        models.db.session.flush()
        resource = models.create_scim_group_mapping(
            group,
            resource_id=models.new_scim_id(),
            external_id=replacement['externalId'],
        )
        models.replace_scim_group_graph(
            resource,
            member_ids=replacement['members'],
            external_destinations=replacement['externalDestinations'],
        )
        models.db.session.commit()
    except (IntegrityError, models.AddressConflict):
        models.db.session.rollback()
        return _scim_error(409, f'Address {email} already exists', 'uniqueness')
    except (
        models.ScimExternalDestinationError,
        models.ScimGraphError,
    ) as identity_error:
        models.db.session.rollback()
        return _scim_error(400, str(identity_error), 'invalidValue')
    except models.ScimIdentityError:
        models.db.session.rollback()
        flask.current_app.logger.exception(
            'SCIM Group identity invariant failed during creation'
        )
        return _scim_error(500, 'The SCIM Group identity is inconsistent')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM Group creation failed')
        return _scim_error(500, 'The SCIM Group could not be created')
    return _scim_response(_make_group_resource(resource), 201)


def _get_group_response(group_id):
    group_id, error = _resource_id(group_id, 'Group')
    if error:
        return error
    resource = _get_group(group_id)
    if not resource:
        return _scim_error(404, f'Group {group_id} cannot be found')
    conditional = _conditional_read_response(resource)
    if conditional:
        return conditional
    return _scim_response(_make_group_resource(resource))


def _replace_group_response(
    group_id,
    data,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    group_id, error = _resource_id(group_id, 'Group')
    if error:
        return error
    try:
        models.lock_scim_graph()
        resource = _get_scim_for_update(group_id, 'Group')
        error = _if_match_error(resource, if_match)
        if error:
            models.db.session.rollback()
            return error
        error = _if_none_match_error(resource, if_none_match)
        if error:
            models.db.session.rollback()
            return error
        if not resource:
            models.db.session.rollback()
            return _scim_error(404, f'Group {group_id} cannot be found')
        replacement, error = _group_replacement(data, current=resource)
        if error:
            models.db.session.rollback()
            return error
        models.permit_scim_managed_alias_edit(resource.alias)
        resource.alias.comment = replacement['displayName']
        resource.external_id = replacement['externalId']
        models.replace_scim_group_graph(
            resource,
            member_ids=replacement['members'],
            external_destinations=replacement['externalDestinations'],
        )
        models.db.session.commit()
    except (
        models.ScimExternalDestinationError,
        models.ScimGraphError,
    ) as identity_error:
        models.db.session.rollback()
        return _scim_error(400, str(identity_error), 'invalidValue')
    except models.ScimIdentityError:
        models.db.session.rollback()
        flask.current_app.logger.exception(
            'SCIM Group identity invariant failed during replacement'
        )
        return _scim_error(500, 'The SCIM Group identity is inconsistent')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM Group replacement failed')
        return _scim_error(500, 'The SCIM Group could not be replaced')
    return _scim_response(_make_group_resource(resource))


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
    try:
        models.lock_scim_graph()
        resource = _get_scim_for_update(group_id, 'Group')
        error = _if_match_error(resource, if_match)
        if error:
            models.db.session.rollback()
            return error
        error = _if_none_match_error(resource, if_none_match)
        if error:
            models.db.session.rollback()
            return error
        if not resource:
            models.db.session.rollback()
            return _scim_error(404, f'Group {group_id} cannot be found')
        replacement = _patch_group(resource, data)
        if not isinstance(replacement, dict):
            models.db.session.rollback()
            return replacement
        if not replacement['displayName']:
            models.db.session.rollback()
            return _scim_error(
                400,
                'Group displayName is required',
                'mutability',
            )
        models.permit_scim_managed_alias_edit(resource.alias)
        resource.alias.comment = replacement['displayName']
        resource.external_id = replacement['externalId']
        models.replace_scim_group_graph(
            resource,
            member_ids=replacement['members'],
            external_destinations=replacement['externalDestinations'],
        )
        models.db.session.commit()
    except (
        models.ScimExternalDestinationError,
        models.ScimGraphError,
    ) as identity_error:
        models.db.session.rollback()
        return _scim_error(400, str(identity_error), 'invalidValue')
    except models.ScimIdentityError:
        models.db.session.rollback()
        flask.current_app.logger.exception(
            'SCIM Group identity invariant failed during patch'
        )
        return _scim_error(500, 'The SCIM Group identity is inconsistent')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM Group patch failed')
        return _scim_error(500, 'The SCIM Group could not be patched')
    return _scim_response(_make_group_resource(resource))


def _delete_group_response(
    group_id,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    group_id, error = _resource_id(group_id, 'Group')
    if error:
        return error
    try:
        models.lock_scim_graph()
        resource = _get_scim_for_update(group_id, 'Group')
        error = _if_match_error(resource, if_match)
        if error:
            models.db.session.rollback()
            return error
        error = _if_none_match_error(resource, if_none_match)
        if error:
            models.db.session.rollback()
            return error
        if not resource:
            models.db.session.rollback()
            return _scim_error(404, f'Group {group_id} cannot be found')
        alias = resource.alias
        models.tombstone_scim_resource(resource)
        # Persist the detached tombstone before deleting the Alias. Otherwise
        # the generic before_flush lifecycle hook still sees the database's
        # pre-tombstone live FK and attempts to tombstone it a second time.
        models.db.session.flush()
        models.db.session.delete(alias)
        models.db.session.commit()
    except models.ScimGraphError as identity_error:
        models.db.session.rollback()
        return _scim_error(400, str(identity_error), 'invalidValue')
    except models.ScimIdentityError:
        models.db.session.rollback()
        flask.current_app.logger.exception(
            'SCIM Group identity invariant failed during deletion'
        )
        return _scim_error(500, 'The SCIM Group identity is inconsistent')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM Group deletion failed')
        return _scim_error(500, 'The SCIM Group could not be deleted')
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
    query = (
        models.ScimResource.query
        .filter(
            models.ScimResource.resource_type == 'User',
            models.ScimResource.deleted_at.is_(None),
            models.ScimResource.user_email.is_not(None),
        )
        .join(
            models.User,
            models.ScimResource.user_email == models.User._email,
        )
        .order_by(models.ScimResource.id)
    )

    filter_value = flask.request.args.get('filter')
    if filter_value:
        match = _FILTER_PATTERN.fullmatch(filter_value)
        if not match:
            return _scim_error(
                400,
                'Only userName or externalId eq filters are supported',
                'invalidFilter',
            )
        attribute, value = match.groups()
        if attribute.casefold() == 'username':
            if not validators.email(value):
                return _scim_error(
                    400,
                    'userName filter value must be a valid email address',
                    'invalidFilter',
                )
            query = query.filter(models.User._email == value.lower())
        elif attribute.casefold() == 'externalid':
            try:
                encoded = value.encode('utf-8')
            except UnicodeEncodeError:
                encoded = None
            query = query.filter(
                models.ScimResource.external_id_bytes == encoded
            )
        else:
            return _scim_error(
                400,
                'Only userName or externalId eq filters are supported',
                'invalidFilter',
            )

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
        return _scim_error(400, 'userName is required', 'invalidValue')
    external_id, error = _external_id_value(data, replacing=True)
    if error:
        return error
    try:
        models.lock_scim_graph()
        domain_name = email.rsplit('@', 1)[1]
        domain = models.db.session.get(models.Domain, domain_name)
        if not domain:
            models.db.session.rollback()
            return _scim_error(404, f'Domain {domain_name} does not exist')
        address = models.db.session.get(models.MailAddress, email)
        user = models.db.session.get(models.User, email)
        if address is not None or user is not None:
            models.db.session.rollback()
            return _scim_error(
                409,
                f'Address {email} already exists',
                'uniqueness',
            )
        if (
            domain.max_users != -1
            and len(domain.users) >= domain.max_users
        ):
            models.db.session.rollback()
            return _scim_error(
                409,
                f'Too many users for domain {domain_name}',
                'uniqueness',
            )
        localpart = email.rsplit('@', 1)[0]
        user = models.User(localpart=localpart, domain=domain)
        models.db.session.add(user)
        error, password_changed, _ = _apply_user_data(
            user,
            data,
            replacing=True,
        )
        if error:
            models.db.session.rollback()
            return error
        if not password_changed:
            user.set_password(secrets.token_urlsafe(), keep_sessions=True)
        models.db.session.add(user)
        models.db.session.flush()
        resource = models.create_scim_user_mapping(
            user,
            external_id=external_id,
        )
        models.db.session.commit()
    except (IntegrityError, models.AddressConflict):
        models.db.session.rollback()
        return _scim_error(409, f'Address {email} already exists', 'uniqueness')
    except models.ScimIdentityError as identity_error:
        models.db.session.rollback()
        return _scim_error(409, str(identity_error), 'uniqueness')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM User creation failed')
        return _scim_error(500, 'The SCIM User could not be created')
    return _scim_response(_make_user_resource(resource), 201)


@blueprint.route('/Users/<path:user_id>', methods=['GET'])
def get_user(user_id):
    user_id, error = _resource_id(user_id, 'User')
    if error:
        return error
    resource = _get_user(user_id)
    if not resource:
        return _scim_error(404, f'User {user_id} cannot be found')
    conditional = _conditional_read_response(resource)
    if conditional:
        return conditional
    return _scim_response(_make_user_resource(resource))


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
    try:
        models.lock_scim_graph()
        resource = _get_scim_for_update(user_id, 'User')
        error = _if_match_error(resource, if_match)
        if error:
            models.db.session.rollback()
            return error
        error = _if_none_match_error(resource, if_none_match)
        if error:
            models.db.session.rollback()
            return error
        if not resource:
            models.db.session.rollback()
            return _scim_error(404, f'User {user_id} cannot be found')
        user = resource.user
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
            return _scim_error(
                400,
                'userName is required',
                'invalidValue',
            )
        if new_email != user.email:
            models.db.session.rollback()
            return _scim_error(
                400,
                'Changing userName/email is not supported',
                'mutability',
            )
        if 'password' in data:
            models.db.session.rollback()
            return _scim_error(
                400,
                'Changing an existing password through SCIM is not supported',
                'mutability',
            )
        external_id, error = _external_id_value(data, replacing=True)
        if error:
            models.db.session.rollback()
            return error
        resource.external_id = external_id
        error, password_changed, deactivated = _apply_user_data(
            user,
            data,
            replacing=True,
        )
        if error:
            models.db.session.rollback()
            return error
        models.db.session.add(resource)
        models.db.session.add(user)
        error = _commit_user_change(
            user,
            prune_sessions=password_changed or deactivated,
        )
        if error:
            return error
    except models.ScimIdentityError:
        models.db.session.rollback()
        flask.current_app.logger.exception(
            'SCIM User identity invariant failed during replacement'
        )
        return _scim_error(500, 'The SCIM User identity is inconsistent')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM User replacement failed')
        return _scim_error(500, 'The SCIM User could not be replaced')
    return _scim_response(_make_user_resource(resource))


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
    try:
        models.lock_scim_graph()
        resource = _get_scim_for_update(user_id, 'User')
        error = _if_match_error(resource, if_match)
        if error:
            models.db.session.rollback()
            return error
        error = _if_none_match_error(resource, if_none_match)
        if error:
            models.db.session.rollback()
            return error
        if not resource:
            models.db.session.rollback()
            return _scim_error(404, f'User {user_id} cannot be found')
        error, prune_sessions = _patch_user(resource, data)
        if error:
            models.db.session.rollback()
            return error
        models.db.session.add(resource)
        models.db.session.add(resource.user)
        error = _commit_user_change(
            resource.user,
            prune_sessions=prune_sessions,
        )
        if error:
            return error
    except models.ScimIdentityError:
        models.db.session.rollback()
        flask.current_app.logger.exception(
            'SCIM User identity invariant failed during patch'
        )
        return _scim_error(500, 'The SCIM User identity is inconsistent')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM User patch failed')
        return _scim_error(500, 'The SCIM User could not be patched')
    return _scim_response(_make_user_resource(resource))


def _delete_user_response(
    user_id,
    if_match=_IF_MATCH_FROM_REQUEST,
    if_none_match=_IF_MATCH_FROM_REQUEST,
):
    user_id, error = _resource_id(user_id, 'User')
    if error:
        return error
    try:
        models.lock_scim_graph()
        resource = _get_scim_for_update(user_id, 'User')
        error = _if_match_error(resource, if_match)
        if error:
            models.db.session.rollback()
            return error
        error = _if_none_match_error(resource, if_none_match)
        if error:
            models.db.session.rollback()
            return error
        if not resource:
            models.db.session.rollback()
            return _scim_error(404, f'User {user_id} cannot be found')
        email = resource.user.email
        models.tombstone_scim_resource(
            resource,
            scrub_user_authority=True,
        )
        models.db.session.commit()
    except models.ScimGraphError as identity_error:
        models.db.session.rollback()
        return _scim_error(400, str(identity_error), 'invalidValue')
    except models.ScimIdentityError:
        models.db.session.rollback()
        flask.current_app.logger.exception(
            'SCIM User identity invariant failed during deletion'
        )
        return _scim_error(500, 'The SCIM User identity is inconsistent')
    except SQLAlchemyError:
        models.db.session.rollback()
        flask.current_app.logger.exception('SCIM User deletion failed')
        return _scim_error(500, 'The SCIM User could not be deleted')
    try:
        utils.MailuSessionExtension.prune_sessions(uid=email)
    except Exception:
        flask.current_app.logger.exception(
            'SCIM post-commit session cleanup failed'
        )
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
    """Resolve Bulk references only in Group member reference slots."""
    if not isinstance(value, dict):
        return value
    resolved = dict(value)
    if 'members' in resolved:
        members = resolved['members']
        if isinstance(members, list):
            resolved_members = []
            for member in members:
                if (
                    isinstance(member, str)
                    and member.startswith('bulkId:')
                ):
                    member = bulk_ids.get(member[7:], member)
                elif isinstance(member, dict):
                    member = dict(member)
                    reference = member.get('value')
                    if (
                        isinstance(reference, str)
                        and reference.startswith('bulkId:')
                    ):
                        member['value'] = bulk_ids.get(
                            reference[7:],
                            reference,
                        )
                resolved_members.append(member)
            resolved['members'] = resolved_members
    operations = resolved.get('Operations')
    if isinstance(operations, list):
        resolved_operations = []
        for operation in operations:
            if not isinstance(operation, dict):
                resolved_operations.append(operation)
                continue
            operation = dict(operation)
            path = operation.get('path')
            if not path and isinstance(operation.get('value'), dict):
                operation['value'] = _resolve_bulk_ids(
                    operation['value'],
                    bulk_ids,
                )
            elif isinstance(path, str):
                core_path = _schema_path(path.strip(), SCIM_GROUP_SCHEMA)
                if core_path.casefold() == 'members':
                    wrapped = {
                        'members': (
                            operation.get('value')
                            if isinstance(operation.get('value'), list)
                            else [operation.get('value')]
                        )
                    }
                    operation['value'] = _resolve_bulk_ids(
                        wrapped,
                        bulk_ids,
                    )['members']
            resolved_operations.append(operation)
        resolved['Operations'] = resolved_operations
    return resolved


def _member_bulk_references(value):
    references = set()
    if not isinstance(value, dict):
        return references
    members = value.get('members')
    if isinstance(members, list):
        for member in members:
            reference = (
                member.get('value')
                if isinstance(member, dict)
                else member
            )
            if isinstance(reference, str) and reference.startswith('bulkId:'):
                references.add(reference[7:])
    operations = value.get('Operations')
    if isinstance(operations, list):
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            path = operation.get('path')
            if not path and isinstance(operation.get('value'), dict):
                references.update(
                    _member_bulk_references(operation['value'])
                )
            elif isinstance(path, str):
                core_path = _schema_path(path.strip(), SCIM_GROUP_SCHEMA)
                if core_path.casefold() == 'members':
                    item = operation.get('value')
                    references.update(_member_bulk_references({
                        'members': item if isinstance(item, list) else [item],
                    }))
    return references


def _bulk_id_references(value):
    return _member_bulk_references(value)


def _path_bulk_reference(operation):
    path = operation.get('path')
    if not isinstance(path, str):
        return set()
    parts = path.lstrip('/').split('/', 1)
    if len(parts) == 2 and parts[1].startswith('bulkId:'):
        return {parts[1][7:]}
    return set()


def _operation_bulk_references(operation):
    references = _member_bulk_references(operation.get('data'))
    references.update(_path_bulk_reference(operation))
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
    operations = data['Operations'] if 'Operations' in data else data.get('operations')
    if not isinstance(operations, list):
        return _scim_error(400, 'Operations must be a list', 'invalidSyntax')
    if not operations:
        return _scim_error(400, 'Operations must not be empty', 'invalidValue')
    if len(operations) > SCIM_MAX_BULK_OPERATIONS:
        return _scim_error(413, 'Too many bulk operations', 'tooMany')
    fail_on_errors = data.get('failOnErrors', len(operations))
    if (
        isinstance(fail_on_errors, bool)
        or not isinstance(fail_on_errors, int)
        or fail_on_errors < 0
    ):
        return _scim_error(400, 'failOnErrors must be a non-negative integer', 'invalidValue')
    bulk_id_values = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        bulk_id = operation.get('bulkId')
        method_value = operation.get('method')
        if not isinstance(method_value, str):
            return _scim_error(400, 'Bulk operation method must be a string', 'invalidValue')
        method = method_value.upper()
        if method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return _scim_error(400, f'Unsupported bulk method {method!r}', 'invalidValue')
        if method == 'POST' and (not isinstance(bulk_id, str) or not bulk_id):
            return _scim_error(400, 'POST bulk operations require a non-empty bulkId', 'invalidValue')
        if method != 'POST' and bulk_id is not None:
            return _scim_error(400, 'bulkId is permitted only for POST operations', 'invalidValue')
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
