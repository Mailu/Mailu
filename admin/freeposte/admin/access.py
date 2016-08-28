from freeposte.admin import db, models, forms

import flask
import flask_login
import functools


def permissions_wrapper(handler):
    """ Decorator that produces a decorator for checking permissions.
    """
    def callback(function, args, kwargs, dargs, dkwargs):
        authorized = handler(args, kwargs, *dargs, **dkwargs)
        if not authorized:
            flask.abort(403)
        elif type(authorized) is int:
            flask.abort(authorized)
        else:
            return function(*args, **kwargs)
    # If the handler has no argument, declare a
    # simple decorator, otherwise declare a nested decorator
    # There are at least two mandatory arguments
    if handler.__code__.co_argcount > 2:
        def decorator(*dargs, **dkwargs):
            def inner(function):
                @functools.wraps(function)
                def wrapper(*args, **kwargs):
                    return callback(function, args, kwargs, dargs, dkwargs)
                return flask_login.login_required(wrapper)
            return inner
    else:
        def decorator(function):
            @functools.wraps(function)
            def wrapper(*args, **kwargs):
                return callback(function, args, kwargs, (), {})
            return flask_login.login_required(wrapper)
    return decorator


@permissions_wrapper
def global_admin(args, kwargs):
    return flask_login.current_user.global_admin


@permissions_wrapper
def domain_admin(args, kwargs, model, key):
    obj = model.query.get(kwargs[key])
    if not obj:
        flask.abort(404)
    else:
        domain = obj if type(obj) is models.Domain else obj.domain
        return domain in flask_login.current_user.get_managed_domains()


@permissions_wrapper
def owner(args, kwargs, model, key):
    obj = model.query.get(kwargs[key])
    if not obj:
        flask.abort(404)
    else:
        user = obj if type(obj) is models.User else obj.user
        return (
            user.email == flask_login.current_user.email
            or user.domain in flask_login.current_user.get_managed_domains()
        )


@permissions_wrapper
def authenticated(args, kwargs):
    return True



def confirmation_required(action):
    """ View decorator that asks for a confirmation first.
    """
    def inner(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            form = forms.ConfirmationForm()
            if form.validate_on_submit():
                return function(*args, **kwargs)
            return flask.render_template(
                "confirm.html", action=action.format(*args, **kwargs),
                form=form
            )
        return wrapper
    return inner
