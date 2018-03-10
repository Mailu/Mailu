import flask
import flask_bootstrap
import redis
import os
import jinja2

app = flask.Flask(__name__)
flask_bootstrap.Bootstrap(app)
db = redis.StrictRedis(host='localhost', port=6379, db=0)

app.jinja_loader = jinja2.ChoiceLoader([
    app.jinja_loader,
    jinja2.FileSystemLoader("flavors"),
])


def render_flavor(flavor, template, **context):
    path = os.path.join(flavor, template)
    return flask.render_template(path, **context)


@app.route("/")
def index():
    return flask.render_template('index.html')


@app.route("/setup", methods=["POST"])
def setup():
    flavor = flask.request.form.get("flavor", "compose")
    rendered = render_flavor(flavor, "setup.html")
    return flask.render_template("setup.html", contents=rendered)


if __name__ == "__main__":
    app.run(debug=True)
