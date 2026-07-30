import flask
import pytest

from mailu import configuration, models


def _configured_app(monkeypatch, database_uri, engine_options=None):
    monkeypatch.setenv('DB_FLAVOR', '')
    monkeypatch.setenv('SQLALCHEMY_DATABASE_URI', database_uri)
    app = flask.Flask(__name__)
    if engine_options is not None:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
    configuration.ConfigManager().init_app(app)
    return app


@pytest.mark.parametrize(
    'database_uri',
    [
        'mysql+mysqlconnector://mailu:secret@database/mailu',
        'mariadb+mariadbconnector://mailu:secret@database/mailu',
    ],
)
def test_mysql_engine_uses_read_committed_and_preserves_options(
    env_setup,
    monkeypatch,
    database_uri,
):
    app = _configured_app(
        monkeypatch,
        database_uri,
        {
            'isolation_level': 'SERIALIZABLE',
            'pool_pre_ping': True,
        },
    )

    assert app.config['SQLALCHEMY_ENGINE_OPTIONS'] == {
        'isolation_level': 'READ COMMITTED',
        'pool_pre_ping': True,
    }


@pytest.mark.parametrize(
    'database_uri',
    [
        'sqlite:////data/main.db',
        'postgresql://mailu:secret@database/mailu',
    ],
)
def test_other_database_engines_keep_existing_options(
    env_setup,
    monkeypatch,
    database_uri,
):
    app = _configured_app(
        monkeypatch,
        database_uri,
        {'pool_pre_ping': True},
    )

    assert app.config['SQLALCHEMY_ENGINE_OPTIONS'] == {
        'pool_pre_ping': True,
    }


def test_generated_mysql_database_uri_uses_read_committed(
    env_setup,
    monkeypatch,
):
    monkeypatch.setenv('DB_FLAVOR', 'mysql')
    monkeypatch.setenv('DB_PW', 'secret')
    app = flask.Flask(__name__)

    configuration.ConfigManager().init_app(app)

    assert app.config['SQLALCHEMY_DATABASE_URI'].startswith(
        'mysql+mysqlconnector://',
    )
    assert app.config['SQLALCHEMY_ENGINE_OPTIONS'] == {
        'isolation_level': 'READ COMMITTED',
    }


class _BinlogCursor:
    def __init__(self, settings):
        self.settings = settings
        self.statement = None
        self.closed = False

    def execute(self, statement):
        self.statement = statement

    def fetchone(self):
        return self.settings

    def close(self):
        self.closed = True


class _BinlogConnection:
    def __init__(self, settings):
        self.cursor_instance = _BinlogCursor(settings)

    def cursor(self):
        return self.cursor_instance


@pytest.mark.parametrize(
    ('settings', 'blocked'),
    [
        ((0, 1, 'STATEMENT'), False),
        ((1, 0, 'STATEMENT'), False),
        ((1, 1, 'ROW'), False),
        ((1, 1, 'MIXED'), False),
        ((1, 1, 'STATEMENT'), True),
    ],
)
def test_mysql_binlog_preflight_rejects_only_active_statement_logging(
    settings,
    blocked,
):
    connection = _BinlogConnection(settings)

    if blocked:
        with pytest.raises(RuntimeError, match='binlog_format=STATEMENT'):
            models._reject_mysql_statement_binlog(connection, None)
    else:
        models._reject_mysql_statement_binlog(connection, None)

    assert connection.cursor_instance.statement == (
        'SELECT @@GLOBAL.log_bin, @@SESSION.sql_log_bin, '
        '@@SESSION.binlog_format'
    )
    assert connection.cursor_instance.closed is True
