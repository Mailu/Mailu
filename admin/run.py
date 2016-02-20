from freeposte import app, db


# Initialize the database if required (first launch)
db.create_all()
db.session.commit()


if __name__ == '__main__':
    app.run(debug=True)
