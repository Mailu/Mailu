import os
from socrate.system import parse_bool

from datetime import timedelta
import ipaddress

DEFAULT_CONFIG = {
    # Specific to the admin UI
    'DOCKER_SOCKET': 'unix:///var/run/docker.sock',
    'BABEL_DEFAULT_LOCALE': 'en',
    'BABEL_DEFAULT_TIMEZONE': 'UTC',
    'BOOTSTRAP_SERVE_LOCAL': True,
    'RATELIMIT_STORAGE_URL': '',
    'DEBUG': False,
    'DEBUG_PROFILER': False,
    'DEBUG_TB_INTERCEPT_REDIRECTS': False,
    'DEBUG_ASSETS': '',
    'DOMAIN_REGISTRATION': False,
    'TEMPLATES_AUTO_RELOAD': True,
    'MEMORY_SESSIONS': False,
    'FETCHMAIL_ENABLED': True,
    'MAILU_VERSION': 'unknown',
    # Database settings
    'DB_FLAVOR': None,
    'DB_USER': 'mailu',
    'DB_PW': None,
    'DB_HOST': 'database',
    'DB_NAME': 'mailu',
    'DB_APPENDIX': '',
    'SQLITE_DATABASE_FILE': 'data/main.db',
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////data/main.db',
    'SQLALCHEMY_DATABASE_URI_ROUNDCUBE': 'sqlite:////data/roundcube.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    # Statistics management
    'INSTANCE_ID_PATH': '/data/instance',
    'STATS_ENDPOINT': '202406.{}.stats.mailu.io',
    # Common configuration variables
    'SECRET_KEY': 'changeMe',
    'QUARANTINE_KEY': '',
    'QUARANTINE_RETENTION_DAYS': 90,
    'QUARANTINE_MAX_MESSAGE_BYTES': 52428800,
    'DOMAIN': 'mailu.io',
    'HOSTNAMES': 'mail.mailu.io,alternative.mailu.io,yetanother.mailu.io',
    'POSTMASTER': 'postmaster',
    'WILDCARD_SENDERS': '',
    'TLS_FLAVOR': 'cert',
    'INBOUND_TLS_ENFORCE': False,
    'DEFER_ON_TLS_ERROR': True,
    'AUTH_RATELIMIT_IP': '5/hour',
    'AUTH_RATELIMIT_IP_V4_MASK': 24,
    'AUTH_RATELIMIT_IP_V6_MASK': 48,
    'AUTH_RATELIMIT_USER': '50/day',
    'AUTH_RATELIMIT_EXEMPTION': '',
    'AUTH_RATELIMIT_EXEMPTION_LENGTH': 86400,
    # Anonymous Email Service (anonmail) defaults
    'ANONMAIL_MAX_RETRIES': 10,
    'DISABLE_STATISTICS': False,
    # Mail settings
    'DMARC_RUA': None,
    'DMARC_RUF': None,
    'DMARC_SEND_REPORTS': False,
    'WELCOME': False,
    'WELCOME_SUBJECT': 'Dummy welcome topic',
    'WELCOME_BODY': 'Dummy welcome body',
    'DKIM_SELECTOR': 'dkim',
    'DKIM_PATH': '/dkim/{domain}.{selector}.key',
    'DEFAULT_QUOTA': 1000000000,
    'MESSAGE_RATELIMIT': '200/day',
    'MESSAGE_RATELIMIT_EXEMPTION': '',
    'RECIPIENT_DELIMITER': '',
    # Web settings
    'SITENAME': 'Mailu',
    'WEBSITE': 'https://mailu.io',
    'ADMIN': 'none',
    'WEBMAIL_AVAILABLE': 'roundcube,snappymail',
    'RECAPTCHA_PUBLIC_KEY': '',
    'RECAPTCHA_PRIVATE_KEY': '',
    'LOGO_URL': None,
    'LOGO_BACKGROUND': None,
    # Advanced settings
    'AUTH_REQUIRE_TOKENS': True,
    'API': False,
    'API_TOKEN': None,
    'FULL_TEXT_SEARCH': 'en',
    'FULL_TEXT_SEARCH_ATTACHMENTS': False,
    'LOG_LEVEL': 'INFO',
    'SESSION_KEY_BITS': 128,
    'SESSION_TIMEOUT': 3600,
    'PERMANENT_SESSION_LIFETIME': 30*24*3600,
    'SESSION_COOKIE_SECURE': None,
    'PASSKEY_RP_ID': '',
    'PASSKEY_REQUIRED': False,
    'ACCOUNT_SETUP_TOKEN_TTL': 7 * 24 * 3600,
    'OAUTH2_ACCESS_TOKEN_TTL': 24 * 3600,
    'OAUTH2_REFRESH_TOKEN_TTL': 90 * 24 * 3600,
    'OAUTH2_REFRESH_TOKEN_IDLE': 7 * 24 * 3600,
    'CREDENTIAL_ROUNDS': 13,
    'TLS_PERMISSIVE': True,
    'TZ': 'Etc/UTC',
    'DEFAULT_SPAM_THRESHOLD': 80,
    'PORTS': '25,80,443,465,993,995,4190',
    'PROXY_AUTH_WHITELIST': '',
    'PROXY_AUTH_HEADER': 'X-Auth-Email',
    'PROXY_AUTH_CREATE': False,
    'PROXY_AUTH_LOGOUT_URL': None,
    'SUBNET': '192.168.203.0/24',
    'SUBNET6': None,
    'WEBDAV': '',
}

