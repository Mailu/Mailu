""" Mailu command line interface
"""

import sys
import os
import socket
import uuid

import click

from flask import current_app as app
from flask.cli import FlaskGroup, with_appcontext
from marshmallow.exceptions import ValidationError

from . import models
from .schemas import MailuSchema


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
        email = '{}@{}'.format(localpart, domain_name)
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
    email = '{0}@{1}'.format(localpart, domain_name)
    user   = models.User.query.get(email)
    if hash_scheme is None:
        hash_scheme = app.config['PASSWORD_SCHEME']
    if user:
        user.set_password(password, hash_scheme=hash_scheme)
    else:
        print("User " + email + " not found.")
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
    """ Import a user along with password hash.
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


# @mailu.command()
# @click.option('-v', '--verbose', is_flag=True, help='Increase verbosity')
# @click.option('-d', '--delete-objects', is_flag=True, help='Remove objects not included in yaml')
# @click.option('-n', '--dry-run', is_flag=True, help='Perform a trial run with no changes made')
# @click.argument('source', metavar='[FILENAME|-]', type=click.File(mode='r'), default=sys.stdin)
# @with_appcontext
# def config_update(verbose=False, delete_objects=False, dry_run=False, source=None):
#     """ Update configuration with data from YAML-formatted input
#     """

    # try:
    #     new_config = yaml.safe_load(source)
    # except (yaml.scanner.ScannerError, yaml.parser.ParserError) as exc:
    #     print(f'[ERROR] Invalid yaml: {exc}')
    #     sys.exit(1)
    # else:
    #     if isinstance(new_config, str):
    #         print(f'[ERROR] Invalid yaml: {new_config!r}')
    #         sys.exit(1)
    #     elif new_config is None or not new_config:
    #         print('[ERROR] Empty yaml: Please pipe yaml into stdin')
    #         sys.exit(1)

    # error = False
    # tracked = {}
    # for section, model in yaml_sections:

    #     items = new_config.get(section)
    #     if items is None:
    #         if delete_objects:
    #             print(f'[ERROR] Invalid yaml: Section "{section}" is missing')
    #             error = True
    #             break
    #         else:
    #             continue

    #     del new_config[section]

    #     if not isinstance(items, list):
    #         print(f'[ERROR] Section "{section}" must be a list, not {items.__class__.__name__}')
    #         error = True
    #         break
    #     elif not items:
    #         continue

    #     # create items
    #     for data in items:

    #         if verbose:
    #             print(f'Handling {model.__table__} data: {data!r}')

    #         try:
    #             changed = model.from_dict(data, delete_objects)
    #         except Exception as exc:
    #             print(f'[ERROR] {exc.args[0]} in data: {data}')
    #             error = True
    #             break

    #         for item, created in changed:

    #             if created is True:
    #                 # flush newly created item
    #                 db.session.add(item)
    #                 db.session.flush()
    #                 if verbose:
    #                     print(f'Added {item!r}: {item.to_dict()}')
    #                 else:
    #                     print(f'Added {item!r}')

    #             elif created:
    #                 # modified instance
    #                 if verbose:
    #                     for key, old, new in created:
    #                         print(f'Updated {key!r} of {item!r}: {old!r} -> {new!r}')
    #                 else:
    #                   print(f'Updated {item!r}: {", ".join(sorted([kon[0] for kon in created]))}')

    #             # track primary key of all items
    #             tracked.setdefault(item.__class__, set()).update(set([item._dict_pval()]))

    #     if error:
    #         break

    # # on error: stop early
    # if error:
    #     print('[ERROR] An error occured. Not committing changes.')
    #     db.session.rollback()
    #     sys.exit(1)

    # # are there sections left in new_config?
    # if new_config:
    #     print(f'[ERROR] Unknown section(s) in yaml: {", ".join(sorted(new_config.keys()))}')
    #     error = True

    # # test for conflicting domains
    # domains = set()
    # for model, items in tracked.items():
    #     if model in (models.Domain, models.Alternative, models.Relay):
    #         if domains & items:
    #             for fqdn in domains & items:
    #                 print(f'[ERROR] Duplicate domain name used: {fqdn}')
    #             error = True
    #         domains.update(items)

    # # delete items not tracked
    # if delete_objects:
    #     for model, items in tracked.items():
    #         for item in model.query.all():
    #             if not item._dict_pval() in items:
    #                 print(f'Deleted {item!r} {item}')
    #                 db.session.delete(item)

    # # don't commit when running dry
    # if dry_run:
    #     print('Dry run. Not commiting changes.')
    #     db.session.rollback()
    # else:
    #     db.session.commit()


SECTIONS = {'domains', 'relays', 'users', 'aliases'}


@mailu.command()
@click.option('-v', '--verbose', is_flag=True, help='Increase verbosity')
@click.option('-n', '--dry-run', is_flag=True, help='Perform a trial run with no changes made')
@click.argument('source', metavar='[FILENAME|-]', type=click.File(mode='r'), default=sys.stdin)
@with_appcontext
def config_import(verbose=False, dry_run=False, source=None):
    """ Import configuration YAML
    """

    context = {
        'verbose': verbose, # TODO: use callback function to be verbose?
        'import': True,
    }

    try:
        config = MailuSchema(context=context).loads(source)
    except ValidationError as exc:
        print(f'[ERROR] {exc}')
        # TODO: show nice errors
        from pprint import pprint
        pprint(exc.messages)
        sys.exit(1)
    else:
        print(config)
        print(MailuSchema().dumps(config))
        # TODO: does not commit yet.
        # TODO: delete other entries?

    # don't commit when running dry
    if True: #dry_run:
        print('Dry run. Not commiting changes.')
        db.session.rollback()
    else:
        db.session.commit()


@mailu.command()
@click.option('-f', '--full', is_flag=True, help='Include attributes with default value')
@click.option('-s', '--secrets', is_flag=True,
              help='Include secret attributes (dkim-key, passwords)')
@click.option('-d', '--dns', is_flag=True, help='Include dns records')
@click.option('-o', '--output-file', 'output', default=sys.stdout, type=click.File(mode='w'),
              help='save yaml to file')
@click.argument('sections', nargs=-1)
@with_appcontext
def config_dump(full=False, secrets=False, dns=False, output=None, sections=None):
    """ Dump configuration as YAML to stdout or file

    SECTIONS can be: domains, relays, users, aliases
    """

    if sections:
        for section in sections:
            if section not in SECTIONS:
                print(f'[ERROR] Unknown section: {section!r}')
                sys.exit(1)
        sections = set(sections)
    else:
        sections = SECTIONS

    context={
        'full': full,
        'secrets': secrets,
        'dns': dns,
    }

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
        email="%s@%s" % (localpart, domain_name)
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
    manageruser = models.User.query.get(user_name + '@' + domain_name)
    domain.managers.append(manageruser)
    db.session.add(domain)
    db.session.commit()
