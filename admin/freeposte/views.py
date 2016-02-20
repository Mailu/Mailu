import flask_admin as admin
from flask_admin.contrib import sqla

from freeposte import app, db, models


# Flask admin
admin = admin.Admin(app, name='Freeposte.io', template_mode='bootstrap3')


class DomainModelView(sqla.ModelView):
    pass


class UserModelView(sqla.ModelView):
    pass


class AliasModelView(sqla.ModelView):
    pass


# Add views
admin.add_view(DomainModelView(models.Domain, db.session))
admin.add_view(UserModelView(models.User, db.session))
admin.add_view(AliasModelView(models.Alias, db.session))
