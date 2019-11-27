#!/usr/bin/env python
"""Helper program that first prints its PID as the first line and then each received
signal name per line.

Since all signals are printed and otherwise ignored, you'll need to send
SIGKILL (kill -9) to this process to actually end it.
"""

import os
import signal
import sys
from queue import Queue

CATCHABLE_SIGNALS = frozenset(
    set(range(1, 32)) - {signal.SIGKILL, signal.SIGSTOP, signal.SIGCHLD},
)


SIGNAL_NAMES = {sig.value:sig.name for sig in signal.Signals}


signal_queue = Queue()


def unbuffered_print(line):
    """Write line to stdout and flush."""
    sys.stdout.write('{}\n'.format(line))
    sys.stdout.flush()


def print_signal(signum, _):
    """Signal handler to queue the singals."""
    signal_queue.put(signum)


if __name__ == '__main__':
    # set signal handlers
    for signum in CATCHABLE_SIGNALS:
        signal.signal(signum, print_signal)

    unbuffered_print(str(os.getpid()))

    # loop forever just printing signals
    last_signal = None
    while True:
        signum = signal_queue.get()
        unbuffered_print(SIGNAL_NAMES[signum])

        if signum == signal.SIGINT and last_signal == signal.SIGINT:
            print('Received SIGINT twice, exiting.')
            exit(0)
        last_signal = signum
