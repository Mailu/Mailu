from wtforms import validators, fields
from flask_babel import lazy_gettext as _
import flask_wtf

class LoginForm(flask_wtf.FlaskForm):
    class Meta:
        csrf = False
    email = fields.StringField(_('E-mail'), [validators.Email(), validators.DataRequired()])
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    submitWebmail = fields.SubmitField(_('Sign in'))
    submitAdmin = fields.SubmitField(_('Sign in'))
