import os
import signal

import pytest

from .utils import print_signals, process_state, sleep_until, SUSPEND_SIGNALS


def test_shell_background_support_setsid():
    """In setsid mode, should suspend itself and its children when it
    receives SIGTSTP, SIGTTOU, or SIGTTIN.
    """
    with print_signals() as (proc, pid):
        for signum in SUSPEND_SIGNALS:
            # both entrypoint and print_signals should be running or sleeping
            assert process_state(pid) in ['running', 'sleeping']
            assert process_state(proc.pid) in ['running', 'sleeping']

            # both should now suspend
            proc.send_signal(signum)

            def assert_both_stopped():
                assert process_state(proc.pid) == process_state(pid) == 'stopped'

            sleep_until(assert_both_stopped)

            # and then both wake up again
            proc.send_signal(signal.SIGCONT)
            assert proc.stdout.readline().strip() == 'SIGCONT'
            assert process_state(pid) in ['running', 'sleeping']
            assert process_state(proc.pid) in ['running', 'sleeping']


def test_shell_background_support_without_setsid():
    """In non-setsid mode, should forward the signals SIGTSTP,
    SIGTTOU, and SIGTTIN, and then suspend itself.
    """
    with print_signals(('--no-setsid',)) as (proc, _):
        for sig in signal.Signals:
            if sig.value in SUSPEND_SIGNALS:
                print('Signal', sig.name)
                assert process_state(proc.pid) in ['running', 'sleeping']
                proc.send_signal(sig.value)
                assert proc.stdout.readline().strip() == sig.name
                os.waitpid(proc.pid, os.WUNTRACED)
                assert process_state(proc.pid) == 'stopped'

                proc.send_signal(signal.SIGCONT)
                assert proc.stdout.readline().strip() == 'SIGCONT'
                assert process_state(proc.pid) in ['running', 'sleeping']
