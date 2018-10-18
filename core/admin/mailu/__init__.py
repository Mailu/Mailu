import flask
import flask_bootstrap

from mailu import utils, debug, models, configuration


def create_app_from_config(config):
    """ Create a new application based on the given configuration
    """
    app = flask.Flask(__name__)
    app.app_context().push()

    # Bootstrap is used for basic JS and CSS loading
    # TODO: remove this and use statically generated assets instead
    app.bootstrap = flask_bootstrap.Bootstrap(app)

    # Initialize application extensions
    config.init_app(app)
    models.db.init_app(app)
    utils.limiter.init_app(app)
    utils.babel.init_app(app)
    utils.login.init_app(app)
    utils.login.user_loader(models.User.query.get)
    utils.proxy.init_app(app)

    # Initialize debugging tools
    if app.config.get("DEBUG"):
        debug.toolbar.init_app(app)
        # TODO: add a specific configuration variable for profiling
        # debug.profiler.init_app(app)

    # Inject the default variables in the Jinja parser
    # TODO: move this to blueprints when needed
    @app.context_processor
    def inject_defaults():
        signup_domains = models.Domain.query.filter_by(signup_enabled=True).all()
        return dict(
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
