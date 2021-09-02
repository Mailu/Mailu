from wtforms import validators, fields, widgets
from wtforms_components import fields as fields_
from flask_babel import lazy_gettext as _

import flask_login
import flask_wtf
import re

LOCALPART_REGEX = "^[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*$"

class LoginForm(flask_wtf.FlaskForm):
    class Meta:
        csrf = False
    email = fields.StringField(_('E-mail'), [validators.Email()])
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    submit = fields.SubmitField(_('Sign in'))
