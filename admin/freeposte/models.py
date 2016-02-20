from freeposte import db


class Domain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    max_users = db.Column(db.Integer)
    max_aliases = db.Column(db.Integer)

    def __str__(self):
        return self.name


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    domain_id = db.Column(db.Integer, db.ForeignKey(Domain.id))
    domain = db.relationship(Domain, backref='users')
    password = db.Column(db.String(255))
    quota_bytes = db.Column(db.Integer())

    def __str__(self):
        return '{0}@{1}'.format(self.username, self.domain.name)


class Alias(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    localpart = db.Column(db.String(80))
    domain_id = db.Column(db.Integer, db.ForeignKey(Domain.id))
    domain = db.relationship(Domain, backref='aliases')
    destination = db.Column(db.String())

    def __str__(self):
        return '{0}@{1}'.format(self.username, self.domain.name)
