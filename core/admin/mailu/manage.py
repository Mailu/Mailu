""" Mailu command line interface
"""

import sys
import os
import socket
import logging
import uuid

from collections import Counter
from itertools import chain

import click
import sqlalchemy
import yaml

from flask import current_app as app
from flask.cli import FlaskGroup, with_appcontext
from marshmallow.exceptions import ValidationError

from . import models
from .schemas import MailuSchema, get_schema, get_fieldspec, colorize, RenderJSON, HIDDEN


db = models.db


@click.group(cls=FlaskGroup, context_settings={'help_option_names': ['-?', '-h', '--help']})
def mailu():
    """ Mailu command line
    """


@mailu.command()
@with_appcontext
def advertise():
    """ Advertise this server against statistic services.
    """
    if os.path.isfile(app.config['INSTANCE_ID_PATH']):
        with open(app.config['INSTANCE_ID_PATH'], 'r') as handle:
            instance_id = handle.read()
    else:
        instance_id = str(uuid.uuid4())
        with open(app.config['INSTANCE_ID_PATH'], 'w') as handle:
            handle.write(instance_id)
    if not app.config['DISABLE_STATISTICS']:
        try:
            socket.gethostbyname(app.config['STATS_ENDPOINT'].format(instance_id))
        except OSError:
            pass


@mailu.command()
@click.argument('localpart')
@click.argument('domain_name')
@click.argument('password')
@click.option('-m', '--mode')
@with_appcontext
def admin(localpart, domain_name, password, mode='create'):
    """ Create an admin user
        'mode' can be:
            - 'create' (default) Will try to create user and will raise an exception if present
            - 'ifmissing': if user exists, nothing happens, else it will be created
            - 'update': user is created or, if it exists, its password gets updated
    """
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)

    user = None
    if mode == 'ifmissing' or mode == 'update':
        email = f'{localpart}@{domain_name}'
        user = models.User.query.get(email)

        if user and mode == 'ifmissing':
            print('user %s exists, not updating' % email)
            return

    if not user:
        user = models.User(
            localpart=localpart,
            domain=domain,
            global_admin=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print("created admin user")
    elif mode == 'update':
        user.set_password(password)
        db.session.commit()
        print("updated admin password")



@mailu.command()
@click.argument('localpart')
@click.argument('domain_name')
@click.argument('password')
@click.argument('hash_scheme', required=False)
@with_appcontext
def user(localpart, domain_name, password, hash_scheme=None):
    """ Create a user
    """
    if hash_scheme is None:
        hash_scheme = app.config['PASSWORD_SCHEME']
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)
    user = models.User(
        localpart=localpart,
        domain=domain,
        global_admin=False
    )
    user.set_password(password, hash_scheme=hash_scheme)
    db.session.add(user)
    db.session.commit()


@mailu.command()
@click.argument('localpart')
@click.argument('domain_name')
@click.argument('password')
@click.argument('hash_scheme', required=False)
@with_appcontext
def password(localpart, domain_name, password, hash_scheme=None):
    """ Change the password of an user
    """
    email = f'{localpart}@{domain_name}'
    user = models.User.query.get(email)
    if hash_scheme is None:
        hash_scheme = app.config['PASSWORD_SCHEME']
    if user:
        user.set_password(password, hash_scheme=hash_scheme)
    else:
        print(f'User {email} not found.')
    db.session.commit()


@mailu.command()
@click.argument('domain_name')
@click.option('-u', '--max-users')
@click.option('-a', '--max-aliases')
@click.option('-q', '--max-quota-bytes')
@with_appcontext
def domain(domain_name, max_users=-1, max_aliases=-1, max_quota_bytes=0):
    """ Create a domain
    """
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name, max_users=max_users,
                               max_aliases=max_aliases, max_quota_bytes=max_quota_bytes)
        db.session.add(domain)
        db.session.commit()


