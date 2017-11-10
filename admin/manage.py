from mailu import manager, db
from mailu.admin import models

import os
import socket
import uuid


@manager.command
def advertise():
    """ Advertise this server against statistic services.
    """
    filepath = "/data/instance"
    endpoint = "14.{}.stats.mailu.io"
    if os.path.isfile(filepath):
        with open(filepath, "r") as handle:
            instance_id = handle.read()
    else:
        instance_id = str(uuid.uuid4())
        with open(filepath, "w") as handle:
            handle.write(instance_id)
    try:
        socket.gethostbyname(endpoint.format(instance_id))
    except:
        pass


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
        global_admin=False
    )
    user.set_password(password)
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


if __name__ == "__main__":
    manager.run()
