"""Test startup migration decisions without running the webmail entrypoint."""

import ast
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock


class RoundcubeUpgradeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.image = Path(self.directory.name) / 'image-version'
        self.marker = Path(self.directory.name) / '.roundcube-version'
        self.image.write_text('2024.06.1\n')
        self.process = Mock()
        self.process.CalledProcessError = subprocess.CalledProcessError
        self.process.STDOUT = subprocess.STDOUT
        self.already_initialized()
        source = Path(__file__).resolve().parents[1] / 'webmails/start.py'
        tree = ast.parse(source.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'initialize_database')
        namespace = dict(os=os, tempfile=tempfile,
                         subprocess=self.process, demote=lambda: None, print=Mock())
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        self.initialize = namespace['initialize_database']

    def already_initialized(self):
        self.process.check_output.side_effect = subprocess.CalledProcessError(
            1, 'initdb.sh', output=b'table already exists')

    def run_startup(self):
        self.initialize(str(self.image), str(self.marker))

    def test_first_upgrade_then_restart(self):
        self.run_startup()
        self.assertEqual(self.marker.read_text(), '2024.06.1\n')
        self.assertEqual(self.process.check_call.call_count, 2)
        self.run_startup()
        self.assertEqual(self.process.check_call.call_count, 2)
        self.assertEqual(self.process.check_output.call_count, 2)

    def test_new_version_upgrades(self):
        self.run_startup()
        self.image.write_text('2024.06.2\n')
        self.run_startup()
        self.assertEqual(self.process.check_call.call_count, 4)
        self.assertEqual(self.marker.read_text(), '2024.06.2\n')

    def test_newly_initialized_database_overrides_matching_marker(self):
        self.run_startup()
        self.process.check_output.side_effect = None
        self.process.check_output.return_value = b'Initialized database'
        self.run_startup()
        self.assertEqual(self.process.check_call.call_count, 4)

    def test_empty_marker_is_replaced_after_upgrade(self):
        self.marker.write_text('')
        self.run_startup()
        self.assertEqual(self.process.check_call.call_count, 2)
        self.assertEqual(self.marker.read_text(), '2024.06.1\n')

    def test_upgrade_and_cleanup_failures_preserve_marker_and_retry(self):
        for failed_step, exit_code in ((0, 4), (1, 5)):
            with self.subTest(failed_step=failed_step):
                self.process.check_call.side_effect = None
                self.image.write_text('2024.06.1\n')
                self.run_startup()
                previous = self.marker.read_text()
                self.image.write_text('2024.06.2\n')
                failure = subprocess.CalledProcessError(1, 'migration')
                self.process.check_call.side_effect = [failure] if failed_step == 0 else [None, failure]
                with self.assertRaises(SystemExit) as raised:
                    self.run_startup()
                self.assertEqual(raised.exception.code, exit_code)
                self.assertEqual(self.marker.read_text(), previous)
                self.process.check_call.side_effect = None
                self.run_startup()
                self.assertEqual(self.marker.read_text(), '2024.06.2\n')

    def test_initialization_failure_does_not_write_marker(self):
        self.process.check_output.side_effect = subprocess.CalledProcessError(
            1, 'initdb.sh', output=b'Cannot connect to database')
        with self.assertRaises(SystemExit) as raised:
            self.run_startup()
        self.assertEqual(raised.exception.code, 3)
        self.assertFalse(self.marker.exists())
        self.process.check_call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