@mailu.command()
@click.argument('localpart')
@click.argument('domain_name')
@click.argument('password_hash')
@click.argument('hash_scheme')
@with_appcontext
def user_import(localpart, domain_name, password_hash, hash_scheme = None):
    """ Import a user along with password hash
    """
    if hash_scheme is None:
        hash_scheme = app.config['PASSWORD_SCHEME']
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)
    user = models.User(
        localpart=localpart,
        domain=domain,
        global_admin=False
    )
    user.set_password(password_hash, hash_scheme=hash_scheme, raw=True)
    db.session.add(user)
    db.session.commit()


# TODO: remove deprecated config_update function?
@mailu.command()
@click.option('-v', '--verbose')
@click.option('-d', '--delete-objects')
@with_appcontext
def config_update(verbose=False, delete_objects=False):
    """ Sync configuration with data from YAML (deprecated)
    """
    new_config = yaml.safe_load(sys.stdin)
    # print new_config
    domains = new_config.get('domains', [])
    tracked_domains = set()
    for domain_config in domains:
        if verbose:
            print(str(domain_config))
        domain_name = domain_config['name']
        max_users = domain_config.get('max_users', -1)
        max_aliases = domain_config.get('max_aliases', -1)
        max_quota_bytes = domain_config.get('max_quota_bytes', 0)
        tracked_domains.add(domain_name)
        domain = models.Domain.query.get(domain_name)
        if not domain:
            domain = models.Domain(name=domain_name,
                                   max_users=max_users,
                                   max_aliases=max_aliases,
                                   max_quota_bytes=max_quota_bytes)
            db.session.add(domain)
            print(f'Added {domain_config}')
        else:
            domain.max_users = max_users
            domain.max_aliases = max_aliases
            domain.max_quota_bytes = max_quota_bytes
            db.session.add(domain)
            print(f'Updated {domain_config}')

    users = new_config.get('users', [])
    tracked_users = set()
    user_optional_params = ('comment', 'quota_bytes', 'global_admin',
                            'enable_imap', 'enable_pop', 'forward_enabled',
                            'forward_destination', 'reply_enabled',
                            'reply_subject', 'reply_body', 'displayed_name',
                            'spam_enabled', 'email', 'spam_threshold')
    for user_config in users:
        if verbose:
            print(str(user_config))
        localpart = user_config['localpart']
        domain_name = user_config['domain']
        password_hash = user_config.get('password_hash', None)
        hash_scheme = user_config.get('hash_scheme', None)
        domain = models.Domain.query.get(domain_name)
        email = f'{localpart}@{domain_name}'
        optional_params = {}
        for k in user_optional_params:
            if k in user_config:
                optional_params[k] = user_config[k]
        if not domain:
            domain = models.Domain(name=domain_name)
            db.session.add(domain)
        user = models.User.query.get(email)
        tracked_users.add(email)
        tracked_domains.add(domain_name)
        if not user:
            user = models.User(
                localpart=localpart,
                domain=domain,
                **optional_params
            )
        else:
            for k in optional_params:
                setattr(user, k, optional_params[k])
        user.set_password(password_hash, hash_scheme=hash_scheme, raw=True)
        db.session.add(user)

    aliases = new_config.get('aliases', [])
    tracked_aliases = set()
    for alias_config in aliases:
        if verbose:
            print(str(alias_config))
        localpart = alias_config['localpart']
        domain_name = alias_config['domain']
        if isinstance(alias_config['destination'], str):
            destination = alias_config['destination'].split(',')
        else:
            destination = alias_config['destination']
        wildcard = alias_config.get('wildcard', False)
        domain = models.Domain.query.get(domain_name)
        email = f'{localpart}@{domain_name}'
        if not domain:
            domain = models.Domain(name=domain_name)
            db.session.add(domain)
        alias = models.Alias.query.get(email)
        tracked_aliases.add(email)
        tracked_domains.add(domain_name)
        if not alias:
            alias = models.Alias(
                localpart=localpart,
                domain=domain,
                wildcard=wildcard,
                destination=destination,
                email=email
            )
        else:
            alias.destination = destination
            alias.wildcard = wildcard
        db.session.add(alias)

    db.session.commit()

    managers = new_config.get('managers', [])
    # tracked_managers=set()
    for manager_config in managers:
        if verbose:
            print(str(manager_config))
        domain_name = manager_config['domain']
        user_name = manager_config['user']
        domain = models.Domain.query.get(domain_name)
        manageruser = models.User.query.get(f'{user_name}@{domain_name}')
        if manageruser not in domain.managers:
            domain.managers.append(manageruser)
        db.session.add(domain)

    db.session.commit()

    if delete_objects:
        for user in db.session.query(models.User).all():
            if not user.email in tracked_users:
                if verbose:
                    print(f'Deleting user: {user.email}')
                db.session.delete(user)
        for alias in db.session.query(models.Alias).all():
            if not alias.email in tracked_aliases:
                if verbose:
                    print(f'Deleting alias: {alias.email}')
                db.session.delete(alias)
        for domain in db.session.query(models.Domain).all():
            if not domain.name in tracked_domains:
                if verbose:
                    print(f'Deleting domain: {domain.name}')
                db.session.delete(domain)
    db.session.commit()


