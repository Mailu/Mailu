from freeposte import app, db, models, forms, utils
from flask.ext import login as flask_login

import os
import flask


@app.route('/status', methods=['GET'])
@flask_login.login_required
def status():
    utils.require_global_admin()
    return flask.render_template('admin/status.html')


@app.route('/admins', methods=['GET'])
@flask_login.login_required
def admins():
    return flask.render_template('admin/admins.html')
