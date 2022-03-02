import os

from datetime import timedelta
from socrate import system
import ipaddress

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
    'MEMORY_SESSIONS': False,
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
    'STATS_ENDPOINT': '19.{}.stats.mailu.io',
    # Common configuration variables
    'SECRET_KEY': 'changeMe',
    'DOMAIN': 'mailu.io',
    'HOSTNAMES': 'mail.mailu.io,alternative.mailu.io,yetanother.mailu.io',
    'POSTMASTER': 'postmaster',
    'WILDCARD_SENDERS': '',
    'TLS_FLAVOR': 'cert',
    'INBOUND_TLS_ENFORCE': False,
    'DEFER_ON_TLS_ERROR': True,
    'AUTH_RATELIMIT_IP': '60/hour',
    'AUTH_RATELIMIT_IP_V4_MASK': 24,
    'AUTH_RATELIMIT_IP_V6_MASK': 56,
    'AUTH_RATELIMIT_USER': '100/day',
    'AUTH_RATELIMIT_EXEMPTION': '',
    'AUTH_RATELIMIT_EXEMPTION_LENGTH': 86400,
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
    'MESSAGE_RATELIMIT': '200/day',
    'MESSAGE_RATELIMIT_EXEMPTION': '',
    'RECIPIENT_DELIMITER': '',
    'REPLICATION': False,
    'REPLICATION_TARGET': '',
    # Web settings
    'SITENAME': 'Mailu',
    'WEBSITE': 'https://mailu.io',
    'ADMIN' : 'none',
    'WEB_ADMIN': '/admin',
    'WEB_WEBMAIL': '/webmail',
    'WEBMAIL': 'none',
    'RECAPTCHA_PUBLIC_KEY': '',
    'RECAPTCHA_PRIVATE_KEY': '',
    'LOGO_URL': None,
    'LOGO_BACKGROUND': None,
    # Advanced settings
    'LOG_LEVEL': 'WARNING',
    'SESSION_KEY_BITS': 128,
    'SESSION_TIMEOUT': 3600,
    'PERMANENT_SESSION_LIFETIME': 30*24*3600,
    'SESSION_COOKIE_SECURE': True,
    'CREDENTIAL_ROUNDS': 12,
    'TZ': 'Etc/UTC',
    # Host settings
    'HOST_IMAP': 'imap',
    'HOST_LMTP': 'imap:2525',
    'HOST_POP3': 'imap',
    'HOST_SMTP': 'smtp',
    'HOST_AUTHSMTP': 'smtp',
    'HOST_ADMIN': 'admin',
    'HOST_WEBMAIL': 'webmail',
    'HOST_WEBDAV': 'webdav:5232',
    'HOST_REDIS': 'redis',
    'HOST_FRONT': 'front',
    'HOST_DSYNC': None,
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
        if self.config['REPLICATION'] and self.config['REPLICATION_TARGET'].startswith('tcp:'):
            self.config['HOST_DSYNC'] = system.resolve_address(self.config['REPLICATION_TARGET'].split(":")[1])

    def __get_env(self, key, value):
        key_file = key + "_FILE"
        if key_file in os.environ:
            with open(os.environ.get(key_file)) as file:
                value_from_file = file.read()
            return value_from_file.strip()
        else:
            return os.environ.get(key, value)

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
            key: self.__coerce_value(self.__get_env(key, value))
            for key, value in DEFAULT_CONFIG.items()
        })
        self.resolve_hosts()

        # automatically set the sqlalchemy string
        if self.config['DB_FLAVOR']:
            template = self.DB_TEMPLATES[self.config['DB_FLAVOR']]
            self.config['SQLALCHEMY_DATABASE_URI'] = template.format(**self.config)

        self.config['RATELIMIT_STORAGE_URL'] = f'redis://{self.config["REDIS_ADDRESS"]}/2'
        self.config['QUOTA_STORAGE_URL'] = f'redis://{self.config["REDIS_ADDRESS"]}/1'
        self.config['SESSION_STORAGE_URL'] = f'redis://{self.config["REDIS_ADDRESS"]}/3'
        self.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
        self.config['SESSION_COOKIE_HTTPONLY'] = True
        self.config['SESSION_PERMANENT'] = True
        self.config['SESSION_TIMEOUT'] = int(self.config['SESSION_TIMEOUT'])
        self.config['PERMANENT_SESSION_LIFETIME'] = int(self.config['PERMANENT_SESSION_LIFETIME'])
        self.config['AUTH_RATELIMIT_IP_V4_MASK'] = int(self.config['AUTH_RATELIMIT_IP_V4_MASK'])
        self.config['AUTH_RATELIMIT_IP_V6_MASK'] = int(self.config['AUTH_RATELIMIT_IP_V6_MASK'])
        hostnames = [host.strip() for host in self.config['HOSTNAMES'].split(',')]
        self.config['AUTH_RATELIMIT_EXEMPTION'] = set(ipaddress.ip_network(cidr, False) for cidr in (cidr.strip() for cidr in self.config['AUTH_RATELIMIT_EXEMPTION'].split(',')) if cidr)
        self.config['MESSAGE_RATELIMIT_EXEMPTION'] = set([s for s in self.config['MESSAGE_RATELIMIT_EXEMPTION'].lower().replace(' ', '').split(',') if s])
        self.config['HOSTNAMES'] = ','.join(hostnames)
        self.config['HOSTNAME'] = hostnames[0]

        # update the app config
        app.config.update(self.config)

