""" Mailu command line interface
"""

import sys
import os
import socket
import json
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
from .schemas import MailuSchema, get_schema


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


# TODO: remove this deprecated function
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


SECTIONS = {'domains', 'relays', 'users', 'aliases'}


@mailu.command()
@click.option('-v', '--verbose', count=True, help='Increase verbosity')
@click.option('-q', '--quiet', is_flag=True, help='Quiet mode - only show errors')
@click.option('-u', '--update', is_flag=True, help='Update mode - merge input with existing config')
@click.option('-n', '--dry-run', is_flag=True, help='Perform a trial run with no changes made')
@click.argument('source', metavar='[FILENAME|-]', type=click.File(mode='r'), default=sys.stdin)
@with_appcontext
def config_import(verbose=0, quiet=False, update=False, dry_run=False, source=None):
    """ Import configuration as YAML or JSON from stdin or file
    """

    # verbose
    # 0 : show number of changes
    # 1 : also show changes
    # 2 : also show secrets
    # 3 : also show input data
    # 4 : also show sql queries

    if quiet:
        verbose = -1

    counter = Counter()
    dumper = {}

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
            changes = 'no changes.'
        return chain(message, changes)

    def log(action, target, message=None):
        if message is None:
            message = json.dumps(dumper[target.__class__].dump(target), ensure_ascii=False)
        print(f'{action} {target.__table__}: {message}')

    def listen_insert(mapper, connection, target): # pylint: disable=unused-argument
        """ callback function to track import """
        counter.update([('Added', target.__table__.name)])
        if verbose >= 1:
            log('Added', target)

    def listen_update(mapper, connection, target): # pylint: disable=unused-argument
        """ callback function to track import """

        changed = {}
        inspection = sqlalchemy.inspect(target)
        for attr in sqlalchemy.orm.class_mapper(target.__class__).column_attrs:
            if getattr(inspection.attrs, attr.key).history.has_changes():
                if sqlalchemy.orm.attributes.get_history(target, attr.key)[2]:
                    before = sqlalchemy.orm.attributes.get_history(target, attr.key)[2].pop()
                    after = getattr(target, attr.key)
                    # only remember changed keys
                    if before != after and (before or after):
                        if verbose >= 1:
                            changed[str(attr.key)] = (before, after)
                        else:
                            break

        if verbose >= 1:
            # use schema with dump_context to hide secrets and sort keys
            primary = json.dumps(str(target), ensure_ascii=False)
            dumped = get_schema(target)(only=changed.keys(), context=dump_context).dump(target)
            for key, value in dumped.items():
                before, after = changed[key]
                if value == '<hidden>':
                    before = '<hidden>' if before else before
                    after = '<hidden>' if after else after
                else:
                    # TODO: use schema to "convert" before value?
                    after = value
                before = json.dumps(before, ensure_ascii=False)
                after = json.dumps(after, ensure_ascii=False)
                log('Modified', target, f'{primary} {key}: {before} -> {after}')

        if changed:
            counter.update([('Modified', target.__table__.name)])

    def listen_delete(mapper, connection, target): # pylint: disable=unused-argument
        """ callback function to track import """
        counter.update([('Deleted', target.__table__.name)])
        if verbose >= 1:
            log('Deleted', target)

    # this listener should not be necessary, when:
    # dkim keys should be stored in database and it should be possible to store multiple
    # keys per domain. the active key would be also stored on disk on commit.
    def listen_dkim(session, flush_context): # pylint: disable=unused-argument
        """ callback function to track import """
        for target in session.identity_map.values():
            if not isinstance(target, models.Domain):
                continue
            primary = json.dumps(str(target), ensure_ascii=False)
            before = target._dkim_key_on_disk
            after = target._dkim_key
            if before != after and (before or after):
                if verbose >= 2:
                    before = before.decode('ascii', 'ignore')
                    after = after.decode('ascii', 'ignore')
                else:
                    before = '<hidden>' if before else ''
                    after = '<hidden>' if after else ''
                before = json.dumps(before, ensure_ascii=False)
                after = json.dumps(after, ensure_ascii=False)
                log('Modified', target, f'{primary} dkim_key: {before} -> {after}')
                counter.update([('Modified', target.__table__.name)])

    def track_serialize(self, item):
        """ callback function to track import """
        log('Handling', self.opts.model, item)

    # configure contexts
    dump_context = {
        'secrets': verbose >= 2,
    }
    load_context = {
        'callback': track_serialize if verbose >= 3 else None,
        'clear': not update,
        'import': True,
    }

    # register listeners
    for schema in get_schema():
        model = schema.Meta.model
        dumper[model] = schema(context=dump_context)
        sqlalchemy.event.listen(model, 'after_insert', listen_insert)
        sqlalchemy.event.listen(model, 'after_update', listen_update)
        sqlalchemy.event.listen(model, 'after_delete', listen_delete)

    # special listener for dkim_key changes
    sqlalchemy.event.listen(db.session, 'after_flush', listen_dkim)

    if verbose >= 4:
        logging.basicConfig()
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    try:
        with models.db.session.no_autoflush:
            config = MailuSchema(only=SECTIONS, context=load_context).loads(source)
    except ValidationError as exc:
        raise click.ClickException(format_errors(exc.messages)) from exc
    except Exception as exc:
        # (yaml.scanner.ScannerError, UnicodeDecodeError, ...)
        raise click.ClickException(f'[{exc.__class__.__name__}] {" ".join(str(exc).split())}') from exc

    # flush session to show/count all changes
    if dry_run or verbose >= 1:
        db.session.flush()

    # check for duplicate domain names
    dup = set()
    for fqdn in chain(db.session.query(models.Domain.name),
                      db.session.query(models.Alternative.name),
                      db.session.query(models.Relay.name)):
        if fqdn in dup:
            raise click.ClickException(f'[ValidationError] Duplicate domain name: {fqdn}')
        dup.add(fqdn)

    # TODO: implement special update "items"
    # -pkey: which             - remove item "which"
    # -key: null or [] or {}   - set key to default
    # -pkey: null or [] or {}  - remove all existing items in this list

    # don't commit when running dry
    if dry_run:
        db.session.rollback()
        if not quiet:
            print(*format_changes('Dry run. Not commiting changes.'))
        # TODO: remove debug
        print(MailuSchema().dumps(config))
    else:
        db.session.commit()
        if not quiet:
            print(*format_changes('Commited changes.'))


