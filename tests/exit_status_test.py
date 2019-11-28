import signal
import sys
import pytest
from .utils import popen_entrypoint


@pytest.mark.parametrize("exit_status", [0, 1, 2, 32, 64, 127, 254, 255])
def test_exit_status_regular_exit(exit_status):
    """Should exit with the same exit status as the process that it
    supervises when that process exits normally.
    """
    proc = popen_entrypoint(("--", "sh", "-c", "exit {}".format(exit_status)))
    proc.wait()
    assert proc.returncode == exit_status


@pytest.mark.parametrize(
    "signal", [signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT, signal.SIGKILL,],
)
def test_exit_status_terminated_by_signal(signal):
    """Should exit with status 128 + signal when the child process is
    terminated by a signal.
    """
    proc = popen_entrypoint(
        (
            "--",
            sys.executable,
            "-c",
            "import os; os.kill(os.getpid(), {})".format(signal,),
        )
    )
    proc.wait()
    assert proc.returncode == 128 + signal
