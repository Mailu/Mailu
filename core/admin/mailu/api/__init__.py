from flask import redirect, url_for

# import api version(s)
from . import v1

# api
ROOT='/api'
ACTIVE=v1

# patch url for swaggerui static assets
from flask_restx.apidoc import apidoc
apidoc.static_url_path = f'{ROOT}/swaggerui'

def register(app):

    # register api bluprint(s)
    app.register_blueprint(v1.blueprint, url_prefix=f'{ROOT}/v{int(v1.VERSION)}')

    # add redirect to current api version
    @app.route(f'{ROOT}/')
    def redir():
        return redirect(url_for(f'{ACTIVE.blueprint.name}.root'))

    # swagger ui config
    app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
    app.config.SWAGGER_UI_OPERATION_ID = True
    app.config.SWAGGER_UI_REQUEST_DURATION = True

    # TODO: remove patch of static assets for debugging
    import os
    if 'STATIC_ASSETS' in os.environ:
        app.blueprints['ui'].static_folder = os.environ['STATIC_ASSETS']

# TODO: authentication via username + password
# TODO: authentication via api token
# TODO: api access for all users (via token)
# TODO: use permissions from "manager_of"
# TODO: switch to marshmallow, as parser is deprecated. use flask_accepts?
