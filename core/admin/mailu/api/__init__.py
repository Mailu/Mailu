from flask import redirect, url_for
from flask_restx import apidoc
from . import v1


def register(app, web_api):

    ACTIVE=v1
    ROOT=web_api
    v1.app = app
    # register api bluprint(s)
    apidoc.apidoc.url_prefix = f'{ROOT}/v{int(v1.VERSION)}'
    v1.api_token = app.config['API_TOKEN']
    app.register_blueprint(v1.blueprint, url_prefix=f'{ROOT}/v{int(v1.VERSION)}')



    # add redirect to current api version
    @app.route(f'{ROOT}/')
    def redir():
        return redirect(url_for(f'{ACTIVE.blueprint.name}.root'))

    # swagger ui config
    app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
    app.config.SWAGGER_UI_OPERATION_ID = True
    app.config.SWAGGER_UI_REQUEST_DURATION = True
    app.config.RESTX_MASK_SWAGGER = False
