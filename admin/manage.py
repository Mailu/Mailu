from mailu import manager, db
from mailu.admin import models


@manager.command
def flushdb():
    """ Flush the database
    """
    db.drop_all()


@manager.command
def initdb():
    """ Initialize the database
    """
    db.create_all()


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
def user(localpart, domain_name, password, hash_scheme='SHA512-CRYPT'):
    """ Create an user
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
def user_raw(localpart, domain_name, password, hash_scheme='SHA512-CRYPT'):
    """ Create an user
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
