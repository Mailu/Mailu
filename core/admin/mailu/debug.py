#Note: Currently flask_debugtoolbar is not compatible with flask.
#import flask_debugtoolbar

from werkzeug.middleware.profiler import ProfilerMiddleware


# Debugging toolbar
#toolbar = flask_debugtoolbar.DebugToolbarExtension()


# Profiler
class Profiler(object):
    def init_app(self, app):
        app.wsgi_app = ProfilerMiddleware(
            app.wsgi_app, restrictions=[30]
        )

profiler = Profiler()
