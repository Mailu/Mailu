"""Apply webmail-specific configuration overrides."""
from configparser import ConfigParser
from pathlib import Path


def roundcube_overrides(directory='/roundcube-overrides', legacy='/overrides'):
    directory = Path(directory)
    # Keep manually configured deployments using the old mount working.
    if not directory.is_dir():
        directory = Path(legacy)
    includes = sorted(path.name for path in directory.iterdir()
                      if path.name.endswith(('.inc', '.inc.php'))) if directory.is_dir() else []
    return str(directory), includes


def apply_snappymail_overrides(config_file, override_file):
    """Merge a partial administrator-provided INI into the generated config."""
    override_file = Path(override_file)
    if not override_file.is_file():
        return
    config = ConfigParser(interpolation=None)
    config.optionxform = str
    with open(config_file, encoding='utf-8') as source:
        config.read_file(source)
    with override_file.open(encoding='utf-8') as source:
        config.read_file(source)
    with open(config_file, 'w', encoding='utf-8') as target:
        config.write(target)
