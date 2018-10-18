import flask_debugtoolbar

from werkzeug.contrib import profiler as werkzeug_profiler


# Debugging toolbar
toolbar = flask_debugtoolbar.DebugToolbarExtension()


# Profiler
class Profiler(object):
    def init_app(self):
        app.wsgi_app = werkzeug_profiler.ProfilerMiddleware(
            app.wsgi_app, restrictions=[30]
        )

profiler = Profiler()