@mailu.command()
@click.option('-v', '--verbose', count=True, help='Increase verbosity.')
@click.option('-s', '--secrets', is_flag=True, help='Show secret attributes in messages.')
@click.option('-q', '--quiet', is_flag=True, help='Quiet mode - only show errors.')
@click.option('-c', '--color', is_flag=True, help='Force colorized output.')
@click.option('-u', '--update', is_flag=True, help='Update mode - merge input with existing config.')
@click.option('-n', '--dry-run', is_flag=True, help='Perform a trial run with no changes made.')
@click.argument('source', metavar='[FILENAME|-]', type=click.File(mode='r'), default=sys.stdin)
@with_appcontext
def config_import(verbose=0, secrets=False, quiet=False, color=False, update=False, dry_run=False, source=None):
    """ Import configuration as YAML or JSON from stdin or file
    """

    # verbose
    # 0 : show number of changes
    # 1 : also show changes
    # 2 : also show secrets
    # 3 : also show input data
    # 4 : also show sql queries
    # 5 : also show tracebacks

    if quiet:
        verbose = -1

    color_cfg = {
        'color': color or sys.stdout.isatty(),
        'lexer': 'python',
        'strip': True,
    }

    counter = Counter()
    logger = {}

    def format_errors(store, path=None):

        res = []
        if path is None:
            path = []
        for key in sorted(store):
            location = path + [str(key)]
            value = store[key]
            if isinstance(value, dict):
                res.extend(format_errors(value, location))
            else:
                for message in value:
                    res.append((".".join(location), message))

        if path:
            return res

        fmt = f'     - {{:<{max([len(loc) for loc, msg in res])}}} : {{}}'
        res = [fmt.format(loc, msg) for loc, msg in res]
        num = f'error{["s",""][len(res)==1]}'
        res.insert(0, f'[ValidationError] {len(res)} {num} occured during input validation')

        return '\n'.join(res)

    def format_changes(*message):
        if counter:
            changes = []
            last = None
            for (action, what), count in sorted(counter.items()):
                if action != last:
                    if last:
                        changes.append('/')
                    changes.append(f'{action}:')
                    last = action
                changes.append(f'{what}({count})')
        else:
            changes = ['No changes.']
        return chain(message, changes)

    def log(action, target, message=None):

        if message is None:
            try:
                message = logger[target.__class__].dump(target)
            except KeyError:
                message = target
        if not isinstance(message, str):
            message = repr(message)
        print(f'{action} {target.__table__}: {colorize(message, **color_cfg)}')

    def listen_insert(mapper, connection, target): # pylint: disable=unused-argument
        """ callback function to track import """
        counter.update([('Created', target.__table__.name)])
        if verbose >= 1:
            log('Created', target)

    def listen_update(mapper, connection, target): # pylint: disable=unused-argument
        """ callback function to track import """

        changed = {}
        inspection = sqlalchemy.inspect(target)
        for attr in sqlalchemy.orm.class_mapper(target.__class__).column_attrs:
            history = getattr(inspection.attrs, attr.key).history
            if history.has_changes() and history.deleted:
                before = history.deleted[-1]
                after = getattr(target, attr.key)
                # TODO: remove special handling of "comment" after modifying model
                if attr.key == 'comment' and not before and not after:
                    pass
                # only remember changed keys
                elif before != after:
                    if verbose >= 1:
                        changed[str(attr.key)] = (before, after)
                    else:
                        break

        if verbose >= 1:
            # use schema with dump_context to hide secrets and sort keys
            dumped = get_schema(target)(only=changed.keys(), context=diff_context).dump(target)
            for key, value in dumped.items():
                before, after = changed[key]
                if value == HIDDEN:
                    before = HIDDEN if before else before
                    after = HIDDEN if after else after
                else:
                    # TODO: need to use schema to "convert" before value?
                    after = value
                log('Modified', target, f'{str(target)!r} {key}: {before!r} -> {after!r}')

        if changed:
            counter.update([('Modified', target.__table__.name)])

    def listen_delete(mapper, connection, target): # pylint: disable=unused-argument
        """ callback function to track import """
        counter.update([('Deleted', target.__table__.name)])
        if verbose >= 1:
            log('Deleted', target)

    # TODO: this listener will not be necessary, if dkim keys would be stored in database
    _dedupe_dkim = set()
    def listen_dkim(session, flush_context): # pylint: disable=unused-argument
        """ callback function to track import """
        for target in session.identity_map.values():
            # look at Domains originally loaded from db
            if not isinstance(target, models.Domain) or not target._sa_instance_state.load_path:
                continue
            before = target._dkim_key_on_disk
            after = target._dkim_key
            if before != after:
                if secrets:
                    before = before.decode('ascii', 'ignore')
                    after = after.decode('ascii', 'ignore')
                else:
                    before = HIDDEN if before else ''
                    after = HIDDEN if after else ''
                # "de-dupe" messages; this event is fired at every flush
                if not (target, before, after) in _dedupe_dkim:
                    _dedupe_dkim.add((target, before, after))
                    counter.update([('Modified', target.__table__.name)])
                    if verbose >= 1:
                        log('Modified', target, f'{str(target)!r} dkim_key: {before!r} -> {after!r}')

    def track_serialize(obj, item, backref=None):
        """ callback function to track import """
        # called for backref modification?
        if backref is not None:
            log('Modified', item, '{target!r} {key}: {before!r} -> {after!r}'.format(**backref))
            return
        # verbose?
        if not verbose >= 2:
            return
        # hide secrets in data
        data = logger[obj.opts.model].hide(item)
        if 'hash_password' in data:
            data['password'] = HIDDEN
        if 'fetches' in data:
            for fetch in data['fetches']:
                fetch['password'] = HIDDEN
        log('Handling', obj.opts.model, data)

    # configure contexts
    diff_context = {
        'full': True,
        'secrets': secrets,
    }
    log_context = {
        'secrets': secrets,
    }
    load_context = {
        'import': True,
        'update': update,
        'clear': not update,
        'callback': track_serialize,
    }

    # register listeners
    for schema in get_schema():
        model = schema.Meta.model
        logger[model] = schema(context=log_context)
        sqlalchemy.event.listen(model, 'after_insert', listen_insert)
        sqlalchemy.event.listen(model, 'after_update', listen_update)
        sqlalchemy.event.listen(model, 'after_delete', listen_delete)

    # special listener for dkim_key changes
    sqlalchemy.event.listen(db.session, 'after_flush', listen_dkim)

    if verbose >= 3:
        logging.basicConfig()
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    try:
        with models.db.session.no_autoflush:
            config = MailuSchema(only=MailuSchema.Meta.order, context=load_context).loads(source)
    except ValidationError as exc:
        raise click.ClickException(format_errors(exc.messages)) from exc
    except Exception as exc:
        if verbose >= 5:
            raise
        # (yaml.scanner.ScannerError, UnicodeDecodeError, ...)
        raise click.ClickException(
            f'[{exc.__class__.__name__}] '
            f'{" ".join(str(exc).split())}'
        ) from exc

    # flush session to show/count all changes
    if dry_run or verbose >= 1:
        db.session.flush()

    # check for duplicate domain names
    dup = set()
    for fqdn in chain(
        db.session.query(models.Domain.name),
        db.session.query(models.Alternative.name),
        db.session.query(models.Relay.name)
    ):
        if fqdn in dup:
            raise click.ClickException(f'[ValidationError] Duplicate domain name: {fqdn}')
        dup.add(fqdn)

    # don't commit when running dry
    if dry_run:
        if not quiet:
            print(*format_changes('Dry run. Not commiting changes.'))
        db.session.rollback()
    else:
        if not quiet:
            print(*format_changes('Committing changes.'))
        db.session.commit()


