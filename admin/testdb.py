from freeposte import db, models


if __name__ == "__main__":
    db.drop_all()
    db.create_all()
    db.session.commit()
