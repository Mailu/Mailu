import unittest
import io

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


class TestSystem(unittest.TestCase):
    """ Test the system functions
    """

    def test_resolve_hostname(self):
        self.assertEqual(
            system.resolve_hostname("1.2.3.4.xip.io"),
            "1.2.3.4"
        )

    def test_resolve_address(self):
        self.assertEqual(
            system.resolve_address("1.2.3.4.xip.io:80"),
            "1.2.3.4:80"
        )
