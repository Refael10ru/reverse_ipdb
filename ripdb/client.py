"""Dialing out from the target process to the listener.

Resolution order for host/port: explicit argument > environment variable >
built-in default. Connecting fails open: if nobody is listening (or the host
is unreachable within the timeout), the caller gets ``None`` and treats the
breakpoint as a no-op.

``dial`` is the low-level primitive (acquire the shell lock, open the socket);
``connect`` wraps it in a ``SocketIO`` for the line-based pdb path. The pty
path in ``pty_bridge`` uses ``dial`` directly so it can own the raw socket.
"""

import os
import socket
import threading

from .transport import SocketIO

DEFAULT_HOST = "host.docker.internal"
DEFAULT_PORT = 4444
CONNECT_TIMEOUT = 1.0

# Only one thread gets the interactive shell at a time; others pass through.
# The lock is held for the whole session and released when the socket closes.
_shell_lock = threading.Lock()


def resolve_target(host=None, port=None):
    """Resolve the (host, port) to dial, applying env vars and defaults."""
    host = host or os.environ.get("DEBUG_HOST", DEFAULT_HOST)
    port = int(port or os.environ.get("DEBUG_PORT", DEFAULT_PORT))
    return host, port


def banner(mode):
    """The first line a target sends: machine-readable mode + human identity.

    ``mode`` is "pty" (IPython over a pseudo-terminal) or "line" (plain pdb);
    the listener reads it to decide raw pass-through vs. line bridging.
    """
    host = socket.gethostname()
    thread = threading.current_thread().name
    return f"*** ripdb/{mode} {host} pid={os.getpid()} thread={thread}\n"


def dial(host=None, port=None):
    """Acquire the shell lock and open a socket to the listener.

    Returns ``(sock, release)`` or ``None``. ``None`` means either nobody is
    listening (fail-open) or another thread already holds the shell. ``release``
    frees the lock and is idempotent; the caller must arrange to call it when
    the session ends (e.g. via SocketIO's on_close, or the pty bridge teardown).
    """
    if not _shell_lock.acquire(blocking=False):
        return None  # another thread already has the shell

    released = False

    def release():
        nonlocal released
        if not released:
            released = True
            _shell_lock.release()

    try:
        host, port = resolve_target(host, port)
        try:
            sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
        except OSError:
            release()
            return None  # nobody listening -> keep running
        sock.settimeout(None)
        return sock, release
    except BaseException:
        release()
        raise


def connect(host=None, port=None):
    """Dial and wrap the socket as a SocketIO for the line-based pdb path."""
    dialed = dial(host, port)
    if dialed is None:
        return None
    sock, release = dialed
    io = SocketIO(sock, on_close=release)
    io.write(banner("line"))
    io.flush()
    return io
