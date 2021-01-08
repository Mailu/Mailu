"""
Common functions for all API versions
"""

from .. import models

def fqdn_in_use(*names):
    """ Checks if fqdn is used
    """
    for name in names:
        for model in models.Domain, models.Alternative, models.Relay:
            if model.query.get(name):
                return model
    return None
