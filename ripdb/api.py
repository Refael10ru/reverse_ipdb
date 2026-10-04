"""Public entry points: set_trace / set_trace_ipython.

Call these directly from the code you want to pause::

    import ripdb
    ripdb.set_trace()

Concurrency: the shell lock is acquired inside ``client.connect`` and held
for the whole debugging session (released when the socket closes on detach),
so the first thread to reach a breakpoint gets the shell and the rest pass
straight through. ``Pdb.set_trace`` only installs the trace hook and returns
immediately, which is why the lock cannot be released here.
"""

import sys

from .client import connect
from .debugger import ReverseIPdb, ReversePdb


def set_trace(*, host=None, port=None, frame=None):
    """Pause here and hand a pdb shell to a listener dialed over TCP.

    No listener (or a shell already active elsewhere) -> no-op.
    """
    io = connect(host, port)
    if io is None:
        return
    ReversePdb(io).set_trace(frame or sys._getframe(1))


def set_trace_ipython(*, host=None, port=None, frame=None):
    """Like set_trace, but drops into IPython's debugger."""
    io = connect(host, port)
    if io is None:
        return
    ReverseIPdb(io).set_trace(frame or sys._getframe(1))
