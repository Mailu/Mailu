from flask_wtf import Form
from wtforms import validators, fields, widgets
from wtforms_components import fields as fields_


class LoginForm(Form):
    email = fields.StringField('E-mail', [validators.Email()])
    pw = fields.PasswordField('Password', [validators.DataRequired()])
    submit = fields.SubmitField('Sign in')


class DomainCreateForm(Form):
    name = fields.StringField('Domain name', [validators.DataRequired()])
    comment = fields.StringField('Comment')
    submit = fields.SubmitField('Create')


class DomainEditForm(Form):
    max_users = fields.IntegerField('Maximum mailbox count')
    max_aliases = fields.IntegerField('Maximum aliases count')
    comment = fields.StringField('Comment')
    submit = fields.SubmitField('Save')


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
    forward = fields.StringField('Destination', [validators.Email()])
    submit = fields.SubmitField('Update')


class UserReplyForm(Form):
    reply_subject = fields.StringField('Reply subject')
    reply_body = fields.StringField('Reply body', widget=widgets.TextArea())
    submit = fields.SubmitField('Update')


class AliasForm(Form):
    localpart = fields.StringField('Alias', [validators.DataRequired()])
    destination = fields.StringField('Destination')
    comment = fields.StringField('Comment')
    submit = fields.SubmitField('Create')
