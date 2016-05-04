from flask_wtf import Form
from wtforms import validators, fields, widgets
from wtforms_components import fields as fields_


class LoginForm(Form):
    email = fields.StringField('E-mail', [validators.Email()])
    pw = fields.PasswordField('Password', [validators.DataRequired()])
    submit = fields.SubmitField('Sign in')


class DomainForm(Form):
    name = fields.StringField('Domain name', [validators.DataRequired()])
    max_users = fields_.IntegerField('Maximum user count', default=10)
    max_aliases = fields_.IntegerField('Maximum alias count', default=10)
    comment = fields.StringField('Comment')
    submit = fields.SubmitField('Create')


class UserForm(Form):
    localpart = fields.StringField('E-mail', [validators.DataRequired()])
    pw = fields.PasswordField('Password', [validators.DataRequired()])
    pw2 = fields.PasswordField('Confirm password', [validators.EqualTo('pw')])
    quota_bytes = fields_.DecimalSliderField('Quota', default=1000000000)
    enable_imap = fields.BooleanField('Allow IMAP access', default=True)
    enable_pop = fields.BooleanField('Allow POP3 access', default=True)
    comment = fields.StringField('Comment')
    submit = fields.SubmitField('Save')


class UserSettingsForm(Form):
    displayed_name = fields.StringField('Displayed name')
    spam_enabled = fields.BooleanField('Enable spam filter')
    spam_threshold = fields.DecimalField('Spam filter sensitivity')
    submit = fields.SubmitField('Save settings')


class UserPasswordForm(Form):
    pw = fields.PasswordField('Password', [validators.DataRequired()])
    pw2 = fields.PasswordField('Password check', [validators.DataRequired()])
    submit = fields.SubmitField('Update password')


class UserForwardForm(Form):
    forward_enabled = fields.BooleanField('Enable forwarding')
    forward_destination = fields.StringField(
        'Destination', [validators.Optional(), validators.Email()]
    )
    submit = fields.SubmitField('Update')


class UserReplyForm(Form):
    reply_enabled = fields.BooleanField('Enable automatic reply')
    reply_subject = fields.StringField('Reply subject')
    reply_body = fields.StringField('Reply body', widget=widgets.TextArea())
    submit = fields.SubmitField('Update')


class AliasForm(Form):
    localpart = fields.StringField('Alias', [validators.DataRequired()])
    destination = fields.StringField('Destination')
    comment = fields.StringField('Comment')
    submit = fields.SubmitField('Create')


class AdminForm(Form):
    admin = fields.StringField('Admin email', [validators.Email()])
    submit = fields.SubmitField('Submit')


class ManagerForm(Form):
    manager = fields.StringField('Manager email', [validators.Email()])
    submit = fields.SubmitField('Submit')


class FetchForm(Form):
    protocol = fields.SelectField('Protocol', choices=[
        ('imap', 'IMAP'), ('pop3', 'POP3')
    ])
    host = fields.StringField('Hostname or IP')
    port = fields.IntegerField('TCP port')
    tls = fields.BooleanField('Enable TLS')
    username = fields.StringField('Username')
    password = fields.StringField('Password')
    submit = fields.SubmitField('Submit')
