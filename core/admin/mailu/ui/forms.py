from wtforms import validators, fields, widgets
from wtforms_components import fields as fields_
from flask_babel import lazy_gettext as _

import flask_login
import flask_wtf
import re


class DestinationField(fields.SelectMultipleField):
    """ Allow for multiple emails selection from current user choices and
    additional email addresses.
    """

    validator = re.compile(r'^.+@([^.@][^@]+)$', re.IGNORECASE)

    def iter_choices(self):
        managed = [
            str(email)
            for email in flask_login.current_user.get_managed_emails()
        ]
        for email in managed:
            selected = self.data is not None and self.coerce(email) in self.data
            yield (email, email, selected)
        for email in self.data or ():
            if email not in managed:
                yield (email, email, True)

    def pre_validate(self, form):
        for item in self.data:
            if not self.validator.match(item):
                raise validators.ValidationError(_('Invalid email address.'))


class ConfirmationForm(flask_wtf.FlaskForm):
    submit = fields.SubmitField(_('Confirm'))


class LoginForm(flask_wtf.FlaskForm):
    email = fields.StringField(_('E-mail'), [validators.Email()])
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    submit = fields.SubmitField(_('Sign in'))


class DomainForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Domain name'), [validators.DataRequired()])
    max_users = fields_.IntegerField(_('Maximum user count'), default=10)
    max_aliases = fields_.IntegerField(_('Maximum alias count'), default=10)
    max_quota_bytes = fields_.IntegerSliderField(_('Maximum user quota'), default=0)
    comment = fields.StringField(_('Comment'))
    submit = fields.SubmitField(_('Create'))


class AlternativeForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Alternative name'), [validators.DataRequired()])
    submit = fields.SubmitField(_('Create'))


class RelayForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Relayed domain name'), [validators.DataRequired()])
    smtp = fields.StringField(_('Remote host'))
    comment = fields.StringField(_('Comment'))
    submit = fields.SubmitField(_('Create'))


class UserForm(flask_wtf.FlaskForm):
    localpart = fields.StringField(_('E-mail'), [validators.DataRequired()])
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('Confirm password'), [validators.EqualTo('pw')])
    quota_bytes = fields_.IntegerSliderField(_('Quota'), default=1000000000)
    enable_imap = fields.BooleanField(_('Allow IMAP access'), default=True)
    enable_pop = fields.BooleanField(_('Allow POP3 access'), default=True)
    comment = fields.StringField(_('Comment'))
    submit = fields.SubmitField(_('Save'))


class UserSettingsForm(flask_wtf.FlaskForm):
    displayed_name = fields.StringField(_('Displayed name'))
    spam_enabled = fields.BooleanField(_('Enable spam filter'))
    spam_threshold = fields_.IntegerSliderField(_('Spam filter tolerance'))
    submit = fields.SubmitField(_('Save settings'))


class UserPasswordForm(flask_wtf.FlaskForm):
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('Password check'), [validators.DataRequired()])
    submit = fields.SubmitField(_('Update password'))


class UserForwardForm(flask_wtf.FlaskForm):
    forward_enabled = fields.BooleanField(_('Enable forwarding'))
    forward_keep = fields.BooleanField(_('Keep a copy of the emails'))
    forward_destination = fields.StringField(
        _('Destination'), [validators.Optional(), validators.Email()]
    )
    submit = fields.SubmitField(_('Update'))


class UserReplyForm(flask_wtf.FlaskForm):
    reply_enabled = fields.BooleanField(_('Enable automatic reply'))
    reply_subject = fields.StringField(_('Reply subject'))
    reply_body = fields.StringField(_('Reply body'),
        widget=widgets.TextArea())
    reply_enddate = fields.html5.DateField(_('End of vacation'))
    submit = fields.SubmitField(_('Update'))


class TokenForm(flask_wtf.FlaskForm):
    displayed_password = fields.StringField(
        _('Your token (write it down, as it will never be displayed again)')
    )
    raw_password = fields.HiddenField([validators.DataRequired()])
    comment = fields.StringField(_('Comment'))
    ip = fields.StringField(
        _('Authorized IP'), [validators.Optional(), validators.IPAddress()]
    )
    submit = fields.SubmitField(_('Create'))


class AliasForm(flask_wtf.FlaskForm):
    localpart = fields.StringField(_('Alias'), [validators.DataRequired()])
    wildcard = fields.BooleanField(
        _('Use SQL LIKE Syntax (e.g. for catch-all aliases)'))
    destination = DestinationField(_('Destination'))
    comment = fields.StringField(_('Comment'))
    submit = fields.SubmitField(_('Create'))


class AdminForm(flask_wtf.FlaskForm):
    admin = fields.SelectField(_('Admin email'), choices=[])
    submit = fields.SubmitField(_('Submit'))


class ManagerForm(flask_wtf.FlaskForm):
    manager = fields.SelectField(_('Manager email'))
    submit = fields.SubmitField(_('Submit'))


class FetchForm(flask_wtf.FlaskForm):
    protocol = fields.SelectField(_('Protocol'), choices=[
        ('imap', 'IMAP'), ('pop3', 'POP3')
    ])
    host = fields.StringField(_('Hostname or IP'))
    port = fields.IntegerField(_('TCP port'))
    tls = fields.BooleanField(_('Enable TLS'))
    username = fields.StringField(_('Username'))
    password = fields.StringField(_('Password'))
    keep = fields.BooleanField(_('Keep emails on the server'))
    submit = fields.SubmitField(_('Submit'))


class AnnouncementForm(flask_wtf.FlaskForm):
    announcement_subject = fields.StringField(_('Announcement subject'),
        [validators.DataRequired()])
    announcement_body = fields.StringField(_('Announcement body'),
        [validators.DataRequired()], widget=widgets.TextArea())
    submit = fields.SubmitField(_('Send'))
