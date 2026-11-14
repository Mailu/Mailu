"""Webmail overrides are isolated and retain generated defaults."""
import importlib.util
from pathlib import Path


path = Path(__file__).resolve().parents[2] / 'webmails/overrides.py'
spec = importlib.util.spec_from_file_location('webmail_overrides', path)
overrides = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overrides)


def test_roundcube_uses_its_own_directory(tmp_path):
    roundcube = tmp_path / 'roundcube'
    snappymail = tmp_path / 'snappymail'
    roundcube.mkdir()
    snappymail.mkdir()
    (roundcube / 'custom.inc.php').write_text('<?php')
    (snappymail / 'not-roundcube.inc.php').write_text('<?php')
    directory, includes = overrides.roundcube_overrides(roundcube, tmp_path)
    assert directory == str(roundcube)
    assert includes == ['custom.inc.php']


def test_roundcube_legacy_mount_remains_usable(tmp_path):
    (tmp_path / 'custom.inc').write_text('<?php')
    assert overrides.roundcube_overrides(tmp_path / 'missing', tmp_path) == (str(tmp_path), ['custom.inc'])


def test_snappymail_override_preserves_generated_values(tmp_path):
    config = tmp_path / 'application.ini'
    config.write_text('[webmail]\nattachment_size_limit = 30\n[security]\nallow_admin_panel = Off\n')
    override = tmp_path / 'override.ini'
    override.write_text('[webmail]\nattachment_size_limit = 15\n[contacts]\nenable = On\n')
    overrides.apply_snappymail_overrides(config, override)
    result = config.read_text()
    assert 'attachment_size_limit = 15' in result
    assert 'allow_admin_panel = Off' in result
    assert '[contacts]\nenable = On' in result


def test_snappymail_missing_override_leaves_config_untouched(tmp_path):
    config = tmp_path / 'application.ini'
    contents = '; generated config\n[security]\nallow_admin_panel = Off\n'
    config.write_text(contents)
    overrides.apply_snappymail_overrides(config, tmp_path / 'missing.ini')
    assert config.read_text() == contents
