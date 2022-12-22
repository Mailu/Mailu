from wtforms import validators, fields, widgets
from wtforms_components import fields as fields_
from flask_babel import lazy_gettext as _

import flask_login
import flask_wtf
import re

LOCALPART_REGEX = "^[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*$"

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

class MultipleEmailAddressesVerify(object):
    def __init__(self,message=_('Invalid email address.')):
        self.message = message

    def __call__(self, form, field):
        pattern = re.compile(r'^([_a-z0-9\-]+)(\.[_a-z0-9\-]+)*@([a-z0-9\-]{1,}\.)*([a-z]{1,})(,([_a-z0-9\-]+)(\.[_a-z0-9\-]+)*@([a-z0-9\-]{1,}\.)*([a-z]{2,}))*$')
        if not pattern.match(field.data.replace(" ", "")):
            raise validators.ValidationError(self.message)

class MultipleFoldersVerify(object):
    """ Ensure that we have CSV formated data """
    def __init__(self,message=_('Invalid list of folders.')):
        self.message = message

    def __call__(self, form, field):
        pattern = re.compile(r'^[^,]+(,[^,]+)*$')
        if not pattern.match(field.data.replace(" ", "")):
            raise validators.ValidationError(self.message)

class ConfirmationForm(flask_wtf.FlaskForm):
    submit = fields.SubmitField(_('Confirm'))

class DomainForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Domain name'), [validators.DataRequired()])
    max_users = fields_.IntegerField(_('Maximum user count'), [validators.NumberRange(min=-1)], default=10)
    max_aliases = fields_.IntegerField(_('Maximum alias count'), [validators.NumberRange(min=-1)], default=10)
    max_quota_bytes = fields_.IntegerSliderField(_('Maximum user quota'), default=0)
    signup_enabled = fields.BooleanField(_('Enable sign-up'), default=False)
    comment = fields.StringField(_('Comment'))
    submit = fields.SubmitField(_('Save'))


class DomainSignupForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Domain name'), [validators.DataRequired()])
    localpart = fields.StringField(_('Initial admin'), [validators.DataRequired()])
    pw = fields.PasswordField(_('Admin password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('Confirm password'), [validators.EqualTo('pw')])
    pwned = fields.HiddenField(label='', default=-1)
    captcha = flask_wtf.RecaptchaField()
    submit = fields.SubmitField(_('Create'))


class AlternativeForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Alternative name'), [validators.DataRequired()])
    submit = fields.SubmitField(_('Save'))


class RelayForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Relayed domain name'), [validators.DataRequired()])
    smtp = fields.StringField(_('Remote host'))
    comment = fields.StringField(_('Comment'))
    submit = fields.SubmitField(_('Save'))


class UserForm(flask_wtf.FlaskForm):
    localpart = fields.StringField(_('E-mail'), [validators.DataRequired(), validators.Regexp(LOCALPART_REGEX)])
    pw = fields.PasswordField(_('Password'))
    pw2 = fields.PasswordField(_('Confirm password'), [validators.EqualTo('pw')])
    pwned = fields.HiddenField(label='', default=-1)
    quota_bytes = fields_.IntegerSliderField(_('Quota'), default=10**9)
    enable_imap = fields.BooleanField(_('Allow IMAP access'), default=True)
    enable_pop = fields.BooleanField(_('Allow POP3 access'), default=True)
    allow_spoofing = fields.BooleanField(_('Allow the user to spoof the sender (send email as anyone)'), default=False)
    displayed_name = fields.StringField(_('Displayed name'))
    comment = fields.StringField(_('Comment'))
    enabled = fields.BooleanField(_('Enabled'), default=True)
    submit = fields.SubmitField(_('Save'))


class UserSignupForm(flask_wtf.FlaskForm):
    localpart = fields.StringField(_('Email address'), [validators.DataRequired(), validators.Regexp(LOCALPART_REGEX)])
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('Confirm password'), [validators.EqualTo('pw')])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Sign up'))

class UserSignupFormCaptcha(UserSignupForm):
    captcha = flask_wtf.RecaptchaField()

class UserSettingsForm(flask_wtf.FlaskForm):
    displayed_name = fields.StringField(_('Displayed name'))
    spam_enabled = fields.BooleanField(_('Enable spam filter'))
    spam_mark_as_read = fields.BooleanField(_('Enable marking spam mails as read'))
    spam_threshold = fields_.IntegerSliderField(_('Spam filter tolerance'))
    forward_enabled = fields.BooleanField(_('Enable forwarding'))
    forward_keep = fields.BooleanField(_('Keep a copy of the emails'))
    forward_destination = fields.StringField(_('Destination'), [validators.Optional(), MultipleEmailAddressesVerify()])
    submit = fields.SubmitField(_('Save settings'))


class UserPasswordForm(flask_wtf.FlaskForm):
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('Password check'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Update password'))


class UserReplyForm(flask_wtf.FlaskForm):
    reply_enabled = fields.BooleanField(_('Enable automatic reply'))
    reply_subject = fields.StringField(_('Reply subject'))
    reply_body = fields.StringField(_('Reply body'),
        widget=widgets.TextArea())
    reply_startdate = fields.DateField(_('Start of vacation'))
    reply_enddate = fields.DateField(_('End of vacation'))
    submit = fields.SubmitField(_('Update'))


class TokenForm(flask_wtf.FlaskForm):
    displayed_password = fields.StringField(
        _('Your token (write it down, as it will never be displayed again)')
    )
    raw_password = fields.HiddenField([validators.DataRequired()])
    comment = fields.StringField(_('Comment'))
    ip = fields.StringField(
        _('Authorized IP'), [validators.Optional(), validators.IPAddress(ipv6=True)]
    )
    submit = fields.SubmitField(_('Save'))


class AliasForm(flask_wtf.FlaskForm):
    localpart = fields.StringField(_('Alias'), [validators.DataRequired(), validators.Regexp(LOCALPART_REGEX)])
    wildcard = fields.BooleanField(
        _('Use SQL LIKE Syntax (e.g. for catch-all aliases)'))
    destination = DestinationField(_('Destination'))
    comment = fields.StringField(_('Comment'))
    submit = fields.SubmitField(_('Save'))


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
    host = fields.StringField(_('Hostname or IP'), [validators.DataRequired()])
    port = fields.IntegerField(_('TCP port'), [validators.DataRequired(), validators.NumberRange(min=0, max=65535)], default=993)
    tls = fields.BooleanField(_('Enable TLS'), default=True)
    username = fields.StringField(_('Username'), [validators.DataRequired()])
    password = fields.PasswordField(_('Password'))
    keep = fields.BooleanField(_('Keep emails on the server'))
    scan = fields.BooleanField(_('Rescan emails locally'))
    folders = fields.StringField(_('Folders to fetch on the server'), [validators.Optional(), MultipleFoldersVerify()], default='INBOX,Junk')
    submit = fields.SubmitField(_('Submit'))


class AnnouncementForm(flask_wtf.FlaskForm):
    announcement_subject = fields.StringField(_('Announcement subject'),
        [validators.DataRequired()])
    announcement_body = fields.StringField(_('Announcement body'),
        [validators.DataRequired()], widget=widgets.TextArea())
    submit = fields.SubmitField(_('Send'))
