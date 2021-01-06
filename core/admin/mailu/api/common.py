from .. import models

def fqdn_in_use(*names):
    for name in names:
        for model in models.Domain, models.Alternative, models.Relay:
            if model.query.get(name):
                return model
    return None
