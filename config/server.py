import flask
import flask_bootstrap
import redis
import os
import jinja2

app = flask.Flask(__name__)
flask_bootstrap.Bootstrap(app)
db = redis.StrictRedis(host='localhost', port=6379, db=0)


def build_app(setup_path):

    for version in ("master", "1.8"):

        bp = flask.Blueprint(version, __name__)
        template_dir = os.path.join(setup_path, version, "templates")
        flavor_dir = os.path.join(setup_path, version, "flavors")
        bp.jinja_loader = jinja2.ChoiceLoader([
            jinja2.FileSystemLoader(template_dir),
            jinja2.FileSystemLoader(flavor_dir)
        ])

        @bp.route("/")
        def wizard():
            return flask.render_template('wizard.html')


        @bp.route("/setup", methods=["POST"])
        def setup():
            flavor = flask.request.form.get("flavor", "compose")
            rendered = render_flavor(flavor, "setup.html")
            return flask.render_template("setup.html", contents=rendered)

        app.register_blueprint(bp, url_prefix="/{}".format(version))



if __name__ == "__main__":
    build_app("/tmp/mailutest")
    app.run(debug=True)
