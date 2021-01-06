import os

from socrate import system

DEFAULT_CONFIG = {
    # Specific to the admin UI
    'DOCKER_SOCKET': 'unix:///var/run/docker.sock',
    'BABEL_DEFAULT_LOCALE': 'en',
    'BABEL_DEFAULT_TIMEZONE': 'UTC',
    'BOOTSTRAP_SERVE_LOCAL': True,
    'RATELIMIT_STORAGE_URL': '',
    'QUOTA_STORAGE_URL': '',
    'DEBUG': False,
    'DOMAIN_REGISTRATION': False,
    'TEMPLATES_AUTO_RELOAD': True,
    # Database settings
    'DB_FLAVOR': None,
    'DB_USER': 'mailu',
    'DB_PW': None,
    'DB_HOST': 'database',
    'DB_NAME': 'mailu',
    'SQLITE_DATABASE_FILE':'data/main.db',
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////data/main.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    # Statistics management
    'INSTANCE_ID_PATH': '/data/instance',
    'STATS_ENDPOINT': '18.{}.stats.mailu.io',
    # Common configuration variables
    'SECRET_KEY': 'changeMe',
    'DOMAIN': 'mailu.io',
    'HOSTNAMES': 'mail.mailu.io,alternative.mailu.io,yetanother.mailu.io',
    'POSTMASTER': 'postmaster',
    'TLS_FLAVOR': 'cert',
    'AUTH_RATELIMIT': '10/minute;1000/hour',
    'AUTH_RATELIMIT_SUBNET': True,
    'DISABLE_STATISTICS': False,
    # Mail settings
    'DMARC_RUA': None,
    'DMARC_RUF': None,
    'WELCOME': False,
    'WELCOME_SUBJECT': 'Dummy welcome topic',
    'WELCOME_BODY': 'Dummy welcome body',
    'DKIM_SELECTOR': 'dkim',
    'DKIM_PATH': '/dkim/{domain}.{selector}.key',
    'DEFAULT_QUOTA': 1000000000,
    # Web settings
    'SITENAME': 'Mailu',
    'WEBSITE': 'https://mailu.io',
    'WEB_ADMIN': '/admin',
    'WEB_WEBMAIL': '/webmail',
    'WEBMAIL': 'none',
    'RECAPTCHA_PUBLIC_KEY': '',
    'RECAPTCHA_PRIVATE_KEY': '',
    'API': False,
    # Advanced settings
    'PASSWORD_SCHEME': 'PBKDF2',
    'LOG_LEVEL': 'WARNING',
    # Host settings
    'HOST_IMAP': 'imap',
    'HOST_LMTP': 'imap:2525',
    'HOST_POP3': 'imap',
    'HOST_SMTP': 'smtp',
    'HOST_AUTHSMTP': 'smtp',
    'HOST_ADMIN': 'admin',
    'WEBMAIL': 'none',
    'HOST_WEBMAIL': 'webmail',
    'HOST_WEBDAV': 'webdav:5232',
    'HOST_REDIS': 'redis',
    'HOST_FRONT': 'front',
    'SUBNET': '192.168.203.0/24',
    'SUBNET6': None,
    'POD_ADDRESS_RANGE': None
}

class ConfigManager:
    """ Naive configuration manager that uses environment only
    """

    DB_TEMPLATES = {
        'sqlite': 'sqlite:////{SQLITE_DATABASE_FILE}',
        'postgresql': 'postgresql://{DB_USER}:{DB_PW}@{DB_HOST}/{DB_NAME}',
        'mysql': 'mysql://{DB_USER}:{DB_PW}@{DB_HOST}/{DB_NAME}'
    }

    def __init__(self):
        self.config = dict()

    def get_host_address(self, name):
        # if MYSERVICE_ADDRESS is defined, use this
        if f'{name}_ADDRESS' in os.environ:
            return os.environ.get(f'{name}_ADDRESS')
        # otherwise use the host name and resolve it
        return system.resolve_address(self.config[f'HOST_{name}'])

    def resolve_hosts(self):
        for key in ['IMAP', 'POP3', 'AUTHSMTP', 'SMTP', 'REDIS']:
            self.config[f'{key}_ADDRESS'] = self.get_host_address(key)
        if self.config['WEBMAIL'] != 'none':
            self.config['WEBMAIL_ADDRESS'] = self.get_host_address('WEBMAIL')

    def __coerce_value(self, value):
        if isinstance(value, str) and value.lower() in ('true','yes'):
            return True
        elif isinstance(value, str) and value.lower() in ('false', 'no'):
            return False
        return value

    def init_app(self, app):
        # get current app config
        self.config.update(app.config)
        # get environment variables
        self.config.update({
            key: self.__coerce_value(os.environ.get(key, value))
            for key, value in DEFAULT_CONFIG.items()
        })
        self.resolve_hosts()

        # automatically set the sqlalchemy string
        if self.config['DB_FLAVOR']:
            template = self.DB_TEMPLATES[self.config['DB_FLAVOR']]
            self.config['SQLALCHEMY_DATABASE_URI'] = template.format(**self.config)

        self.config['RATELIMIT_STORAGE_URL'] = f'redis://{self.config["REDIS_ADDRESS"]}/2'
        self.config['QUOTA_STORAGE_URL'] = f'redis://{self.config["REDIS_ADDRESS"]}/1'

        # update the app config
        app.config.update(self.config)
