from mailu import models
from .schemas import schemas

from flask import current_app as app
from flask.cli import FlaskGroup, with_appcontext

import os
import socket
import uuid
import click
import yaml
import sys


db = models.db


@click.group(cls=FlaskGroup)
def mailu():
    """ Mailu command line
    """


@mailu.command()
@with_appcontext
def advertise():
    """ Advertise this server against statistic services.
    """
    if os.path.isfile(app.config["INSTANCE_ID_PATH"]):
        with open(app.config["INSTANCE_ID_PATH"], "r") as handle:
            instance_id = handle.read()
    else:
        instance_id = str(uuid.uuid4())
        with open(app.config["INSTANCE_ID_PATH"], "w") as handle:
            handle.write(instance_id)
    if not app.config["DISABLE_STATISTICS"]:
        try:
            socket.gethostbyname(app.config["STATS_ENDPOINT"].format(instance_id))
        except:
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


yaml_sections = [
    ('domains', models.Domain),
    ('relays', models.Relay),
    ('users', models.User),
    ('aliases', models.Alias),
#    ('config', models.Config),
]

@mailu.command()
@click.option('-v', '--verbose', is_flag=True, help='Increase verbosity')
@click.option('-d', '--delete-objects', is_flag=True, help='Remove objects not included in yaml')
@click.option('-n', '--dry-run', is_flag=True, help='Perform a trial run with no changes made')
@with_appcontext
def config_update(verbose=False, delete_objects=False, dry_run=False, file=None):
    """sync configuration with data from YAML-formatted stdin"""

    out = (lambda *args: print('(DRY RUN)', *args)) if dry_run else print

    try:
        new_config = yaml.safe_load(sys.stdin)
    except (yaml.scanner.ScannerError, yaml.parser.ParserError) as reason:
        out(f'[ERROR] Invalid yaml: {reason}')
        sys.exit(1)
    else:
        if type(new_config) is str:
            out(f'[ERROR] Invalid yaml: {new_config!r}')
            sys.exit(1)
        elif new_config is None or not len(new_config):
            out('[ERROR] Empty yaml: Please pipe yaml into stdin')
            sys.exit(1)

    error = False
    tracked = {}
    for section, model in yaml_sections:

        items = new_config.get(section)
        if items is None:
            if delete_objects:
                out(f'[ERROR] Invalid yaml: Section "{section}" is missing')
                error = True
                break
            else:
                continue

        del new_config[section]

        if type(items) is not list:
            out(f'[ERROR] Section "{section}" must be a list, not {items.__class__.__name__}')
            error = True
            break
        elif not items:
            continue

        # create items
        for data in items:

            if verbose:
                out(f'Handling {model.__table__} data: {data!r}')

            try:
                changed = model.from_dict(data, delete_objects)
            except Exception as reason:
                out(f'[ERROR] {reason.args[0]} in data: {data}')
                error = True
                break

            for item, created in changed:

                if created is True:
                    # flush newly created item
                    db.session.add(item)
                    db.session.flush()
                    if verbose:
                        out(f'Added {item!r}: {item.to_dict()}')
                    else:
                        out(f'Added {item!r}')

                elif len(created):
                    # modified instance
                    if verbose:
                        for key, old, new in created:
                            out(f'Updated {key!r} of {item!r}: {old!r} -> {new!r}')
                    else:
                        out(f'Updated {item!r}: {", ".join(sorted([kon[0] for kon in created]))}')

                # track primary key of all items
                tracked.setdefault(item.__class__, set()).update(set([item._dict_pval()]))

        if error:
            break

    # on error: stop early
    if error:
        out('An error occured. Not committing changes.')
        db.session.rollback()
        sys.exit(1)

    # are there sections left in new_config?
    if new_config:
        out(f'[ERROR] Unknown section(s) in yaml: {", ".join(sorted(new_config.keys()))}')
        error = True

    # test for conflicting domains
    domains = set()
    for model, items in tracked.items():
        if model in (models.Domain, models.Alternative, models.Relay):
            if domains & items:
                for domain in domains & items:
                    out(f'[ERROR] Duplicate domain name used: {domain}')
                error = True
            domains.update(items)

    # delete items not tracked
    if delete_objects:
        for model, items in tracked.items():
            for item in model.query.all():
                if not item._dict_pval() in items:
                    out(f'Deleted {item!r} {item}')
                    db.session.delete(item)

    # don't commit when running dry
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()


@mailu.command()
@click.option('-f', '--full', is_flag=True, help='Include default attributes')
@click.option('-s', '--secrets', is_flag=True, help='Include secrets (dkim-key, plain-text / not hashed)')
@click.option('-d', '--dns', is_flag=True, help='Include dns records')
@click.argument('sections', nargs=-1)
@with_appcontext
def config_dump(full=False, secrets=False, dns=False, sections=None):
    """dump configuration as YAML-formatted data to stdout

    SECTIONS can be: domains, relays, users, aliases
    """

    class spacedDumper(yaml.Dumper):

        def write_line_break(self, data=None):
            super().write_line_break(data)
            if len(self.indents) == 1:
                super().write_line_break()

        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    if sections:
        for section in sections:
            if section not in schemas:
                print(f'[ERROR] Invalid section: {section}')
                return 1
    else:
        sections = sorted(schemas.keys())

# TODO: create World Schema and dump only this with Word.dumps ?

    for section in sections:
        schema = schemas[section](many=True)
        schema.context.update({
            'full': full,
            'secrets': secrets,
            'dns': dns,
        })
        yaml.dump(
            {section: schema.dump(schema.Meta.model.query.all())},
            sys.stdout,
            Dumper=spacedDumper,
            default_flow_style=False,
            allow_unicode=True
        )
        sys.stdout.write('\n')


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
