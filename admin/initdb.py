from freeposte import db


# Initialize the database
db.create_all()
db.session.commit()