class ConfigManager:
    """ Naive configuration manager that uses environment only
    """

    DB_TEMPLATES = {
        'sqlite': 'sqlite:////{SQLITE_DATABASE_FILE}',
        'postgresql': 'postgresql://{DB_USER}:{DB_PW}@{DB_HOST}/{DB_NAME}{DB_APPENDIX}',
        'mysql': 'mysql+mysqlconnector://{DB_USER}:{DB_PW}@{DB_HOST}/{DB_NAME}{DB_APPENDIX}',
    }

    def __init__(self):
        self.config = dict()

    def __get_env(self, key, value):
        key_file = key + "_FILE"
        if key_file in os.environ:
            with open(os.environ.get(key_file)) as file:
                value_from_file = file.read()
            return value_from_file.strip()
        else:
            return os.environ.get(key, value)

    def __coerce_value(self, value):
        return parse_bool(value, value)

    def init_app(self, app):
        # get current app config
        self.config.update(app.config)
        # get environment variables
        for key in os.environ:
            if key.endswith('_ADDRESS'):
                self.config[key] = os.environ[key]

        self.config.update({
            key: self.__coerce_value(self.__get_env(key, value))
            for key, value in DEFAULT_CONFIG.items()
        })
        self.config.update(WEB_ADMIN='/admin', WEB_WEBMAIL='/webmail', WEB_API='/api')
        self.config['ACCOUNT_SETUP_TOKEN_TTL'] = int(
            self.config['ACCOUNT_SETUP_TOKEN_TTL'],
        )
        self.config['OAUTH2_REFRESH_TOKEN_TTL'] = int(
            self.config['OAUTH2_REFRESH_TOKEN_TTL'],
        )
        self.config['OAUTH2_ACCESS_TOKEN_TTL'] = int(
            self.config['OAUTH2_ACCESS_TOKEN_TTL'],
        )
        self.config['OAUTH2_REFRESH_TOKEN_IDLE'] = int(
            self.config['OAUTH2_REFRESH_TOKEN_IDLE'],
        )
        if self.config['OAUTH2_REFRESH_TOKEN_TTL'] <= 0:
            raise ValueError('OAUTH2_REFRESH_TOKEN_TTL must be a positive number of seconds')
        if self.config['OAUTH2_ACCESS_TOKEN_TTL'] <= 0:
            raise ValueError('OAUTH2_ACCESS_TOKEN_TTL must be a positive number of seconds')
        if self.config['OAUTH2_REFRESH_TOKEN_IDLE'] <= 0:
            raise ValueError('OAUTH2_REFRESH_TOKEN_IDLE must be a positive number of seconds')
        self.config['QUARANTINE_RETENTION_DAYS'] = int(self.config['QUARANTINE_RETENTION_DAYS'])
        self.config['QUARANTINE_MAX_MESSAGE_BYTES'] = int(self.config['QUARANTINE_MAX_MESSAGE_BYTES'])

        # automatically set the sqlalchemy string
        if self.config['DB_FLAVOR']:
            template = self.DB_TEMPLATES[self.config['DB_FLAVOR']]
            self.config['SQLALCHEMY_DATABASE_URI'] = template.format(**self.config)

        if not self.config.get('RATELIMIT_STORAGE_URL'):
            self.config['RATELIMIT_STORAGE_URL'] = f'redis://{self.config["REDIS_ADDRESS"]}/2'

        self.config['SESSION_STORAGE_URL'] = f'redis://{self.config["REDIS_ADDRESS"]}/3'
        self.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
        self.config['SESSION_COOKIE_HTTPONLY'] = True
        if self.config['SESSION_COOKIE_SECURE'] is None:
            self.config['SESSION_COOKIE_SECURE'] = self.config['TLS_FLAVOR'] != 'notls'
        self.config['SESSION_PERMANENT'] = True
        self.config['SESSION_TIMEOUT'] = int(self.config['SESSION_TIMEOUT'])
        self.config['SESSION_KEY_BITS'] = int(self.config['SESSION_KEY_BITS'])
        self.config['PERMANENT_SESSION_LIFETIME'] = int(self.config['PERMANENT_SESSION_LIFETIME'])
        self.config['AUTH_RATELIMIT_IP_V4_MASK'] = int(self.config['AUTH_RATELIMIT_IP_V4_MASK'])
        self.config['AUTH_RATELIMIT_IP_V6_MASK'] = int(self.config['AUTH_RATELIMIT_IP_V6_MASK'])
        self.config['AUTH_RATELIMIT_EXEMPTION'] = set(ipaddress.ip_network(cidr, False) for cidr in (cidr.strip() for cidr in self.config['AUTH_RATELIMIT_EXEMPTION'].split(',')) if cidr)
        self.config['MESSAGE_RATELIMIT_EXEMPTION'] = set([s for s in self.config['MESSAGE_RATELIMIT_EXEMPTION'].lower().replace(' ', '').split(',') if s])
        hostnames = [host.strip() for host in self.config['HOSTNAMES'].split(',')]
        self.config['HOSTNAMES'] = ','.join(hostnames)
        self.config['HOSTNAME'] = hostnames[0]
        oauth2_scheme = 'http' if self.config['TLS_FLAVOR'] == 'notls' else 'https'
        self.config['OAUTH2_ISSUER'] = f"{oauth2_scheme}://{self.config['HOSTNAME']}"
        oauth2_prefix = f"{self.config['WEB_ADMIN'].rstrip('/')}/oauth2"
        self.config['OAUTH2_AUTH_URL'] = f"{self.config['OAUTH2_ISSUER']}{oauth2_prefix}/authorize"
        self.config['OAUTH2_TOKEN_URL'] = f"{self.config['OAUTH2_ISSUER']}{oauth2_prefix}/token"
        self.config['OAUTH2_CLIENT_ID'] = 'mailu'
        self.config['OAUTH2_SCOPE'] = 'imap smtp pop3 sieve offline_access'
        self.config['DEFAULT_SPAM_THRESHOLD'] = int(self.config['DEFAULT_SPAM_THRESHOLD'])
        self.config['ANONMAIL_MAX_RETRIES'] = int(self.config['ANONMAIL_MAX_RETRIES'])
        self.config['PROXY_AUTH_WHITELIST'] = set(ipaddress.ip_network(cidr, False) for cidr in (cidr.strip() for cidr in self.config['PROXY_AUTH_WHITELIST'].split(',')) if cidr)
        try:
            self.config['MAILU_VERSION'] = open('/version', 'r').read()
        except FileNotFoundError:
            pass

        # update the app config
        app.config.update(self.config)
