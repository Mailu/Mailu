import logging
import tenacity

from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig

from flask import current_app
from mailu import models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# add your model's MetaData object here
# for 'autogenerate' support
config.set_main_option(
    'sqlalchemy.url',
    current_app.config.get('SQLALCHEMY_DATABASE_URI')
)
target_metadata = models.Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(url=url)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.readthedocs.org/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    engine = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix    = 'sqlalchemy.',
        poolclass = pool.NullPool
    )

    @tenacity.retry(
        stop   = tenacity.stop_after_attempt(100),
        wait   = tenacity.wait_random(min=2, max=5),
        before = tenacity.before_log(logging.getLogger('tenacity.retry'), logging.DEBUG),
        before_sleep = tenacity.before_sleep_log(logging.getLogger('tenacity.retry'), logging.INFO),
        after  = tenacity.after_log(logging.getLogger('tenacity.retry'), logging.DEBUG)
    )
    def try_connect(db):
        return db.connect()

    with try_connect(engine) as connection:

        context.configure(
            connection      = connection,
            target_metadata = target_metadata,
            process_revision_directives = process_revision_directives,
            **current_app.extensions['migrate'].configure_args
        )

        with context.begin_transaction():
            context.run_migrations()

    connection.close()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
