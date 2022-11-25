from flask import redirect, url_for
from flask_restx import apidoc
from . import v1 as APIv1


def register(app, web_api_root):

    APIv1.app = app
    # register api bluprint(s)
    apidoc.apidoc.url_prefix = f'{web_api_root}/v{int(APIv1.VERSION)}'
    APIv1.api_token = app.config['API_TOKEN']
    app.register_blueprint(APIv1.blueprint, url_prefix=f'{web_api_root}/v{int(APIv1.VERSION)}')

    # add redirect to current api version
    @app.route(f'{web_api_root}/')
    def redir():
        return redirect(url_for(f'{APIv1.blueprint.name}.root'))

    # swagger ui config
    app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
    app.config.SWAGGER_UI_OPERATION_ID = True
    app.config.SWAGGER_UI_REQUEST_DURATION = True
    app.config.RESTX_MASK_SWAGGER = False
