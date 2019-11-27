"""Test internals of the dumb_init module."""

import signal
from unittest.mock import patch
from pytest import raises
from entrypoint.dumb_init import *

def test_rewrites_invalid_names():
    """SignalRewrites raise an error if invalid signal names given."""
    rewrites = SignalRewrites()
    with raises(AttributeError):
        rewrites.set('SIGKILL', 'UNKNOWN')
    with raises(AttributeError):
        rewrites.set('UNKNOWN', 'SIGKILL')


def test_rewrites_as_default():
    """SignalRewrites should tanslate to the same signal by default."""
    rewrites = SignalRewrites()
    for sig in signal.Signals:
        assert rewrites.translate(sig.value) == sig.value


def test_rewrites_to_none():
    """Rewrie to signal NONE translates to 0, which can be interpreted as ignored."""
    rewrites = SignalRewrites()
    rewrites.set('SIGHUP', 'NONE')
    assert rewrites.translate('SIGHUP') == 0


def test_rewrite_signal():
    """Rewrite when a rewrite is set."""
    for from_sig in signal.Signals:
        for to_sig in signal.Signals:
            rewrites = SignalRewrites()
            rewrites.set(from_sig.value, to_sig.value)
            for sig in signal.Signals:
                if sig == from_sig:
                    assert rewrites.translate(sig.value) == to_sig.value
                else:
                    assert rewrites.translate(sig.value) == sig.value


def test_rewrite_signal_by_name():
    """Rewrite when a rewrite is set by its name."""
    for from_sig in signal.Signals:
        for to_sig in signal.Signals:
            rewrites = SignalRewrites()
            rewrites.set(from_sig.name[3:].lower(), to_sig.name)
            for sig in signal.Signals:
                if sig == from_sig:
                    assert rewrites.translate(sig.value) == to_sig.value
                else:
                    assert rewrites.translate(sig.value) == sig.value


def test_ignore_signal():
    """Temporarily ignore a signal."""
    ignores = SignalIgnores()
    assert not ignores.is_ignored(signal.SIGCONT)
    ignores.ignore_next(signal.SIGCONT)
    assert not ignores.is_ignored(signal.SIGTERM)
    assert ignores.is_ignored(signal.SIGCONT)
    assert not ignores.is_ignored(signal.SIGCONT)


@patch('os.kill')
def test_forward_signal(kill):
    """Signals are forwarded by calling kill."""
    forward_signal(signal.SIGTERM, child_pid=1, session_leader=False)
    kill.assert_called_once_with(1, signal.SIGTERM)
    forward_signal(signal.SIGTERM, child_pid=1, session_leader=True)
    kill.assert_called_with(-1, signal.SIGTERM)


@patch('os.kill')
def test_forward_ignored_signal(kill):
    """Signals ignored by rewriting to none should be ignored."""
    with patch('entrypoint.dumb_init._signal_rewrites', SignalRewrites()) as signal_rewrites:
        signal_rewrites.set(signal.SIGTERM, 'NONE')
        forward_signal(signal.SIGTERM, None, False)
        assert not kill.called


@patch('os.kill')
@patch('entrypoint.dumb_init.forward_signal')
def test_handle_signal(forward_signal, kill):
    """Forward other signals than SIGCHLD, which indicates for a child process to be waited."""
    for sig in signal.Signals:
        if sig == signal.SIGCHLD:
            continue # never forwarded
        forward_signal.reset_mock()
        kill.reset_mock()
        handle_signal(sig.value, None, True)
        assert forward_signal.called
        if sig.value in (signal.SIGTSTP, signal.SIGTTOU, signal.SIGTTIN):
            assert kill.called
        else:
            assert not kill.called


@patch('os.kill')
@patch('os.waitpid')
def test_handle_children(waitpid, kill):
    """Wait children when signaled so."""
    waitpid.side_effect = [(1, 0), (0, 0)]
    handle_signal(signal.SIGCHLD, 0, True)
    assert waitpid.call_count == 2
    assert not kill.called

    waitpid.side_effect = [(1, 0), (0, 0)]
    with raises(SystemExit):
        handle_signal(signal.SIGCHLD, child_pid=1, session_leader=False)
    kill.assert_called_once_with(1, signal.SIGTERM)
    waitpid.side_effect = [(1, 0), (0, 0)]
    with raises(SystemExit):
        handle_signal(signal.SIGCHLD, child_pid=1, session_leader=True)
    kill.assert_called_with(-1, signal.SIGTERM)


@patch('os.fork')
@patch('entrypoint.dumb_init.signal_handler_loop')
def test_init_parent_runs_signal_hander(signal_handler_loop, fork):
    """Init forks and runs signal handler loop in the parent process."""
    fork.return_value = 1 # child's pid
    init()
    assert signal_handler_loop.called


@patch('os.fork')
@patch('os.setsid')
def test_init_child_runs_execvp(setsid, fork):
    """Init forks and runs signal handler loop in the parent process."""
    fork.return_value = 0 # select the child branch after fork
    init(use_setsid=False)
    assert not setsid.called
    init(use_setsid=True)
    assert setsid.called
