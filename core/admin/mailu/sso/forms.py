from wtforms import validators, fields
from flask_babel import lazy_gettext as _
import flask_wtf


class LoginForm(flask_wtf.FlaskForm):
    class Meta:
        csrf = False
    email = fields.StringField(_('E-mail'), [validators.Email(), validators.DataRequired()], render_kw={'autofocus': True})
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submitWebmail = fields.SubmitField(_('Sign in'))
    submitAdmin = fields.SubmitField(_('Sign in'))


class PWChangeForm(flask_wtf.FlaskForm):
    oldpw = fields.PasswordField(_('Current password'), [validators.DataRequired()])
    pw = fields.PasswordField(_('New password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('New password (again)'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Change password'))
