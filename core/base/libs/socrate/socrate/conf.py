import jinja2
import importlib


def jinja(source, environ, destination=None):
    """ Render a Jinja configuration file, supports file handle or path
    """
    close_source = close_destination = False
    if type(source) is str:
        source = open(source, "r")
        close_source = True
    if type(destination) is str:
        destination = open(destination, "w")
        close_destination = True
    result = jinja2.Template(source.read()).render(environ)
    if close_source:
        source.close()
    if destination is not None:
        destination.write(result)
        if close_destination:
            destination.close()
    return result


def merge(*objects):
    """ Merge simple python objects, which only consist of
    strings, integers, bools, lists and dicts
    """
    mode = type(objects[0])
    if not all(type(obj) is mode for obj in objects):
        raise ValueError("Cannot merge mixed typed objects")
    if len(objects) == 1:
        return objects[0]
    elif mode is dict:
        return {
            key: merge(*[obj[key] for obj in objects if key in obj])
            for obj in objects for key in obj.keys()
        }
    elif mode is list:
        return sum(objects, [])
    else:
        raise ValueError("Cannot merge objects of type {}: {}".format(
            mode, objects))


def resolve_function(function, cache={}):
    """ Resolve a fully qualified function name in Python, and caches
    the result
    """
    if function not in cache:
        module, name = function.rsplit(".", 1)
        cache[function] = getattr(importlib.import_module(module), name)
    return cache[function]


