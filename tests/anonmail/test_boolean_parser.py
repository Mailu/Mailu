import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), (True, True), (" on ", True), ("0", False), ("OFF", False)],
)
def test_shared_boolean_parser(value, expected):
    from socrate.system import parse_bool

    assert parse_bool(value, False) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), (" OFF ", False), ("yes", True), ("legacy", "legacy"), ("", "")],
)
def test_environment_boolean_coercion_uses_shared_parser(value, expected):
    from socrate.system import _coerce_value
    from mailu.configuration import ConfigManager

    assert _coerce_value(value) == expected
    assert ConfigManager()._ConfigManager__coerce_value(value) == expected
