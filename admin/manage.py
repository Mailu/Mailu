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
def user_import(localpart, domain_name, password_hash, hash_scheme='SHA512-CRYPT'):
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
def config_update():
    """sync configuration with data from stdin"""
    import yaml, sys
    new_config=yaml.load(sys.stdin)
    # print new_config
    users=new_config['users']
    for user_config in users:
        localpart=user_config['localpart']
        domain_name=user_config['domain']
        password_hash=user_config['password_hash']
        hash_scheme=user_config['hash_scheme']
        domain = models.Domain.query.get(domain_name)
        if not domain:
            domain = models.Domain(name=domain_name)
            db.session.add(domain)
        user = models.User.query.get('{0}@{1}'.format(localpart,domain_name))
        if not user:
            user = models.User(
                localpart=localpart,
                domain=domain,
                global_admin=False
            )
        user.set_password(password_hash, hash_scheme=hash_scheme, raw=True)
        db.session.add(user)

    aliases=new_config['aliases']
    for alias_config in aliases:
        localpart=alias_config['localpart']
        domain_name=alias_config['domain']
        destination=alias_config['destination']
        domain = models.Domain.query.get(domain_name)
        if not domain:
            domain = models.Domain(name=domain_name)
            db.session.add(domain)
        alias = models.Alias.query.get('{0}@{1}'.format(localpart, domain_name))
        if not alias:
            alias = models.Alias(
                localpart=localpart,
                domain=domain,
                destination=destination.split(','),
                email="%s@%s" % (localpart, domain_name)
            )
        else:
            alias.destination = destination.split(',')
        db.session.add(alias)
    
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


if __name__ == "__main__":
    manager.run()
