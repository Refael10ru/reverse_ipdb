"""Dialing out from the target process to the listener.

Resolution order for host/port: explicit argument > environment variable >
built-in default. Connecting fails open: if nobody is listening (or the host
is unreachable within the timeout), ``connect`` returns ``None`` and the
caller treats the breakpoint as a no-op.
"""

import os
import socket
import threading

from .transport import SocketIO

DEFAULT_HOST = "host.docker.internal"
DEFAULT_PORT = 4444
CONNECT_TIMEOUT = 1.0

# Only one thread gets the interactive shell at a time; others pass through.
# The listener in Part 2 handles one session at a time, and a single socket
# cannot be shared across concurrently-paused threads without interleaving.
_shell_lock = threading.Lock()


def resolve_target(host=None, port=None):
    """Resolve the (host, port) to dial, applying env vars and defaults."""
    host = host or os.environ.get("DEBUG_HOST", DEFAULT_HOST)
    port = int(port or os.environ.get("DEBUG_PORT", DEFAULT_PORT))
    return host, port


def connect(host=None, port=None):
    """Dial the listener. Returns a SocketIO, or None.

    None is returned either because nobody is listening (fail-open: the
    breakpoint becomes a no-op) or because another thread already holds the
    interactive shell. When a session does start, the shell lock is held for
    its whole duration and released when the returned SocketIO is closed
    (on detach/EOF), so concurrent breakpoints pass straight through.
    """
    if not _shell_lock.acquire(blocking=False):
        return None  # another thread already has the shell

    released = False

    def _release():
        nonlocal released
        if not released:
            released = True
            _shell_lock.release()

    try:
        host, port = resolve_target(host, port)
        try:
            sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
        except OSError:
            _release()
            return None  # nobody listening -> keep running
        sock.settimeout(None)
        io = SocketIO(sock, on_close=_release)
        thread = threading.current_thread().name
        io.write(f"*** {socket.gethostname()} pid={os.getpid()} thread={thread}\n")
        io.flush()
        return io
    except BaseException:
        _release()
        raise
