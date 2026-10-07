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


def set_trace(*, host=None, port=None, frame=None):
    """Pause here and hand an IPython shell (with completion) to the listener.

    IPython runs over a pseudo-terminal, so completion/history/colour work. No
    listener (or a shell already active elsewhere) -> no-op. A pty is required,
    so on a platform without ``os.openpty`` (e.g. Windows) this is a no-op too.
    """
    if not hasattr(os, "openpty"):
        return
    from . import pty_bridge
    pty_bridge.run(frame or sys._getframe(1), host=host, port=port)


# Explicit alias — IPython-over-pty is the only mode.
set_trace_ipython = set_trace
