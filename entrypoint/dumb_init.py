"""Very simple init process that handles children and signal propagation.
This module is heavily inspired by dumb-init (https://github.com/Yelp/dumb-init),
which is written in C.
"""

import os
import sys
import fcntl
import termios
import signal
import logging
import traceback

log = logging.getLogger(__name__)

# Signals we care about are numbered from 1 to 31, inclusive.
# (32 and above are real-time signals.)
# TODO: this is likely not portable outside of Linux, or on strange architectures
MAX_SIGNAL = 31

# Set of all signals we are interested
all_signals = {sig.value for sig in signal.Signals if sig < MAX_SIGNAL}

# Map signal numbers to names
signal_names = dict((sig.value, sig.name) for sig in signal.Signals)
signal_names[0] = 'NONE'


class SignalRewrites(dict):
    """User-specified signal rewrites."""
    def _signum(self, sig):
        """Returns integer signal number when given a string or int."""
        if isinstance(sig, str):
            sig = sig.upper()
            if sig == 'NONE':
                return 0
            if not sig.startswith('SIG'):
                sig = 'SIG' + sig
            try:
                return signal.Signals[sig].value
            except KeyError:
                raise AttributeError('{} is not a signal name'.format(sig))
        return sig
    def translate(self, sig):
        """Apply signal rewrite if specified and returns the corresponding signum."""
        signum = self._signum(sig)
        if signum in self:
            log.debug('Translating signal %s to %s',
                      signal_names[signum], signal_names[self[signum]])
            return self[signum]
        return signum
    def set(self, from_sig, to_sig):
        """Set a signal rewrite specified by name or int."""
        self[self._signum(from_sig)] = self._signum(to_sig)
    def update(self, updates):
        """Update signal rewrites specified by name or int."""
        for k,v in updates.items() if isinstance(updates, dict) else updates:
            self.set(k, v)


class SignalIgnores(set):
    """One-time ignores due to TTY quirks."""
    def ignore_next(self, signum):
        """Ignore this signal the next time."""
        self.add(signum)
    def is_ignored(self, signum):
        """Test if the specified signal should be ignored this time. Resets the ingore status."""
        if signum in self:
            self.remove(signum)
            return True
        return False


_signal_rewrites = SignalRewrites()
_temporary_ignores = SignalIgnores()


def forward_signal(signum, child_pid, session_leader):
    """Forward signals taking user-specified rewrites into account."""
    signum = _signal_rewrites.translate(signum)
    if signum != 0:
        try:
            os.kill(-child_pid if session_leader else child_pid, signum)
            log.debug('Forwarded signal %s to children.', signal_names[signum])
        except ProcessLookupError as exc:
            log.debug('Forwarding signal %s interrupted: %s',
                      signal_names[signum], exc.strerror)
    else:
        log.debug("Not forwarding signal %s to children (ignored).", signal_names[signum])


def handle_signal(signum, child_pid, session_leader):
    """The main job of this signal handler is to forward signals along to our child
    process(es). In setsid mode, this means signaling the entire process group
    rooted at our child. In non-setsid mode, this is just signaling the primary
    child.

    In most cases, simply proxying the received signal is sufficient. If we
    receive a job control signal, however, we should not only forward it, but
    also sleep dumb-init itself.

    This allows users to run foreground processes using dumb-init and to
    control them using normal shell job control features (e.g. Ctrl-Z to
    generate a SIGTSTP and suspend the process).
    """
    log.debug('Received signal %s.', signal_names[signum])

    if _temporary_ignores.is_ignored(signum):
        log.debug("Ignoring tty hand-off signal %s", signal_names[signum])
    elif signum == signal.SIGCHLD:
        while True:
            killed_pid, status = os.waitpid(-1, os.WNOHANG)
            if not killed_pid:
                break # no more signals waiting
            if os.WIFEXITED(status): # the process called exit
                exit_status = os.WEXITSTATUS(status)
                log.debug("A child with PID %d exited with exit status %d.",
                          killed_pid, exit_status)
            else: # terminated by a signal
                assert os.WIFSIGNALED(status)
                exit_status = 128 + os.WTERMSIG(status)
                log.debug('A child with PID %d was terminated by signal %d.',
                          killed_pid,
                          exit_status - 128)

            if killed_pid == child_pid:
                forward_signal(signal.SIGTERM, child_pid, session_leader)  # send SIGTERM to any remaining children
                log.debug("Child exited with status %d. Goodbye.", exit_status)
                sys.exit(exit_status)

    else:
        forward_signal(signum, child_pid, session_leader)
        if signum in (signal.SIGTSTP, signal.SIGTTOU, signal.SIGTTIN):
            log.debug("Suspending self due to TTY signal.")
            os.kill(os.getpid(), signal.SIGSTOP)


