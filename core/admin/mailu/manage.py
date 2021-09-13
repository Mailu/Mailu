from mailu import models

from flask import current_app as app
from flask import cli as flask_cli

import flask
import os
import socket
import uuid
import click


db = models.db


@click.group()
def mailu(cls=flask_cli.FlaskGroup):
    """ Mailu command line
    """


@mailu.command()
@flask_cli.with_appcontext
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
@click.option('-m', '--mode', default='create', metavar='MODE', help='''\b'create' (default): create user. it's an error if user already exists
'ifmissing': only update password if user is missing
'update': create user or update password if user exists
''')
@flask_cli.with_appcontext
def admin(localpart, domain_name, password, mode):
    """ Create an admin user
    """

    if not mode in ('create', 'update', 'ifmissing'):
        raise click.ClickException(f'invalid mode: {mode!r}')

    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)

    email = f'{localpart}@{domain_name}'
    if user := models.User.query.get(email):
        if mode == 'ifmissing':
            print(f'user {email!r} exists, not updating')
            return
        elif mode == 'update':
            user.set_password(password)
            db.session.commit()
            print("updated admin password")
        else:
            raise click.ClickException(f'user {email!r} exists, not created')
    else:
        user = models.User(
            localpart=localpart,
            domain=domain,
            global_admin=True
        )
        db.session.add(user)
        user.set_password(password)
        db.session.commit()
        print("created admin user")


@mailu.command()
@click.argument('localpart')
@click.argument('domain_name')
@click.argument('password')
@click.argument('hash_scheme', required=False)
@flask_cli.with_appcontext
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
@flask_cli.with_appcontext
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
@flask_cli.with_appcontext
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
@flask_cli.with_appcontext
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


@mailu.command()
@click.option('-v', '--verbose')
@click.option('-d', '--delete-objects')
@flask_cli.with_appcontext
def config_update(verbose=False, delete_objects=False):
    """sync configuration with data from YAML-formatted stdin"""
    import yaml
    import sys
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
            print("Added " + str(domain_config))
        else:
            domain.max_users = max_users
            domain.max_aliases = max_aliases
            domain.max_quota_bytes = max_quota_bytes
            db.session.add(domain)
            print("Updated " + str(domain_config))

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
        email = '{0}@{1}'.format(localpart, domain_name)
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
        if type(alias_config['destination']) is str:
            destination = alias_config['destination'].split(',')
        else:
            destination = alias_config['destination']
        wildcard = alias_config.get('wildcard', False)
        domain = models.Domain.query.get(domain_name)
        email = '{0}@{1}'.format(localpart, domain_name)
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
        manageruser = models.User.query.get(user_name + '@' + domain_name)
        if manageruser not in domain.managers:
            domain.managers.append(manageruser)
        db.session.add(domain)

    db.session.commit()

    if delete_objects:
        for user in db.session.query(models.User).all():
            if not (user.email in tracked_users):
                if verbose:
                    print("Deleting user: " + str(user.email))
                db.session.delete(user)
        for alias in db.session.query(models.Alias).all():
            if not (alias.email in tracked_aliases):
                if verbose:
                    print("Deleting alias: " + str(alias.email))
                db.session.delete(alias)
        for domain in db.session.query(models.Domain).all():
            if not (domain.name in tracked_domains):
                if verbose:
                    print("Deleting domain: " + str(domain.name))
                db.session.delete(domain)
    db.session.commit()


@mailu.command()
@click.argument('email')
@flask_cli.with_appcontext
def user_delete(email):
    """delete user"""
    user = models.User.query.get(email)
    if user:
        db.session.delete(user)
    db.session.commit()


@mailu.command()
@click.argument('email')
@flask_cli.with_appcontext
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
@flask_cli.with_appcontext
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
@flask_cli.with_appcontext
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
@flask_cli.with_appcontext
def setmanager(domain_name, user_name='manager'):
    """ Make a user manager of a domain
    """
    domain = models.Domain.query.get(domain_name)
    manageruser = models.User.query.get(user_name + '@' + domain_name)
    domain.managers.append(manageruser)
    db.session.add(domain)
    db.session.commit()
