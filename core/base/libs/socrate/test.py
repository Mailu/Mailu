import unittest
import io
import os
from unittest import mock

from socrate import conf, system


class TestConf(unittest.TestCase):
    """ Test configuration functions
    """

    MERGE_EXPECTATIONS = [
        ({"a": "1", "b": "2", "c": "3", "d": "4"},
         {"a": "1", "b": "2"},
         {"c": "3", "d": "4"}),

        ({"a": [1, 2, 3, 4, 5], "b": "4"},
         {"a": [1, 2, 3], "b": "4"},
         {"a": [4, 5]}),

        ({"a": {"x": "1", "y": "2", "z": 3}, "b": 4, "c": "5"},
         {"a": {"x": "1", "y": "2"}, "b": 4},
         {"a": {"z": 3}, "c": "5"})
    ]

    def test_jinja(self):
        template = "Test {{ variable }}"
        environ = {"variable": "ok"}
        self.assertEqual(
            conf.jinja(io.StringIO(template), environ),
            "Test ok"
        )
        result = io.StringIO()
        conf.jinja(io.StringIO(template), environ, result)
        self.assertEqual(
            result.getvalue(),
            "Test ok"
        )

    def test_merge(self):
        for result, *parts in TestConf.MERGE_EXPECTATIONS:
            self.assertEqual(result, conf.merge(*parts))

    def test_merge_failure(self):
        with self.assertRaises(ValueError):
            conf.merge({"a": 1}, {"a": 2})
        with self.assertRaises(ValueError):
            conf.merge(1, "a")

    def test_resolve(self):
        self.assertEqual(
            conf.resolve_function("unittest.TestCase"),
            unittest.TestCase
        )
        self.assertEqual(
            conf.resolve_function("unittest.util.strclass"),
            unittest.util.strclass
        )

    def test_resolve_failure(self):
        with self.assertRaises(AttributeError):
            conf.resolve_function("unittest.inexistant")
        with self.assertRaises(ModuleNotFoundError):
            conf.resolve_function("inexistant.function")


class TestEnvironment(unittest.TestCase):
    """Environment setup must distinguish startup from a live reload."""

    def setUp(self):
        for patcher in (
            mock.patch.dict(os.environ, {
                "SECRET_KEY": "test-secret",
                "TLS_FLAVOR": "cert",
                "ADMIN": "true",
            }, clear=True),
            mock.patch.object(system, "_is_compatible_with_hardened_malloc", return_value=False),
            mock.patch.object(system.signal, "signal"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(system.os, "system")
        self.run_command = patcher.start()
        self.addCleanup(patcher.stop)

    def test_startup_cleans_stale_pid_files(self):
        system.set_env()
        self.run_command.assert_called_once_with(
            r'find /run -xdev -type f -name \*.pid -print -delete'
        )

    def test_reload_preserves_pid_files_and_initializes_environment(self):
        env = system.set_env(["SECRET"], cleanup_pids=False)
        self.run_command.assert_not_called()
        self.assertIs(env["ADMIN"], True)
        self.assertIs(env["PORT_993"], True)
        self.assertNotEqual(env["SECRET_KEY"], "test-secret")
        self.assertEqual(len(env["SECRET_KEY"]), 64)

    def test_reload_does_not_disable_later_startup_cleanup(self):
        system.set_env(cleanup_pids=False)
        system.set_env()
        self.run_command.assert_called_once()


class TestSystem(unittest.TestCase):
    """ Test the system functions
    """

    def test_resolve_hostname(self):
        self.assertEqual(
            system.resolve_hostname("1.2.3.4.sslip.io"),
            "1.2.3.4"
        )
        self.assertEqual(
            system.resolve_hostname("2001-db8--f00.sslip.io"),
            "2001:db8::f00"
        )

if __name__ == "__main__":
    unittest.main()