@mailu.command()
@click.option('-f', '--full', is_flag=True, help='Include attributes with default value.')
@click.option('-s', '--secrets', is_flag=True,
              help='Include secret attributes (dkim-key, passwords).')
@click.option('-c', '--color', is_flag=True, help='Force colorized output.')
@click.option('-d', '--dns', is_flag=True, help='Include dns records.')
@click.option('-o', '--output-file', 'output', default=sys.stdout, type=click.File(mode='w'),
              help='Save configuration to file.')
@click.option('-j', '--json', 'as_json', is_flag=True, help='Export configuration in json format.')
@click.argument('only', metavar='[FILTER]...', nargs=-1)
@with_appcontext
def config_export(full=False, secrets=False, color=False, dns=False, output=None, as_json=False, only=None):
    """ Export configuration as YAML or JSON to stdout or file
    """

    if only:
        for spec in only:
            if spec.split('.', 1)[0] not in MailuSchema.Meta.order:
                raise click.ClickException(f'[ERROR] Unknown section: {spec}')
    else:
        only = MailuSchema.Meta.order

    context = {
        'full': full,
        'secrets': secrets,
        'dns': dns,
    }

    schema = MailuSchema(only=only, context=context)
    color_cfg = {'color': color or output.isatty()}

    if as_json:
        schema.opts.render_module = RenderJSON
        color_cfg['lexer'] = 'json'
        color_cfg['strip'] = True

    try:
        print(colorize(schema.dumps(models.MailuConfig()), **color_cfg), file=output)
    except ValueError as exc:
        if spec := get_fieldspec(exc):
            raise click.ClickException(f'[ERROR] Invalid filter: {spec}') from exc
        raise


