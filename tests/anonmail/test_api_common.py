import warnings

import sqlalchemy

from mailu import models
from mailu.api import common


def test_fqdn_in_use_checks_all_fqdn_models_without_cartesian_product(app):
    with app.app_context():
        models.db.session.add(models.Domain(name='example.com'))
        models.db.session.add(models.Alternative(
            name='alternative.example', domain_name='example.com'))
        models.db.session.add(models.Relay(name='relay.example'))
        models.db.session.commit()

        with warnings.catch_warnings():
            warnings.simplefilter('error', sqlalchemy.exc.SAWarning)
            assert common.fqdn_in_use('example.com')
            assert common.fqdn_in_use('alternative.example')
            assert common.fqdn_in_use('relay.example')
            assert not common.fqdn_in_use('unused.example')
