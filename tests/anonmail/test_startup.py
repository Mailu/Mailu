from types import SimpleNamespace

import pytest

from mailu import configuration, create_app_from_config, models


def test_app_factory_does_not_query_domains_before_migrations(app, monkeypatch):
    monkeypatch.setattr(
        models, 'inspect',
        lambda engine: SimpleNamespace(has_table=lambda name: name == 'dkim_key'),
    )
    monkeypatch.setattr(
        models.Domain, 'query',
        SimpleNamespace(all=lambda: pytest.fail('App factory queried domains before migrations ran')),
    )

    create_app_from_config(configuration.ConfigManager())
