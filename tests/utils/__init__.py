"""Collection of test utilities."""

import errno
import os
import re
import signal
import sys
import time
from contextlib import contextmanager
from subprocess import PIPE
from subprocess import Popen

from py._path.local import LocalPath


# these signals cause entrypoint to suspend itself
SUSPEND_SIGNALS = frozenset([
    signal.SIGTSTP,
    signal.SIGTTOU,
    signal.SIGTTIN,
])

NORMAL_SIGNALS = frozenset(
    set(range(1, 32)) -
    {signal.SIGKILL, signal.SIGSTOP, signal.SIGCHLD, signal.SIGSYS} -
    SUSPEND_SIGNALS,
)


def popen_entrypoint(cmdline_args=(), **kwargs):
    """Helper function to launch the entrypoint script as a separate process."""
    if 'encoding' not in kwargs:
        kwargs['encoding'] = 'utf-8'
    if 'stdout' not in kwargs:
        kwargs['stdout'] = PIPE
    if 'stderr' not in kwargs:
        kwargs['stderr'] = PIPE
    cmd = (sys.executable, '-m', 'entrypoint.main') + tuple(cmdline_args)
    proc = Popen(cmd, **kwargs)
    return proc


@contextmanager
def print_signals(args=()):
    """Start print_signals and yield entrypoint process and print_signals PID."""
    proc = popen_entrypoint(
                            tuple(args) +
                            ('--', sys.executable, '-m', 'tests.utils.print_signals'))
    line = proc.stdout.readline().strip()
    print_signals_pid = int(line)

    yield proc, print_signals_pid

    for pid in pid_tree(proc.pid):
        os.kill(pid, signal.SIGKILL)


def child_pids(pid):
    """Return a list of direct child PIDs for the given PID."""
    children = set()
    for p in LocalPath('/proc').listdir():
        try:
            stat = open(p.join('stat').strpath).read()
            m = re.match(r'^\d+ \(.+?\) [a-zA-Z] (\d+) ', stat)
            assert m, stat
            ppid = int(m.group(1))
            if ppid == pid:
                children.add(int(p.basename))
        except OSError:
            # Happens when the process exits after listing it, or between
            # opening stat and reading it.
            pass
    return children


def pid_tree(pid):
    """Return a list of all descendant PIDs for the given PID."""
    children = child_pids(pid)
    return {
        pid
        for child in children
        for pid in pid_tree(child)
    } | children


def is_alive(pid):
    """Return whether a process is running with the given PID."""
    return LocalPath('/proc').join(str(pid)).isdir()


def living_pids(pids):
    """FIlter the PIDs that are alive."""
    return {pid for pid in pids if is_alive(pid)}


def process_state(pid):
    """Return a process' state, such as "stopped" or "running"."""
    status = LocalPath('/proc').join(str(pid), 'status').read()
    m = re.search(r'^State:\s+[A-Z] \(([a-z]+)\)$', status, re.MULTILINE)
    return m.group(1)


def sleep_until(fn, timeout=1.5):
    """Sleep until fn succeeds, or we time out."""
    interval = 0.01
    so_far = 0
    while True:
        try:
            fn()
        except Exception:
            if so_far >= timeout:
                raise
        else:
            break
        time.sleep(interval)
        so_far += interval


def kill_if_alive(pid, signum=signal.SIGKILL):
    """Kill a process, ignoring "no such process" errors."""
    try:
        os.kill(pid, signum)
    except OSError as ex:
        if ex.errno != errno.ESRCH:  # No such process
            raise
