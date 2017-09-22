from mailu import app, manager, db
from mailu.admin import models


@manager.command
def admin(localpart, domain_name, password):
    """ Create an admin user
    """
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)
    user = models.User(
        localpart=localpart,
        domain=domain,
        global_admin=True
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()


@manager.command
def user(localpart, domain_name, password, hash_scheme=app.config['PASSWORD_SCHEME']):
    """ Create a user
    """
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


@manager.command
def user_import(localpart, domain_name, password_hash, hash_scheme=app.config['PASSWORD_SCHEME']):
    """ Import a user along with password hash. Available hashes:
                   'SHA512-CRYPT'
                   'SHA256-CRYPT'
                   'MD5-CRYPT'
                   'CRYPT'
    """
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

@manager.command
def config_update(verbose=False, delete_objects=False):
    """sync configuration with data from YAML-formatted stdin"""
    import yaml, sys
    new_config=yaml.load(sys.stdin)
    # print new_config
    users=new_config['users']
    tracked_users=set()
    for user_config in users:
        if verbose:
            print(str(user_config))
        localpart=user_config['localpart']
        domain_name=user_config['domain']
        password_hash=user_config['password_hash']
        hash_scheme=user_config['hash_scheme']
        domain = models.Domain.query.get(domain_name)
        email='{0}@{1}'.format(localpart,domain_name)
        if not domain:
            domain = models.Domain(name=domain_name)
            db.session.add(domain)
        user = models.User.query.get(email)
        tracked_users.add(email)
        if not user:
            user = models.User(
                localpart=localpart,
                domain=domain,
                global_admin=False
            )
        user.set_password(password_hash, hash_scheme=hash_scheme, raw=True)
        db.session.add(user)

    aliases=new_config['aliases']
    tracked_aliases=set()
    for alias_config in aliases:
        if verbose:
            print(str(alias_config))
        localpart=alias_config['localpart']
        domain_name=alias_config['domain']
        pre_destination=alias_config['destination']
        if type(pre_destination) == type(""):
            destination = pre_destination.split(',')
        else:
            destination = pre_destination
        domain = models.Domain.query.get(domain_name)
        email='{0}@{1}'.format(localpart,domain_name)
        if not domain:
            domain = models.Domain(name=domain_name)
            db.session.add(domain)
        alias = models.Alias.query.get(email)
        tracked_aliases.add(email)
        if not alias:
            alias = models.Alias(
                localpart=localpart,
                domain=domain,
                destination=destination,
                email=email
            )
        else:
            alias.destination = destination
        db.session.add(alias)
    
    if delete_objects:
        for user in db.session.query(models.User).all():
            if not ( user.email in tracked_users ):
                db.session.delete(user)
        for alias in db.session.query(models.Alias).all():
            if not ( alias.email in tracked_aliases ):
                db.session.delete(alias)
    db.session.commit()

@manager.command
def user_delete(email):
    """delete user"""
    user = models.User.query.get(email)
    if user:
        db.session.delete(user)
    db.session.commit()

@manager.command
def alias_delete(email):
    """delete alias"""
    alias = models.Alias.query.get(email)
    if alias:
        db.session.delete(alias)
    db.session.commit()

@manager.command
def alias(localpart, domain_name, destination):
    """ Create an alias
    """
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)
    alias = models.Alias(
        localpart=localpart,
        domain=domain,
        destination=destination.split(','),
        email="%s@%s" % (localpart, domain_name)
    )
    db.session.add(alias)
    db.session.commit()

# Set limits to a domain
@manager.command
def setlimits(domain_name, max_users, max_aliases, max_quota_bytes):
  domain = models.Domain.query.get(domain_name)
  domain.max_users = max_users
  domain.max_aliases = max_aliases
  domain.max_quota_bytes = max_quota_bytes

  db.session.add(domain)
  db.session.commit()

# Make the user manager of a domain
@manager.command
def setmanager(domain_name, user_name='manager'):
  domain = models.Domain.query.get(domain_name)
  manageruser = models.User.query.get(user_name + '@' + domain_name)
  domain.managers.append(manageruser)
  db.session.add(domain)
  db.session.commit()


if __name__ == "__main__":
    manager.run()
