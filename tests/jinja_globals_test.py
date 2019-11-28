"""Jinja globals additions."""

from unittest.mock import patch
from pytest import mark, raises

from entrypoint.templates import render_string


@mark.parametrize("variables", [{}, {"x": 0}, {"x": "x", "y": "y"}])
def test_context(variables):
    """Context shloud return the whole variable space."""
    out = render_string("{{ context().keys() }}", variables)
    assert out == repr(variables.keys())


def test_zip():
    """Builtin zip should be callable from Jinja."""
    out = render_string("{{ zip(x, y) }}", {"x": [0, 1], "y": [1, 2]})
    assert out == "[(0, 1), (1, 2)]"


def test_min():
    """Builtin min should be callable from Jinja."""
    out = render_string("{{ min(x, y) }}", {"x": 42, "y": 6 * 9})
    assert out == "42"


def test_max():
    """Builtin max should be callable from Jinja."""
    out = render_string("{{ max(x, y) }}", {"x": 42, "y": 0})
    assert out == "42"


def test_abs():
    """Builtin abs should be callable from Jinja."""
    out = render_string("{{ abs(x) }}", {"x": -42,})
    assert out == "42"


def test_round():
    """Builtin round should be callable from Jinja."""
    out = render_string("{{ round(x) }}", {"x": 3.14})
    assert out == "3"
    out = render_string("{{ round(x, 1) }}", {"x": 3.14})
    assert out == "3.1"


@patch("glob.glob")
def test_glob(glob):
    """Should call glob.glob()."""
    glob.return_value = ["a", "b", "c"]
    out = render_string("""{{ glob('pattern') }}""", {})
    glob.assert_called_once_with("pattern")
    assert out == repr(glob.return_value)


@patch("glob.iglob")
def test_iglob(iglob):
    """Should call glob.iglob()."""
    iglob.return_value = ["a", "b", "c"]
    out = render_string("""{{ iglob('path') }}""", {})
    iglob.assert_called_once_with("path")
    assert out == repr(iglob.return_value)


def test_fatal_error():
    """Should raise a RuntimeError with the specified message."""
    msg = "the end of the universe"
    with raises(RuntimeError, match=msg):
        render_string("{% do fatal_error(msg) %}", {"msg": msg})
