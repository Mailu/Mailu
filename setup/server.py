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


app = flask.Flask(__name__)
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

    version = os.getenv("this_version")

    bp = flask.Blueprint(version, __name__)
    bp.jinja_loader = jinja2.ChoiceLoader([
        jinja2.FileSystemLoader(os.path.join(path, "templates")),
        jinja2.FileSystemLoader(os.path.join(path, "flavors"))
    ])

    @bp.context_processor
    def bp_context(version=version):
        return dict(version=version)

    @bp.route("/")
    def wizard():
        return flask.render_template('wizard.html')

    @bp.route("/submit_flavor", methods=["POST"])
    def submit_flavor():
        data = flask.request.form.copy()
        steps = sorted(os.listdir(os.path.join(path, "templates", "steps", data["flavor"])))
        return flask.render_template('wizard.html', flavor=data["flavor"], steps=steps)

    @bp.route("/submit", methods=["POST"])
    def submit():
        data = flask.request.form.copy()
        data['uid'] = str(uuid.uuid4())
        data['dns'] = str(ipaddress.IPv4Network(data['subnet'])[-2])
        db.set(data['uid'], json.dumps(data))
        return flask.redirect(flask.url_for('.setup', uid=data['uid']))

    @bp.route("/setup/<uid>", methods=["GET"])
    def setup(uid):
        data = json.loads(db.get(uid))
        flavor = data.get("flavor", "compose")
        rendered = render_flavor(flavor, "setup.html", data)
        return flask.render_template("setup.html", contents=rendered)

    @bp.route("/file/<uid>/<filepath>", methods=["GET"])
    def file(uid, filepath):
        data = json.loads(db.get(uid))
        flavor = data.get("flavor", "compose")
        return flask.Response(
            render_flavor(flavor, filepath, data),
            mimetype="application/text"
        )

    app.register_blueprint(bp, url_prefix="/{}".format(version))


if __name__ == "__main__":
    build_app("/tmp/mailutest")
    app.run(debug=True)