def signal_handler_loop(child_pid, session_leader):
    """Wait for signals and handle them."""
    try:
        while True:
            signum = signal.sigwait(all_signals)
            handle_signal(signum, child_pid, session_leader)
    except SystemExit as sys_exit:
        log.debug('Init process terminates (exit=%d)', sys_exit.code)
        sys.exit(sys_exit.code)
    except:
        log.error("Unexpected exception thrown in signal handling")
        traceback.print_exc()
        sys.exit(1) # make sure we never return but exit!


def init(rewrites={}, use_setsid=True):
    """Initialize signal handling, leave the parent process to take care of signal propagation and
    return as a forked child process.
    """

    if use_setsid:
        for signum in [signal.SIGTSTP, signal.SIGTTOU, signal.SIGTTIN]:
            _signal_rewrites.set(signum, signal.SIGSTOP)
    _signal_rewrites.update(rewrites)

    # Block all signals and store the original state
    originally_blocked = signal.pthread_sigmask(signal.SIG_BLOCK, all_signals)

    # A dummy signal handler used for signals we care about.
    # On the FreeBSD kernel, ignored signals cannot be waited on by `sigwait` (but
    # they can be on Linux). We must provide a dummy handler.
    # https:#lists.freebsd.org/pipermail/freebsd-ports/2009-October/057340.html
    for sig in all_signals - {signal.SIGKILL, signal.SIGSTOP}:
        signal.signal(sig, lambda sig, frame: None)

    # Detach dumb-init from controlling tty, so that the child's session can
    # attach to it instead.
    # We want the child to be able to be the session leader of the TTY so that
    # it can do normal job control.
    if use_setsid:
        isatty = sys.stdout.isatty()
        if isatty:
            try:
                fcntl.ioctl(sys.stdin.fileno(), termios.TIOCNOTTY)
                # When the session leader detaches from its controlling tty via
                # TIOCNOTTY, the kernel sends SIGHUP and SIGCONT to the process
                # group. We need to be careful not to forward these on to the
                # dumb-init child so that it doesn't receive a SIGHUP and
                # terminate itself.
                if os.getsid(0) == os.getpid():
                    log.debug('Detached from controlling tty, ignoring '
                              'the first SIGHUP and SIGCONT we receive.')
                    _temporary_ignores.ignore_next(signal.SIGHUP)
                    _temporary_ignores.ignore_next(signal.SIGCONT)
                else:
                    log.debug('Detached from controlling tty, '
                              'but was not session leader.')
            except Exception as exc:
                log.debug('Unable to detach from controlling tty: %s', str(exc))

    pid = os.fork()
    if pid < 0:
        raise RuntimeError("Unable to fork.")
    elif pid == 0: # child process
        # Reset signal blocking
        signal.pthread_sigmask(signal.SIG_SETMASK, originally_blocked)

        if use_setsid:
            try:
                os.setsid()
                log.debug('System call setsid opened a new session')
            except Exception as exc:
                log.error('Unable to setsid: %s. Exiting.', str(exc))
                sys.exit(1)

            try:
                if isatty: # sys.stdout was attached to terminal, reattach
                    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
            except Exception as exc:
                log.debug("Unable to attach to controlling tty: %s", str(exc))

        return # child initialization is ready

    else: # parent process
        log.debug('Child spawned with PID %d', pid)
        signal_handler_loop(child_pid=pid, session_leader=use_setsid)
