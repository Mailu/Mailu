import flask
import flask_bootstrap
import redis
import json
import os
import jinja2
import uuid
import string
import random
import ipaddress
import hashlib


version = os.getenv("this_version")
static_url_path = "/" + version + "/static"
app = flask.Flask(__name__, static_url_path=static_url_path)
flask_bootstrap.Bootstrap(app)
db = redis.StrictRedis(host='redis', port=6379, db=0)


def render_flavor(flavor, template, data):
    return flask.render_template(
        os.path.join(flavor, template),
        **data
    )


@app.add_template_global
def secret(length=16):
    charset = string.ascii_uppercase + string.digits
    return ''.join(
        random.SystemRandom().choice(charset)
        for _ in range(length)
    )


def build_app(path):

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    @app.context_processor
    def app_context():
        return dict(versions=os.getenv("VERSIONS","master").split(','))

    prefix_bp = flask.Blueprint(version, __name__)
    prefix_bp.jinja_loader = jinja2.ChoiceLoader([
        jinja2.FileSystemLoader(os.path.join(path, "templates")),
        jinja2.FileSystemLoader(os.path.join(path, "flavors"))
    ])

    root_bp = flask.Blueprint("root", __name__)
    root_bp.jinja_loader = jinja2.ChoiceLoader([
        jinja2.FileSystemLoader(os.path.join(path, "templates")),
        jinja2.FileSystemLoader(os.path.join(path, "flavors"))
    ])

    @prefix_bp.context_processor
    @root_bp.context_processor
    def bp_context(version=version):
        return dict(version=version)

    @prefix_bp.route("/")
    @root_bp.route("/")
    def wizard():
        return flask.render_template('wizard.html')

    @prefix_bp.route("/submit_flavor", methods=["POST"])
    @root_bp.route("/submit_flavor", methods=["POST"])
    def submit_flavor():
        data = flask.request.form.copy()
        steps = sorted(os.listdir(os.path.join(path, "templates", "steps", data["flavor"])))
        return flask.render_template('wizard.html', flavor=data["flavor"], steps=steps)

    @prefix_bp.route("/submit", methods=["POST"])
    @root_bp.route("/submit", methods=["POST"])
    def submit():
        data = flask.request.form.copy()
        data['uid'] = str(uuid.uuid4())
        data['dns'] = str(ipaddress.IPv4Network(data['subnet'])[-2])
        db.set(data['uid'], json.dumps(data))
        return flask.redirect(flask.url_for('.setup', uid=data['uid']))

    @prefix_bp.route("/setup/<uid>", methods=["GET"])
    @root_bp.route("/setup/<uid>", methods=["GET"])
    def setup(uid):
        data = json.loads(db.get(uid))
        flavor = data.get("flavor", "compose")
        rendered = render_flavor(flavor, "setup.html", data)
        return flask.render_template("setup.html", contents=rendered)

    @prefix_bp.route("/file/<uid>/<filepath>", methods=["GET"])
    @root_bp.route("/file/<uid>/<filepath>", methods=["GET"])
    def file(uid, filepath):
        data = json.loads(db.get(uid))
        flavor = data.get("flavor", "compose")
        return flask.Response(
            render_flavor(flavor, filepath, data),
            mimetype="application/text"
        )

    app.register_blueprint(prefix_bp, url_prefix="/{}".format(version))
    app.register_blueprint(root_bp)


if __name__ == "__main__":
    build_app("/tmp/mailutest")
    app.run(debug=True)
