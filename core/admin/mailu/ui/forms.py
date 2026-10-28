from wtforms import validators, fields, widgets
from wtforms.validators import ValidationError
from wtforms_components import fields as fields_
from flask_babel import lazy_gettext as _
from .. import utils
import flask_wtf
import re
import string
import ipaddress

# Characters a localpart may contain (RFC 5322 dot-atom), kept in a single place
# so that the fields creating an address and the ones referencing one agree.
LOCALPART_CHARS = r'a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-'
LOCALPART_REGEX = rf'^[{LOCALPART_CHARS}]+(?:\.[{LOCALPART_CHARS}]+)*$'
EMAIL_ADDRESS_REGEX = rf'[{LOCALPART_CHARS}]+(?:\.[{LOCALPART_CHARS}]+)*@(?:[a-z0-9-]+\.)*[a-z]+'

def checkStrippable(form, field):
    if field.data != field.data.strip(string.whitespace):
        raise ValidationError(_('Passwords should not start or end with whitespaces'))


def validLocalpart(form, field):
    if not utils.is_valid_localpart(field.data):
        raise ValidationError(_('Invalid email address.'))

AUTOFOCUS = {'autofocus': True}
NO_AUTOCOMPLETE = {'autocomplete': 'off', 'autocorrect': 'off', 'autocapitalize': 'off', 'spellcheck': 'false'}
MAX_QUOTA_BYTES = 1000 * 10**9

class DestinationField(fields.SelectMultipleField):
    """Allow managed or external addresses, searched dynamically in the UI."""

    validator = re.compile(r'^.+@([^.@][^@]+)$', re.IGNORECASE)

    def iter_choices(self):
        for email in self.data or ():
            yield (email, email, True, {})

    def pre_validate(self, form):
        for item in self.data:
            if not utils.is_valid_email(item):
                raise validators.ValidationError(_('Invalid email address.'))

class MultipleEmailAddressesVerify(object):
    def __init__(self,message=_('Invalid email address.')):
        self.message = message

    def __call__(self, form, field):
        addresses = field.data.replace(" ", "").split(',')
        if not all(utils.is_valid_email(address) for address in addresses):
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


class DkimToggleForm(flask_wtf.FlaskForm):
    pass


class DomainForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Domain name'), [validators.DataRequired()], render_kw=NO_AUTOCOMPLETE)
    max_users = fields_.IntegerField(_('Maximum user count'), [validators.NumberRange(min=-1)], default=10)
    max_aliases = fields_.IntegerField(_('Maximum alias count'), [validators.NumberRange(min=-1)], default=10)
    max_quota_bytes = fields_.IntegerSliderField(_('Maximum user quota'), [validators.NumberRange(min=0, max=MAX_QUOTA_BYTES)], default=0)
    signup_enabled = fields.BooleanField(_('Enable sign-up'), default=False)
    anonmail_enabled = fields.BooleanField(_('Enable Global Anonymous Email Service'), default=False)
    passkey_require_enrollment = fields.BooleanField(_('Require all users to enroll a passkey'), default=False)
    passkey_enforce_aaguid = fields.BooleanField(_('Enforce AAGUID restrictions'), default=False)
    passkey_aaguid_mode = fields.RadioField(_('AAGUID list behavior'), choices=[
        ('allow', _('Allow only listed AAGUIDs')),
        ('block', _('Block listed AAGUIDs')),
    ], default='allow', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    passkey_aaguids = fields.TextAreaField(_('AAGUIDs (one UUID per line)'), [validators.Optional()])
    passkey_require_uv = fields.BooleanField(_('Require user verification (PIN or biometrics)'), default=True)
    passkey_backup_eligible_policy = fields.RadioField(_('Backup eligibility policy'), choices=[
        ('optional', _('Optional')),
        ('require', _('Require backup-eligible passkeys')),
        ('deny', _('Deny backup-eligible passkeys')),
    ], default='optional', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    passkey_backup_state_policy = fields.RadioField(_('Backup state policy'), choices=[
        ('optional', _('Optional')),
        ('require', _('Require passkeys to be currently backed up')),
        ('deny', _('Deny currently backed-up passkeys')),
    ], default='optional', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    passkey_require_sign_count_increase = fields.BooleanField(_('Require signature counter to increase at every login'), default=False)
    passkey_attestation_policy = fields.RadioField(_('Authenticator attestation policy'), choices=[
        ('optional', _('Optional')),
        ('require', _('Require an attestation statement')),
        ('deny', _('Deny an attestation statement')),
    ], default='optional', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    passkey_device_bound = fields.BooleanField(_('Only allow device-bound passkeys'), default=False)
    passkey_resident_key = fields.RadioField(
        _('Resident passkey preference'), choices=[
            ('discouraged', _('Discouraged')),
            ('preferred', _('Preferred')),
            ('required', _('Required')),
        ], default='preferred', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput(),
    )
    comment = fields.StringField(_('Comment'), render_kw=AUTOFOCUS)
    submit = fields.SubmitField(_('Save'))

    def validate_passkey_aaguids(form, field):
        _validate_aaguids(field)

    def populate_domain(self, domain):
        """Save the domain form fields, excluding the CSRF token and submit control."""
        for name, field in self._fields.items():
            if name not in ('csrf_token', 'submit'):
                setattr(domain, name, field.data)


class DomainPasskeyPolicyForm(flask_wtf.FlaskForm):
    """Passkey policy fields domain managers may edit for their own domain."""
    passkey_require_enrollment = fields.BooleanField(_('Require all users to enroll a passkey'), default=False)
    passkey_enforce_aaguid = fields.BooleanField(_('Enforce AAGUID restrictions'), default=False)
    passkey_aaguid_mode = fields.RadioField(_('AAGUID list behavior'), choices=[
        ('allow', _('Allow only listed AAGUIDs')),
        ('block', _('Block listed AAGUIDs')),
    ], default='allow', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    passkey_aaguids = fields.TextAreaField(_('AAGUIDs (one UUID per line)'), [validators.Optional()])
    passkey_require_uv = fields.BooleanField(_('Require user verification (PIN or biometrics)'), default=True)
    passkey_backup_eligible_policy = fields.RadioField(_('Backup eligibility policy'), choices=[
        ('optional', _('Optional')),
        ('require', _('Require backup-eligible passkeys')),
        ('deny', _('Deny backup-eligible passkeys')),
    ], default='optional', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    passkey_backup_state_policy = fields.RadioField(_('Backup state policy'), choices=[
        ('optional', _('Optional')),
        ('require', _('Require passkeys to be currently backed up')),
        ('deny', _('Deny currently backed-up passkeys')),
    ], default='optional', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    passkey_require_sign_count_increase = fields.BooleanField(_('Require signature counter to increase at every login'), default=False)
    passkey_attestation_policy = fields.RadioField(_('Authenticator attestation policy'), choices=[
        ('optional', _('Optional')),
        ('require', _('Require an attestation statement')),
        ('deny', _('Deny an attestation statement')),
    ], default='optional', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    passkey_device_bound = fields.BooleanField(_('Only allow device-bound passkeys'), default=False)
    passkey_resident_key = fields.RadioField(_('Resident passkey preference'), choices=[
        ('discouraged', _('Discouraged')),
        ('preferred', _('Preferred')),
        ('required', _('Required')),
    ], default='preferred', widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.RadioInput())
    submit = fields.SubmitField(_('Save'))

    def validate_passkey_aaguids(form, field):
        _validate_aaguids(field)

    def populate_domain(self, domain):
        for name, field in self._fields.items():
            if name not in ('csrf_token', 'submit'):
                setattr(domain, name, field.data)


def _validate_aaguids(field):
    try:
        from .. import passkeys
        passkeys.normalize_aaguids(field.data)
    except ValueError:
        raise ValidationError(_('Enter valid AAGUID UUIDs, one per line.'))


class DomainSignupForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Domain name'), [validators.DataRequired()], render_kw=AUTOFOCUS|NO_AUTOCOMPLETE)
    localpart = fields.StringField(_('Initial admin'), [validators.DataRequired(), validLocalpart], render_kw=NO_AUTOCOMPLETE)
    pw = fields.PasswordField(_('Admin password'), [validators.DataRequired(), checkStrippable])
    pw2 = fields.PasswordField(_('Confirm password'), [validators.EqualTo('pw')])
    pwned = fields.HiddenField(label='', default=-1)
    captcha = flask_wtf.RecaptchaField()
    submit = fields.SubmitField(_('Create'))


class AlternativeForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Alternative name'), [validators.DataRequired()], render_kw=AUTOFOCUS|NO_AUTOCOMPLETE)
    submit = fields.SubmitField(_('Save'))


class RelayForm(flask_wtf.FlaskForm):
    name = fields.StringField(_('Relayed domain name'), [validators.DataRequired()], render_kw=AUTOFOCUS|NO_AUTOCOMPLETE)
    smtp = fields.StringField(_('Remote host'), render_kw=NO_AUTOCOMPLETE)
    comment = fields.StringField(_('Comment'), render_kw=AUTOFOCUS)
    submit = fields.SubmitField(_('Save'))


class UserForm(flask_wtf.FlaskForm):
    localpart = fields.StringField(_('E-mail'), [validators.DataRequired(), validLocalpart], render_kw=NO_AUTOCOMPLETE)
    quota_bytes = fields_.IntegerSliderField(_('Quota'), [validators.NumberRange(min=0, max=MAX_QUOTA_BYTES)], default=10**9)
    enable_imap = fields.BooleanField(_('Allow IMAP access'), default=True)
    enable_pop = fields.BooleanField(_('Allow POP3 access'), default=True)
    allow_spoofing = fields.BooleanField(_('Allow the user to spoof the sender (send email as anyone)'), default=False)
    displayed_name = fields.StringField(_('Displayed name'), render_kw=AUTOFOCUS)
    comment = fields.StringField(_('Comment'))
    enabled = fields.BooleanField(_('Enabled'), default=True)
    change_pw_next_login = fields.BooleanField(_('Force password change at next login'), default=True)
    passkey_enroll_next_login = fields.BooleanField(_('Require passkey'), default=False)
    submit = fields.SubmitField(_('Save'))


class UserSignupForm(flask_wtf.FlaskForm):
    localpart = fields.StringField(_('Email address'), [validators.DataRequired(), validLocalpart], render_kw=AUTOFOCUS|NO_AUTOCOMPLETE)
    pw = fields.PasswordField(_('Password'), [validators.DataRequired(), checkStrippable])
    pw2 = fields.PasswordField(_('Confirm password'), [validators.EqualTo('pw')])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Sign up'))

class UserSignupFormCaptcha(UserSignupForm):
    captcha = flask_wtf.RecaptchaField()

class UserSettingsForm(flask_wtf.FlaskForm):
    displayed_name = fields.StringField(_('Displayed name'), render_kw=AUTOFOCUS)
    gpg_key = fields.TextAreaField(_('OpenPGP public key'), [validators.Optional(), validators.Length(max=65536)])
    submit_gpg_key = fields.SubmitField(_('Publish OpenPGP key'))
    spam_enabled = fields.BooleanField(_('Enable spam filter'))
    spam_mark_as_read = fields.BooleanField(_('Enable marking spam mails as read'))
    spam_threshold = fields_.IntegerSliderField(_('Spam filter tolerance'))
    forward_enabled = fields.BooleanField(_('Enable forwarding'))
    forward_keep = fields.BooleanField(_('Keep a copy of the emails'))
    forward_destination = fields.StringField(_('Destination'), [validators.Optional(), MultipleEmailAddressesVerify()], render_kw=NO_AUTOCOMPLETE)
    submit = fields.SubmitField(_('Save settings'))


class UserPasswordForm(flask_wtf.FlaskForm):
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()], render_kw=AUTOFOCUS)
    pw2 = fields.PasswordField(_('Password check'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Update password'))

class UserPasswordChangeForm(flask_wtf.FlaskForm):
    current_pw = fields.PasswordField(_('Current password'), [validators.DataRequired()], render_kw=AUTOFOCUS)
    pw = fields.PasswordField(_('Password'), [validators.DataRequired(), checkStrippable])
    pw2 = fields.PasswordField(_('Password check'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Update password'))

class UserReplyForm(flask_wtf.FlaskForm):
    reply_enabled = fields.BooleanField(_('Enable automatic reply'))
    reply_subject = fields.StringField(_('Reply subject'), [validators.Optional(), validators.Length(max=255), validators.Regexp(r'^[^\r\n]+\Z')])
    reply_body = fields.TextAreaField(_('Message'), [validators.Length(max=100000)])
    reply_body_html = fields.HiddenField(default='', validators=[validators.Optional(), validators.Length(max=100000)])
    reply_schedule = fields.RadioField(_('When to reply'), choices=[('dates', _('On selected dates')), ('always', _('Until I turn it off'))], default='dates')
    reply_startdate = fields.DateField(_('First day away'), [validators.Optional()])
    reply_enddate = fields.DateField(_('Last day away'), [validators.Optional()])
    submit = fields.SubmitField(_('Save automatic reply'))

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators)
        if not self.reply_enabled.data:
            # Switching off must work even with an unfinished draft; keep CSRF errors.
            for field in (self.reply_subject, self.reply_body, self.reply_body_html, self.reply_schedule, self.reply_startdate, self.reply_enddate):
                field.errors = []
            return not self.errors
        if self.reply_schedule.data == 'dates':
            start, end = self.reply_startdate.data, self.reply_enddate.data
            if (self.reply_enabled.data or start or end) and not (start and end):
                for field in (self.reply_startdate, self.reply_enddate):
                    if not field.data:
                        field.errors = [_("Choose both the first and last day away.")]
                valid = False
            elif start and end and end < start:
                self.reply_enddate.errors = [_("The last day away must be on or after the first day.")]
                valid = False
        return valid


class TokenForm(flask_wtf.FlaskForm):
    displayed_password = fields.StringField(
        _('Authentication token (shown once)')
    )
    raw_password = fields.HiddenField([validators.DataRequired()])
    comment = fields.StringField(_('Comment'), render_kw=AUTOFOCUS)
    ip = fields.StringField(
        _('Authorized IP'), [validators.Optional()], render_kw=NO_AUTOCOMPLETE
    )
    submit = fields.SubmitField(_('Create and activate token'))

    def validate_ip(form, field):
        if not field.data:
            return True
        try:
            for candidate in field.data.replace(' ','').split(','):
                ipaddress.ip_network(candidate, False)
        except:
            raise validators.ValidationError('Not a valid list of CIDRs')

class AliasForm(flask_wtf.FlaskForm):
    localpart = fields.StringField(_('Alias'), [validators.DataRequired(), validLocalpart], render_kw=NO_AUTOCOMPLETE)
    wildcard = fields.BooleanField(
        _('Use SQL LIKE Syntax (e.g. for catch-all aliases)'))
    destination = DestinationField(_('Destination'))
    comment = fields.StringField(_('Comment'), render_kw=AUTOFOCUS)
    submit = fields.SubmitField(_('Save'))


class AdminForm(flask_wtf.FlaskForm):
    admin = fields.SelectMultipleField(_('Accounts'), [validators.DataRequired()], choices=[], validate_choice=False)
    submit = fields.SubmitField(_('Submit'))


class ManagerForm(flask_wtf.FlaskForm):
    manager = fields.SelectMultipleField(_('Accounts'), [validators.DataRequired()], choices=[], validate_choice=False)
    submit = fields.SubmitField(_('Submit'))


class DomainAccessForm(flask_wtf.FlaskForm):
    user = fields.SelectMultipleField(_('Accounts'), [validators.DataRequired()], choices=[], validate_choice=False)
    submit = fields.SubmitField(_('Grant access'))


class AnonymousAliasForm(flask_wtf.FlaskForm):
    domain = fields.SelectField(_('Domain'), [validators.DataRequired()])
    hostname = fields.StringField(_('Hostname (optional)'), [validators.Optional()])
    note = fields.StringField(_('Note (optional)'), [validators.Optional()])
    submit = fields.SubmitField(_('Generate alias'))


class FetchForm(flask_wtf.FlaskForm):
    protocol = fields.SelectField(_('Protocol'), choices=[
        ('imap', 'IMAP'), ('pop3', 'POP3')
    ])
    host = fields.StringField(_('Hostname or IP'), [validators.DataRequired()], render_kw=NO_AUTOCOMPLETE)
    port = fields.IntegerField(_('TCP port'), [validators.DataRequired(), validators.NumberRange(min=0, max=65535)], default=993)
    tls = fields.BooleanField(_('Enable TLS'), default=True)
    username = fields.StringField(_('Username'), [validators.DataRequired()], render_kw=NO_AUTOCOMPLETE)
    password = fields.PasswordField(_('Password'), render_kw=AUTOFOCUS)
    keep = fields.BooleanField(_('Keep emails on the server'))
    scan = fields.BooleanField(_('Rescan emails locally'))
    invisible = fields.BooleanField(_('Keep original metadata'))
    folders = fields.StringField(_('Folders to fetch on the server'), [validators.Optional(), MultipleFoldersVerify()], default='INBOX,Junk', render_kw=NO_AUTOCOMPLETE)
    submit = fields.SubmitField(_('Submit'))


class AnnouncementForm(flask_wtf.FlaskForm):
    announcement_subject = fields.StringField(_('Announcement subject'),
        [validators.DataRequired(), validators.Length(max=255), validators.Regexp(r'^[^\r\n]+\Z', message=_('Enter a subject on one line.'))], render_kw=AUTOFOCUS)
    announcement_body = fields.StringField(_('Announcement body'),
        [validators.DataRequired(), validators.Length(max=100000)], widget=widgets.TextArea())
    submit = fields.SubmitField(_('Send'))
