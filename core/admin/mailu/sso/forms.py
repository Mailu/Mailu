from wtforms import validators, fields
from flask_babel import lazy_gettext as _
import flask_wtf

class LoginForm(flask_wtf.FlaskForm):
    class Meta:
        csrf = False
    email = fields.StringField(_('E-mail'), [validators.Email(), validators.DataRequired()], render_kw={'autofocus': True, 'type': 'email'})
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submitWebmail = fields.SubmitField(_('Sign in'))
    submitAdmin = fields.SubmitField(_('Sign in'))

class TOTPVerifyForm(flask_wtf.FlaskForm):
    class Meta:
        csrf = False
    code = fields.StringField(_('Authentication code'), [validators.DataRequired(), validators.Length(min=6, max=12)], render_kw={'autofocus': True, 'autocomplete': 'one-time-code', 'inputmode': 'numeric', 'pattern': '[0-9]*', 'maxlength': '9'})
    submitCode = fields.SubmitField(_('Verify'))
    submitBackup = fields.SubmitField(_('Use backup code'))

class PWChangeForm(flask_wtf.FlaskForm):
    oldpw = fields.PasswordField(_('Current password'), [validators.DataRequired()])
    pw = fields.PasswordField(_('New password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('New password (again)'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Change password'))
