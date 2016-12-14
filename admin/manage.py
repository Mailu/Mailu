from mailu import manager, db
from mailu.admin import models
from passlib import hash


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
        global_admin=True,
        password=hash.sha512_crypt.encrypt(password)
    )
    db.session.add(user)
    db.session.commit()

@manager.command
def user(localpart, domain_name, password):
    """ Create an user
    """
    domain = models.Domain.query.get(domain_name)
    if not domain:
        domain = models.Domain(name=domain_name)
        db.session.add(domain)
    user = models.User(
        localpart=localpart,
        domain=domain,
        global_admin=False,
        password=hash.sha512_crypt.encrypt(password)
    )
    db.session.add(user)
    db.session.commit()

if __name__ == "__main__":
    manager.run()
