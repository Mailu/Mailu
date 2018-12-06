import os


DEFAULT_CONFIG = {
    # Specific to the admin UI
    'DOCKER_SOCKET': 'unix:///var/run/docker.sock',
    'BABEL_DEFAULT_LOCALE': 'en',
    'BABEL_DEFAULT_TIMEZONE': 'UTC',
    'BOOTSTRAP_SERVE_LOCAL': True,
    'RATELIMIT_STORAGE_URL': 'redis://redis/2',
    'QUOTA_STORAGE_URL': 'redis://redis/1',
    'DEBUG': False,
    'DOMAIN_REGISTRATION': False,
    'TEMPLATES_AUTO_RELOAD': True,
    # Database settings
    'DB_FLAVOR': 'sqlite',
    'DB_USER': 'mailu',
    'DB_PW': '',
    'DB_URL': 'database',
    'DB_NAME': 'mailu',
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////data/main.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    # Statistics management
    'INSTANCE_ID_PATH': '/data/instance',
    'STATS_ENDPOINT': '0.{}.stats.mailu.io',
    # Common configuration variables
    'SECRET_KEY': 'changeMe',
    'DOMAIN': 'mailu.io',
    'HOSTNAMES': 'mail.mailu.io,alternative.mailu.io,yetanother.mailu.io',
    'POSTMASTER': 'postmaster',
    'TLS_FLAVOR': 'cert',
    'AUTH_RATELIMIT': '10/minute;1000/hour',
    'DISABLE_STATISTICS': 'False',
    # Mail settings
    'DMARC_RUA': None,
    'DMARC_RUF': None,
    'WELCOME': 'False',
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
    'RECAPTCHA_PUBLIC_KEY': '',
    'RECAPTCHA_PRIVATE_KEY': '',
    # Advanced settings
    'PASSWORD_SCHEME': 'BLF-CRYPT',
    # Host settings
    'HOST_IMAP': 'imap',
    'HOST_POP3': 'imap',
    'HOST_SMTP': 'smtp',
    'HOST_WEBMAIL': 'webmail',
    'HOST_FRONT': 'front',
    'HOST_AUTHSMTP': os.environ.get('HOST_SMTP', 'smtp'),
    'POD_ADDRESS_RANGE': None
}


class ConfigManager(dict):
    """ Naive configuration manager that uses environment only
    """

    def __init__(self):
        self.config = dict()
        self.parse_env()

    def init_app(self, app):
        self.config.update(app.config)
        self.parse_env()
        if self.config['DB_FLAVOR'] != 'sqlite':
            self.setsql()
        app.config = self

    def parse_env(self):
        self.config.update({
            key: os.environ.get(key, value)
            for key, value in DEFAULT_CONFIG.items()
        })

    def setsql(self):
        if not self.config['DB_PW']:
            self.config['DB_PW'] = self.config['SECRET_KEY']
        self.config['SQLALCHEMY_DATABASE_URI'] = '{driver}://{user}:{pw}@{url}/{db}'.format(
            driver=self.config['DB_FLAVOR'],
            user=self.config['DB_USER'],
            pw=self.config['DB_PW'],
            url=self.config['DB_URL'],
            db=self.config['DB_NAME']
        )

    def setdefault(self, key, value):
        if key not in self.config:
            self.config[key] = value
        return self.config[key]

    def get(self, *args):
        return self.config.get(*args)

    def keys(self):
        return self.config.keys()

    def __getitem__(self, key):
        return self.config.get(key)

    def __setitem__(self, key, value):
        self.config[key] = value

    def __contains__(self, key):
        return key in self.config
