"""Tests for the main module."""

import sys
import logging
from subprocess import PIPE, Popen
from unittest.mock import patch
from pytest import mark, raises
import entrypoint
from entrypoint.main import main
from .utils import popen_entrypoint


def test_no_arguments_prints_usage():
    """Should print some usage help when no arguments given."""
    with popen_entrypoint() as proc:
        assert proc.wait() != 0
        assert not proc.stdout.read(), 'should not output to stdout'
        assert 'usage' in proc.stderr.read().lower()


@mark.parametrize('flag', ['-h', '--help'])
def test_print_help(flag):
    """Command-line help"""
    with popen_entrypoint((flag,)) as proc:
        assert proc.wait() == 0
        stdout, stderr = proc.communicate()
        assert 'usage' in stdout.lower()
        assert 'positional arguments' in stdout.lower()
        assert 'optional arguments' in stdout.lower()
        assert not stderr, 'should not output to stderr'


def test_print_version():
    """Version should be printed with argument --version."""
    with popen_entrypoint(('--version',)) as proc:
        assert proc.wait() == 0
        assert entrypoint.__version__ in proc.stdout.read()
        assert not proc.stderr.read(), 'should not output to stderr'


@mark.parametrize('flag', ['-v', '--verbose'])
@patch('entrypoint.dumb_init.init')
def test_verbose_mode(init, flag):
    """Verbose mode should set loglevel to debug."""
    init.side_effect = SystemExit(0)
    handler = logging.StreamHandler(sys.stdout)
    with patch.object(logging, 'StreamHandler', return_value=handler):
        with patch.object(handler, 'setLevel') as setLevel:
            with raises(SystemExit) as exc:
                main([flag, 'true'])
            assert exc.value.code == 0
            setLevel.assert_called_with(logging.DEBUG)


@mark.parametrize('flag', ['-q', '--quiet'])
@patch('entrypoint.dumb_init.init')
def test_quiet_mode(init, flag):
    """Quiet mode should set loglevel to error."""
    init.side_effect = SystemExit(0)
    handler = logging.StreamHandler(sys.stdout)
    with patch.object(logging, 'StreamHandler', return_value=handler):
        with patch.object(handler, 'setLevel') as setLevel:
            with raises(SystemExit) as exc:
                main([flag, 'true'])
            assert exc.value.code == 0
            setLevel.assert_called_with(logging.ERROR)


@patch('entrypoint.dumb_init.init')
def test_disable_init(init):
    """Parameter --no-init disables dumb_init functionality."""
    with patch('os.execvp'): # avoid exec call and termination of pytest
        with raises(SystemExit):
            main(['-v', '--no-init', 'true'])
        assert not init.called

        with raises(SystemExit):
            main(['-v', 'true'])
        assert init.called


@patch('os.execvp')
@patch('os.fork')
@patch('os.setsid')
def test_disable_setsid(setsid, fork, execvp):
    """Parameter --no-setsid disables use of setsid system call."""
    fork.return_value = 0 # mock fork to lead to the child branch
    execvp.side_effect = SystemExit(0)
    with raises(SystemExit) as exc:
        main(['--no-setsid', 'true'])
    assert exc.value.code == 0
    assert not setsid.called

    with raises(SystemExit) as exc:
        main(['true'])
    assert exc.value.code == 0
    assert setsid.called
