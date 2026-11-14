"""Run PHP hook behavior tests when PHP is available (also run in webmail)."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_snappymail_carddav_hooks():
    php = shutil.which('php84') or shutil.which('php')
    if php is None:
        pytest.skip('PHP is provided by the webmail image')
    subprocess.run([php, str(Path(__file__).with_name('webdav_webmail_test.php')), str(ROOT)], check=True)
