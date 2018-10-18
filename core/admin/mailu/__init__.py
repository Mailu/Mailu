import flask
import flask_bootstrap

import os
import docker
import socket
import uuid

from mailu import utils, debug, db


def create_app_from_config(config):
    """ Create a new application based on the given configuration
    """
    app = flask.Flask(__name__)
    app.config = config

    # Bootstrap is used for basic JS and CSS loading
    # TODO: remove this and use statically generated assets instead
    app.bootstrap = flask_bootstrap.Bootstrap(app)

    # Initialize application extensions
    models.db.init_app(app)
    utils.limiter.init_app(app)
    utils.babel.init_app(app)
    utils.login.init_app(app)
    utils.proxy.init_app(app)
    manage.migrate.init_app(app)
    manage.manager.init_app(app)

    # Initialize debugging tools
    if app.config.get("app.debug"):
        debug.toolbar.init_app(app)
        debug.profiler.init_app(app)

    # Inject the default variables in the Jinja parser
    @app.context_processor
    def inject_defaults():
        signup_domains = models.Domain.query.filter_by(signup_enabled=True).all()
        return dict(
            current_user=utils.login.current_user,
            signup_domains=signup_domains,
            config=app.config
        )

    # Import views
    from mailu import ui, internal
    app.register_blueprint(ui.ui, url_prefix='/ui')
    app.register_blueprint(internal.internal, url_prefix='/internal')

    return app


def create_app():
    """ Create a new application based on the config module 
    """
    config = configuration.ConfigManager()
    return create_app_from_config(config)
