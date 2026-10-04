"""The debugger classes wired to talk over a socket instead of a local TTY.

``DetachMixin`` redefines the quit/EOF commands so that leaving the shell
*detaches* and lets the program continue, rather than raising ``BdbQuit``
into the debugged code. It must come first in the base-class list so its
methods win over the debugger's own.
"""

import pdb


class DetachMixin:
    """Mixin giving any pdb-derived debugger a clean detach.

    Comes FIRST in the bases so these overrides win.
    """

    def __init__(self, io, **kwargs):
        # nosigint: don't hijack the program's Ctrl-C handler
        # readrc:   don't pick up a stray ~/.pdbrc inside the container
        super().__init__(stdin=io, stdout=io, nosigint=True, readrc=False, **kwargs)
        self._io = io

    def do_detach(self, arg):
        """detach | q | Ctrl-D
        Remove all breakpoints, close the connection, let the program run."""
        self.clear_all_breaks()
        self._io.close()
        return self.do_continue(arg)

    # 'q' would normally raise BdbQuit inside the program; make it detach.
    do_quit = do_q = do_exit = do_EOF = do_detach


class ReversePdb(DetachMixin, pdb.Pdb):
    """Standard-library pdb, talking over a socket, detaching on quit."""


def ipython_class():
    """Return a ReverseIPdb class, or None if IPython isn't importable.

    Built lazily so IPython stays an optional dependency.
    """
    try:
        from IPython.core.debugger import Pdb as IPdb
    except ImportError:
        return None

    class ReverseIPdb(DetachMixin, IPdb):
        pass

    return ReverseIPdb