@mailu.command()
@click.option('-f', '--full', is_flag=True, help='Include attributes with default value')
@click.option('-s', '--secrets', is_flag=True,
              help='Include secret attributes (dkim-key, passwords)')
@click.option('-d', '--dns', is_flag=True, help='Include dns records')
@click.option('-o', '--output-file', 'output', default=sys.stdout, type=click.File(mode='w'),
              help='save yaml to file')
@click.option('-j', '--json', 'as_json', is_flag=True, help='Dump in josn format')
@click.argument('sections', nargs=-1)
@with_appcontext
def config_export(full=False, secrets=False, dns=False, output=None, as_json=False, sections=None):
    """ Export configuration as YAML or JSON to stdout or file
    """

    if sections:
        for section in sections:
            if section not in SECTIONS:
                print(f'[ERROR] Unknown section: {section}')
                raise click.exceptions.Exit(1)
        sections = set(sections)
    else:
        sections = SECTIONS

    context = {
        'full': full,
        'secrets': secrets,
        'dns': dns,
    }

    if as_json:
        schema = MailuSchema(only=sections, context=context)
        schema.opts.render_module = json
        print(schema.dumps(models.MailuConfig(), separators=(',',':')), file=output)

    else:
        MailuSchema(only=sections, context=context).dumps(models.MailuConfig(), output)


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
