import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core', 'admin'))
from mailu import create_app_from_config, models
from mailu import configuration


@pytest.fixture(scope='session')
def env_setup():
    # Common environment for tests
    os.environ.setdefault('REDIS_ADDRESS', 'localhost')
    os.environ.setdefault('MEMORY_SESSIONS', 'True')
    os.environ.setdefault('RATELIMIT_STORAGE_URL', 'memory://')
    os.environ.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///:memory:')
    os.environ.setdefault('API_TOKEN', 'not-empty')
    os.environ.setdefault('SECRET_KEY', 'test-secret')
    yield


@pytest.fixture
def app(env_setup):
    config = configuration.ConfigManager()
    app = create_app_from_config(config)
    app.config['TESTING'] = True
    # ensure small defaults suitable for test runs
    app.config.setdefault('ANONMAIL_LOCALPART_LENGTH', 6)
    with app.app_context():
        models.db.create_all()
        models.Base.metadata.create_all(bind=models.db.engine)
        yield app
        models.db.session.remove()
        models.db.drop_all()
        models.Base.metadata.drop_all(bind=models.db.engine)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def create_user_and_token(app):
    def _create(email='test1@example.com', token_str=None):
        user = models.User(localpart=email.split('@', 1)[0], domain_name=email.split('@',1)[1])
        user.set_password('password')
        models.db.session.add(user)
        models.db.session.commit()

        token = models.Token(user_email=user.email)
        token.set_password(token_str or ('a' * 32))
        models.db.session.add(token)
        models.db.session.commit()
        return user, token
    return _create


@pytest.fixture
def grant_domain_access(app):
    def _grant(domain_name, user=None):
        da = models.DomainAccess(domain_name=domain_name, user_email=(user.email if user else None))
        models.db.session.add(da)
        models.db.session.commit()
        return da
    return _grant
