from freeposte import dockercli
from freeposte.admin import app, db, models, forms, utils
from flask.ext import login as flask_login

import os
import pprint
import flask
import json


@app.route('/services', methods=['GET'])
@flask_login.login_required
def services():
    utils.require_global_admin()
    containers = {}
    for brief in dockercli.containers(all=True):
        if brief['Image'].startswith('freeposte/'):
            container = dockercli.inspect_container(brief['Id'])
            container['Image'] = dockercli.inspect_image(container['Image'])
            name = container['Config']['Labels']['com.docker.compose.service']
            containers[name] = container
            pprint.pprint(container)
    return flask.render_template('admin/services.html', containers=containers)


@app.route('/admins', methods=['GET'])
@flask_login.login_required
def admins():
    return flask.render_template('admin/admins.html')
