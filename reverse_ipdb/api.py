"""Public entry points.

Call these directly from the code you want to pause::

    import reverse_ipdb
    reverse_ipdb.set_trace()          # IPython over a pty -> tab/dot-completion
    reverse_ipdb.set_trace_ipython()  # explicit alias of set_trace()

Imports of IPython / prompt_toolkit are deferred until a listener is actually
reached, so a breakpoint with nobody listening stays a cheap no-op.
"""

import os
import sys

from .client import DOCKER_HOST


def set_trace(*, host=None, port=None, frame=None):
    """Pause here and hand an IPython shell (with completion) to the listener.

    IPython runs over a pseudo-terminal, so completion/history/colour work. No
    listener (or a shell already active elsewhere) -> no-op. A pty is required,
    so on a platform without ``os.openpty`` (e.g. Windows) this is a no-op too.
    """
    if not hasattr(os, "openpty"):
        return
    # Deferred: pty_bridge imports termios (POSIX-only), so a top-level import
    # would break `import reverse_ipdb` on Windows, and it keeps the no-listener
    # path from importing anything heavy.
    from . import pty_bridge  # noqa: PLC0415
    pty_bridge.run(frame or sys._getframe(1), host=host, port=port)


def docker_set_trace(*, host=None, port=None, frame=None):
    """``set_trace()`` preconfigured for containers.

    Identical to ``set_trace`` except the default host is the Docker
    host-gateway name ``host.docker.internal``, which routes to the host
    machine from inside a container. Resolution is still
    **arg → DEBUG_HOST env → host.docker.internal**.

    On Docker Desktop (macOS/Windows) the name resolves automatically; on Linux
    start the container with ``--add-host=host.docker.internal:host-gateway``
    (compose: ``extra_hosts``) so it maps to the host gateway.
    """
    host = host or os.environ.get("DEBUG_HOST") or DOCKER_HOST
    set_trace(host=host, port=port, frame=frame or sys._getframe(1))


# Explicit alias — IPython-over-pty is the only mode.
set_trace_ipython = set_trace
