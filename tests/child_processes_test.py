"""Test handling of child processes as a whole program"""

import os
import signal
import sys

import pytest

from .utils import popen_entrypoint, kill_if_alive, pid_tree, sleep_until, living_pids


def spawn_and_kill_pipeline(entrypoint_args=()):
    proc = popen_entrypoint(
        entrypoint_args
        + ("--", "sh", "-c", "yes 'oh, hi' | tail & yes error | tail >&2",)
    )

    def assert_living_pids():
        assert len(living_pids(pid_tree(os.getpid()))) == 6

    sleep_until(assert_living_pids)

    pids = pid_tree(os.getpid())
    proc.send_signal(signal.SIGTERM)
    proc.wait()
    return pids


def test_setsid_signals_entire_group():
    """When running in setsid mode, should signal the entire
    process group rooted at it.
    """
    pids = spawn_and_kill_pipeline()

    def assert_no_living_pids():
        assert len(living_pids(pids)) == 0

    sleep_until(assert_no_living_pids)


def test_no_setsid_doesnt_signal_entire_group():
    """When not running in setsid mode, should only signal its
    immediate child.
    """
    pids = spawn_and_kill_pipeline(("--no-setsid",))

    def assert_four_living_pids():
        assert len(living_pids(pids)) == 4

    sleep_until(assert_four_living_pids)

    for pid in living_pids(pids):
        kill_if_alive(pid)


def spawn_process_which_dies_with_children(entrypoint_args=()):
    """Spawn a process which spawns some children and then dies without
    signaling them.

    Returns a tuple (child pid, child stdout pipe), where the child is
    print_signals. This is useful because you can signal the PID and see if
    anything gets printed onto the stdout pipe.
    """
    proc = popen_entrypoint(
        entrypoint_args
        + (
            "--",
            "sh",
            "-c",
            # we need to sleep before the shell exits, or entrypoint might send
            # TERM to print_signals before it has had time to register custom
            # signal handlers
            "{} -m tests.utils.print_signals & sleep 1".format(sys.executable),
        )
    )
    proc.wait()
    assert proc.returncode == 0

    # read the first line (its PID) from print_signals
    line = proc.stdout.readline()
    child_pid = int(line.strip())

    # at this point, the shell and entrypoint have both exited, but
    # print_signals may or may not still be running (depending on whether
    # setsid mode is enabled)

    return child_pid, proc.stdout


def test_all_processes_receive_term_on_exit_if_setsid():
    """If the child exits for some reason, should send TERM to all
    processes in its session if setsid mode is enabled.
    """
    child_pid, child_stdout = spawn_process_which_dies_with_children()

    # print_signals should have received TERM
    assert child_stdout.readline().strip() == "SIGTERM"

    os.kill(child_pid, signal.SIGKILL)


def test_processes_dont_receive_term_on_exit_if_no_setsid():
    """If the child exits for some reason, should not send TERM to
    any other processes if setsid mode is disabled.
    """
    child_pid, child_stdout = spawn_process_which_dies_with_children(("--no-setsid",))

    # print_signals should not have received TERM; to test this, we send it
    # some other signals and ensure they were received (and TERM wasn't)
    for sig in {signal.Signals.SIGUSR1, signal.Signals.SIGINT}:
        os.kill(child_pid, sig.value)
        assert child_stdout.readline().strip() == sig.name

    os.kill(child_pid, signal.SIGKILL)


@pytest.mark.parametrize(
    "args", [("/doesnotexist",), ("--", "/doesnotexist"),],
)
def test_fails_nonzero_with_bad_exec(args):
    """If can't exec as requested, it should exit nonzero."""
    proc = popen_entrypoint(args)
    stdout, stderr = proc.communicate()
    assert proc.returncode != 0
    assert "No such file or directory" in stdout + stderr
