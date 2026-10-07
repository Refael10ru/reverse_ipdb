"""Public entry points.

Call these directly from the code you want to pause::

    import reverse_ipdb
    reverse_ipdb.set_trace()          # IPython over a pty -> tab/dot-completion
    reverse_ipdb.set_trace_ipython()  # explicit alias of set_trace()

POSIX only: the pty machinery (and so this package) imports ``termios``, so
``import reverse_ipdb`` requires a Unix platform.
"""

import os
import sys

from . import pty_bridge
from .client import DOCKER_HOST


def set_trace(*, host=None, port=None, frame=None):
    """Pause here and hand an IPython shell (with completion) to the listener.

    IPython runs over a pseudo-terminal, so completion/history/colour work. No
    listener (or a shell already active elsewhere) -> no-op.
    """
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
