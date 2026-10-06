"""Public entry points: set_trace / set_trace_pdb / set_trace_ipython.

Call these directly from the code you want to pause::

    import ripdb
    ripdb.set_trace()          # IPython over a pty -> tab/dot-completion
    ripdb.set_trace_pdb()      # stdlib pdb, line-based, pure stdlib

``set_trace_ipython`` is kept as an explicit alias of ``set_trace``.

Imports of IPython / prompt_toolkit are deferred until a listener is actually
reached, so a breakpoint with nobody listening stays a cheap no-op.
"""

import os
import sys


def set_trace(*, host=None, port=None, frame=None):
    """Pause here and hand an IPython shell (with completion) to the listener.

    IPython over a pseudo-terminal is the default; use ``set_trace_pdb`` for
    the stdlib pdb. No listener (or a shell already active elsewhere) -> no-op.
    On platforms without pty support (e.g. Windows) this falls back to the
    line-based pdb automatically.
    """
    frame = frame or sys._getframe(1)
    if not hasattr(os, "openpty"):
        set_trace_pdb(host=host, port=port, frame=frame)
        return
    from . import pty_bridge
    pty_bridge.run(frame, host=host, port=port)


def set_trace_pdb(*, host=None, port=None, frame=None):
    """Pause here with the standard-library pdb over a plain line socket."""
    from .client import connect
    from .debugger import ReversePdb
    io = connect(host, port)
    if io is None:
        return
    ReversePdb(io).set_trace(frame or sys._getframe(1))


# IPython is the default, so this is simply an explicit alias of set_trace.
set_trace_ipython = set_trace
