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

@manager.option('-n','--domain_name',dest='domain_name')
@manager.option('-u','--max_users',dest='max_users')
@manager.option('-a','--max_aliases',dest='max_aliases')
@manager.option('-q','--max_quota_bytes',dest='max_quota_bytes')
def domain(domain_name, max_users=0, max_aliases=0, max_quota_bytes=0):
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)
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
def config_update(verbose=False, delete_objects=False):
    """sync configuration with data from YAML-formatted stdin"""
    import yaml, sys
    new_config=yaml.load(sys.stdin)
    # print new_config
    domains=new_config.get('domains',[])
    tracked_domains=set()
    for domain_config in domains:
        if verbose:
            domain_name = domain_config['name']
            max_users=domain_config.get('max_users',0)
            max_aliases=domain_config.get('max_aliases',0)
            max_quota_bytes=domain_config.get('max_quota_bytes',0)
            tracked_domains.add(domain_name)
            domain = models.Domain.query.get(domain_name)
            if not domain:
                domain = models.Domain(name=domain_name,
                        max_users=max_users,
                        max_aliases=max_aliases,
                        max_quota_bytes=max_quota_bytes)
                db.session.add(domain)
                print("Added "+str(domain_config))
            else:
                domain.max_users = max_users
                domain.max_aliases = max_aliases
                domain.max_quota_bytes = max_quota_bytes
                db.session.add(domain)
                print("Updated "+str(domain_config))

    users=new_config.get('users',[])
    tracked_users=set()
    user_optional_params=('comment','quota_bytes','global_admin',
            'enable_imap','enable_pop','forward_enabled','forward_destination',
            'reply_enabled','reply_subject','reply_body','displayed_name','spam_enabled',
            'email','spam_threshold')
    for user_config in users:
        if verbose:
            print(str(user_config))
        localpart=user_config['localpart']
        domain_name=user_config['domain']
        global_admin=user_config.get('global_admin',False)
        password_hash=user_config.get('password_hash',None)
        hash_scheme=user_config.get('hash_scheme',None)
        domain = models.Domain.query.get(domain_name)
        email='{0}@{1}'.format(localpart,domain_name)
        optional_params={}
        for k in user_optional_params:
            if k in user_config:
                optional_params[k]=user_config[k]
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
        user.set_password(password_hash, hash_scheme=hash_scheme, raw=True)
        db.session.add(user)

    aliases=new_config.get('aliases',[])
    tracked_aliases=set()
    for alias_config in aliases:
        if verbose:
            print(str(alias_config))
        localpart=alias_config['localpart']
        domain_name=alias_config['domain']
        destination=alias_config['destination']
        if type(alias_config['destination']) == str:
            destination = alias_config['destination'].split(',')
        else:
            destination = alias_config['destination']
        wildcard=alias_config.get('wildcard',False)
        domain = models.Domain.query.get(domain_name)
        email='{0}@{1}'.format(localpart,domain_name)
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
            alias.wildcard=wildcard
        db.session.add(alias)

    db.session.commit()

    managers=new_config.get('managers',[])
    # tracked_managers=set()
    for manager_config in managers:
        if verbose:
            print(str(manager_config))
        domain_name = manager_config['domain']
        user_name = manager_config['user']
        domain = models.Domain.query.get(domain_name)
        manageruser = models.User.query.get(user_name + '@' + domain_name)
        if not manageruser in domain.managers:
            domain.managers.append(manageruser)
        db.session.add(domain)
    
    db.session.commit()

    if delete_objects:
        for user in db.session.query(models.User).all():
            if not ( user.email in tracked_users ):
                if verbose:
                    print("Deleting user: "+str(user.email))
                db.session.delete(user)
        for alias in db.session.query(models.Alias).all():
            if not ( alias.email in tracked_aliases ):
                if verbose:
                    print("Deleting alias: "+str(alias.email))
                db.session.delete(alias)
        for domain in db.session.query(models.Domain).all():
            if not ( domain.name in tracked_domains ):
                if verbose:
                    print("Deleting domain: "+str(domain.name))
                db.session.delete(domain)
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


if __name__ == "__main__":
    manager.run()