@mailu.command()
@click.argument('email')
@with_appcontext
def user_delete(email):
    """delete user"""
    user = models.User.query.get(email)
    if user:
        db.session.delete(user)
    db.session.commit()


@mailu.command()
@click.argument('email')
@with_appcontext
def alias_delete(email):
    """delete alias"""
    alias = models.Alias.query.get(email)
    if alias:
        db.session.delete(alias)
    db.session.commit()


@mailu.command()
@click.argument('localpart')
@click.argument('domain_name')
@click.argument('destination')
@click.option('-w', '--wildcard', is_flag=True)
@with_appcontext
def alias(localpart, domain_name, destination, wildcard=False):
    """ Create an alias
    """
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)
    alias = models.Alias(
        localpart=localpart,
        domain=domain,
        wildcard=wildcard,
        destination=destination.split(','),
        email=f'{localpart}@{domain_name}'
    )
    db.session.add(alias)
    db.session.commit()


@mailu.command()
@click.argument('domain_name')
@click.argument('max_users')
@click.argument('max_aliases')
@click.argument('max_quota_bytes')
@with_appcontext
def setlimits(domain_name, max_users, max_aliases, max_quota_bytes):
    """ Set domain limits
    """
    domain = models.Domain.query.get(domain_name)
    domain.max_users = max_users
    domain.max_aliases = max_aliases
    domain.max_quota_bytes = max_quota_bytes
    db.session.add(domain)
    db.session.commit()


@mailu.command()
@click.argument('domain_name')
@click.argument('user_name')
@with_appcontext
def setmanager(domain_name, user_name='manager'):
    """ Make a user manager of a domain
    """
    domain = models.Domain.query.get(domain_name)
    manageruser = models.User.query.get(f'{user_name}@{domain_name}')
    domain.managers.append(manageruser)
    db.session.add(domain)
    db.session.commit()
