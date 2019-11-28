"""Test signal propagation"""

import os
import signal
from itertools import chain

import pytest

from .utils import NORMAL_SIGNALS, print_signals, process_state


def test_proxies_signals():
    """Ensure entrypoint proxies regular signals to its child."""
    with print_signals() as (proc, _):
        for sig in signal.Signals:
            if sig.value in NORMAL_SIGNALS:
                print("Sending", sig.name)
                proc.send_signal(sig.value)
                assert proc.stdout.readline().strip() == sig.name


def _rewrite_map_to_args(rewrite_map):
    return chain.from_iterable(
        ("-r", "{}:{}".format(src, dst)) for src, dst in rewrite_map.items()
    )


@pytest.mark.parametrize(
    "rewrite_map,signals",
    [
        (
            {},
            {
                signal.SIGTERM: "SIGTERM",
                signal.SIGQUIT: "SIGQUIT",
                signal.SIGCONT: "SIGCONT",
                signal.SIGINT: "SIGINT",
            },
        ),
        (
            {"SIGTERM": "SIGINT"},
            {
                signal.SIGTERM: "SIGINT",
                signal.SIGQUIT: "SIGQUIT",
                signal.SIGCONT: "SIGCONT",
                signal.SIGINT: "SIGINT",
            },
        ),
        (
            {"SIGTERM": "SIGINT", "SIGINT": "SIGTERM", "SIGQUIT": "SIGQUIT"},
            {
                signal.SIGTERM: "SIGINT",
                signal.SIGQUIT: "SIGQUIT",
                signal.SIGCONT: "SIGCONT",
                signal.SIGINT: "SIGTERM",
            },
        ),
    ],
)
def test_proxies_signals_with_rewrite(rewrite_map, signals):
    """Ensure entrypoint can rewrite signals."""
    with print_signals(_rewrite_map_to_args(rewrite_map)) as (proc, _):
        for send, expect in signals.items():
            proc.send_signal(send)
            assert proc.stdout.readline().strip() == expect


def test_default_rewrites_can_be_overriden_with_setsid_enabled():
    """In setsid mode, should allow overwriting the default
    rewrites (but still suspend itself).
    """
    rewrite_map = {"SIGTTIN": "SIGTERM", "SIGTTOU": "SIGINT", "SIGTSTP": "SIGHUP"}
    with print_signals(_rewrite_map_to_args(rewrite_map)) as (proc, _):
        for send, expect_receive in rewrite_map.items():
            assert process_state(proc.pid) in ["running", "sleeping"]
            proc.send_signal(signal.Signals[send].value)

            assert proc.stdout.readline().strip() == expect_receive
            os.waitpid(proc.pid, os.WUNTRACED)
            assert process_state(proc.pid) == "stopped"

            proc.send_signal(signal.SIGCONT)
            assert proc.stdout.readline().strip() == "SIGCONT"
            assert process_state(proc.pid) in ["running", "sleeping"]


def test_ignored_signals_are_not_proxied():
    """Ensure entrypoint can ignore signals."""
    rewrite_map = {
        "SIGTERM": "SIGQUIT",
        "SIGINT": "NONE",
        "SIGWINCH": "NONE",
    }
    with print_signals(_rewrite_map_to_args(rewrite_map)) as (proc, _):
        proc.send_signal(signal.SIGTERM)
        proc.send_signal(signal.SIGINT)
        assert proc.stdout.readline().strip() == "SIGQUIT"

        proc.send_signal(signal.SIGWINCH)
        proc.send_signal(signal.SIGHUP)
        assert proc.stdout.readline().strip() == "SIGHUP"
