"""
Well-known URI handlers for avatar and vCard discovery
Implements RFC 5785 for service discovery
"""

import flask
from mailu import models
from mailu.ui import ui


@ui.route('/.well-known/avatar/<path:email>')
def wellknown_avatar(email):
    """Well-known URI for avatar discovery - redirects to API endpoint"""
    # Validate that user exists
    user = models.User.query.get(email)
    if not user:
        flask.abort(404)
    
    # Redirect to the actual avatar API endpoint
    avatar_url = flask.url_for('api.user_user_avatar', email=email, _external=True)
    return flask.redirect(avatar_url, code=302)


@ui.route('/.well-known/vcard/<path:email>')
def wellknown_vcard(email):
    """Well-known URI for vCard discovery - redirects to API endpoint"""
    # Validate that user exists
    user = models.User.query.get(email)
    if not user:
        flask.abort(404)
    
    # Redirect to the actual vCard API endpoint
    vcard_url = flask.url_for('api.user_user_v_card', email=email, _external=True)
    return flask.redirect(vcard_url, code=302)


@ui.route('/.well-known/user-services')
def wellknown_user_services():
    """Discovery endpoint for user services"""
    base_url = flask.request.url_root.rstrip('/')
    
    services = {
        "avatar": {
            "description": "User avatar service",
            "url_template": f"{base_url}/.well-known/avatar/{{email}}",
            "direct_url_template": f"{base_url}/api/v1/user/{{email}}/avatar",
            "format": "image/png or image/jpeg",
            "authentication": "none"
        },
        "vcard": {
            "description": "User vCard service with avatar",
            "url_template": f"{base_url}/.well-known/vcard/{{email}}",
            "direct_url_template": f"{base_url}/api/v1/user/{{email}}/vcard",
            "format": "text/vcard",
            "authentication": "none"
        }
    }
    
    return flask.jsonify(services)
