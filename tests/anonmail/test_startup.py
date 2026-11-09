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


def test_quarantine_migration_cli_moves_existing_records(app, tmp_path, monkeypatch):
    import uuid
    from mailu import quarantine, quarantine_repository

    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    record_id = str(uuid.uuid4())
    (tmp_path / f'{record_id}.json').write_text('{}', encoding='utf-8')
    (tmp_path / f'{record_id}.eml').write_bytes(b'legacy')
    result = app.test_cli_runner().invoke(args=['mailu', 'migrate-quarantine-storage'])
    assert result.exit_code == 0, result.output
    assert quarantine_repository.get(tmp_path, record_id, 'quarantine', 90)[1].read_bytes() == b'legacy'
