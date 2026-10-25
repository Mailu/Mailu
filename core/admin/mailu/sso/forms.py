from wtforms import validators, fields
from flask_babel import lazy_gettext as _
import flask_wtf

class LoginForm(flask_wtf.FlaskForm):
    email = fields.StringField(_('E-mail'), [validators.Email(), validators.DataRequired()], render_kw={'autofocus': True, 'type': 'email', 'autocomplete': 'username webauthn'})
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()], render_kw={'autocomplete': 'current-password'})
    destination = fields.SelectField(_('After sign-in'), choices=[('webmail', _('Webmail')), ('admin', _('Account settings'))])
    destination_explicit = fields.HiddenField(default='0')
    submit = fields.SubmitField(_('Sign in'))
    pwned = fields.HiddenField(label='', default=-1)
    submitWebmail = fields.SubmitField(_('Sign in'))
    submitAdmin = fields.SubmitField(_('Sign in'))

class PWChangeForm(flask_wtf.FlaskForm):
    oldpw = fields.PasswordField(_('Current password'), [validators.DataRequired()])
    pw = fields.PasswordField(_('New password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('New password (again)'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Change password'))


class AccountSetupForm(flask_wtf.FlaskForm):
    pw = fields.PasswordField(_('New password'), [validators.DataRequired(), validators.Length(min=8)])
    pw2 = fields.PasswordField(_('New password (again)'), [
        validators.DataRequired(), validators.EqualTo('pw'),
    ])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Set password'))
