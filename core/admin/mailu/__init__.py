""" Mailu admin app
"""

import flask
import flask_bootstrap

from mailu import utils, debug, models, manage, configuration

import hmac

def create_app_from_config(config):
    """ Create a new application based on the given configuration
    """
    app = flask.Flask(__name__, static_folder='static', static_url_path='/static')
    app.cli.add_command(manage.mailu)

    # Bootstrap is used for error display and flash messages
    app.bootstrap = flask_bootstrap.Bootstrap(app)

    # Initialize application extensions
    config.init_app(app)
    models.db.init_app(app)
    utils.session.init_app(app)
    utils.limiter.init_app(app)
    utils.babel.init_app(app)
    utils.login.init_app(app)
    utils.login.user_loader(models.User.get)
    utils.proxy.init_app(app)
    utils.migrate.init_app(app, models.db)

    app.device_cookie_key = hmac.new(bytearray(app.secret_key, 'utf-8'), bytearray('DEVICE_COOKIE_KEY', 'utf-8'), 'sha256').digest()
    app.temp_token_key = hmac.new(bytearray(app.secret_key, 'utf-8'), bytearray('WEBMAIL_TEMP_TOKEN_KEY', 'utf-8'), 'sha256').digest()
    app.srs_key = hmac.new(bytearray(app.secret_key, 'utf-8'), bytearray('SRS_KEY', 'utf-8'), 'sha256').digest()

    # Initialize list of translations
    app.config.translations = {
        str(locale): locale
        for locale in sorted(
            utils.babel.list_translations(),
            key=lambda l: l.get_language_name().title()
        )
    }

    # Initialize debugging tools
    if app.config.get("DEBUG"):
        debug.toolbar.init_app(app)
    if app.config.get("DEBUG_PROFILER"):
        debug.profiler.init_app(app)
    if assets := app.config.get('DEBUG_ASSETS'):
        app.static_folder = assets

    # Inject the default variables in the Jinja parser
    # TODO: move this to blueprints when needed
    @app.context_processor
    def inject_defaults():
        signup_domains = models.Domain.query.filter_by(signup_enabled=True).all()
        return dict(
            signup_domains= signup_domains,
            config        = app.config,
            get_locale    = utils.get_locale,
        )

    # Jinja filters
    @app.template_filter()
    def format_date(value):
        return utils.flask_babel.format_date(value) if value else ''

    @app.template_filter()
    def format_datetime(value):
        return utils.flask_babel.format_datetime(value) if value else ''

    # Import views
    from mailu import ui, internal, sso
    app.register_blueprint(ui.ui, url_prefix=app.config['WEB_ADMIN'])
    app.register_blueprint(internal.internal, url_prefix='/internal')
    app.register_blueprint(sso.sso, url_prefix='/sso')
    return app


def create_app():
    """ Create a new application based on the config module
    """
    config = configuration.ConfigManager()
    return create_app_from_config(config)

