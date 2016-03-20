from freeposte import db, models
from passlib import hash


# Initialize the database
db.create_all()

domain = models.Domain(name="example.com")
user = models.User(
    localpart="admin",
    domain=domain,
    global_admin=True,
    password=hash.sha512_crypt.encrypt("admin").
)

db.session.add(domain)
db.session.add(user)
db.session.commit()
