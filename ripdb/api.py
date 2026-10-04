"""Public entry points: set_trace / set_trace_pdb / set_trace_ipython.

Call these directly from the code you want to pause::

    import ripdb
    ripdb.set_trace()          # IPython debugger (the default)
    ripdb.set_trace_pdb()      # stdlib pdb, if you'd rather not use IPython

``set_trace_ipython`` is kept as an explicit alias of ``set_trace``.

Concurrency: the shell lock is acquired inside ``client.connect`` and held
for the whole debugging session (released when the socket closes on detach),
so the first thread to reach a breakpoint gets the shell and the rest pass
straight through. ``Pdb.set_trace`` only installs the trace hook and returns
immediately, which is why the lock cannot be released here.
"""

import sys

from .client import connect
from .debugger import ReverseIPdb, ReversePdb


def _launch(cls, host, port, frame):
    """Dial out and drop the caller's frame into the given debugger class.

    No listener (or a shell already active elsewhere) -> no-op.
    """
    io = connect(host, port)
    if io is None:
        return
    cls(io).set_trace(frame)


def set_trace(*, host=None, port=None, frame=None):
    """Pause here and hand an IPython debugger shell to a listener over TCP.

    IPython is the default flavour; use ``set_trace_pdb`` for the stdlib pdb.
    """
    _launch(ReverseIPdb, host, port, frame or sys._getframe(1))


def set_trace_pdb(*, host=None, port=None, frame=None):
    """Like set_trace, but drops into the standard-library pdb."""
    _launch(ReversePdb, host, port, frame or sys._getframe(1))


# IPython is the default, so this is simply an explicit alias of set_trace.
set_trace_ipython = set_trace
