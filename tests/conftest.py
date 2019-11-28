"""Pytest configuration."""

import os
from unittest.mock import patch
from pytest import fixture


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "use_fork: mark test to run without mocking os.fork"
    )
    config.addinivalue_line(
        "markers", "use_execvp: mark test to run without mocking os.execvp"
    )


@fixture(autouse=True, scope="function")
def clean_environment():
    """Ensure all tests start with a clean environment.

    Even if tests properly clean up after themselves, we still need this in
    case the user runs tests with an already-polluted environment.
    """
    with patch.dict(os.environ, {}):
        yield


@fixture(autouse=True, scope="function")
def mock_signal_handers():
    """Ensure that no one sets any non-default signal handlers."""
    with patch("signal.signal"):
        with patch("signal.pthread_sigmask"):
            yield


@fixture(autouse=True, scope="function")
def mock_execvp(request):
    """Ensure that os.execvp is not mistakenly called by any tests.
    This mocking can be explicitly disable by decorating a test with
    @mark.use_execvp.
    """
    if "use_execvp" in request.keywords:
        yield  # skip mocking
    else:
        with patch("os.execvp") as execvp:
            yield execvp


@fixture(autouse=True, scope="function")
def mock_fork(request):
    """Ensure that os.fork is not mistakenly called by any tests.
    This mocking can be explicitly disable by decorating a test with
    @mark.use_fork.
    """
    if "use_fork" in request.keywords:
        yield  # skip mocking
    else:
        with patch("os.fork") as fork:
            yield fork


@fixture(autouse=True, scope="function")
def mock_setsid():
    """Ensure that os.setsid is not called by any tests."""
    with patch("os.setsid"):
        yield
