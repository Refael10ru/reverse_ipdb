"""The debugger classes wired to talk over a socket instead of a local TTY.

``DetachMixin`` redefines the quit/EOF commands so that leaving the shell
*detaches* and lets the program continue, rather than raising ``BdbQuit``
into the debugged code. It must come first in the base-class list so its
methods win over the debugger's own.

Two flavours:

- ``ReversePdb`` — the stdlib pdb over a plain line-based socket (no
  completion, minimal footprint).
- ``ReverseIPdb`` — IPython's ``TerminalPdb`` driven over a pseudo-terminal
  so prompt_toolkit engages, giving tab/dot-completion, history and colour.
  It is constructed by ``pty_bridge`` with explicit stdin/stdout and
  prompt_toolkit I/O, and a ``_ripdb_close`` teardown hook.
"""

import pdb

from IPython.terminal.debugger import TerminalPdb


class DetachMixin:
    """Make quitting the shell detach-and-continue instead of killing the program.

    Comes FIRST in the bases so these overrides win over the debugger's own.
    """

    _ripdb_close = None  # set by the pty launcher; falls back to self._io

    def do_detach(self, arg):
        """detach | q | Ctrl-D
        Remove all breakpoints, tear down the connection, let the program run."""
        self.clear_all_breaks()
        close = getattr(self, "_ripdb_close", None)
        if close is not None:
            close()
        else:
            self._io.close()
        return self.do_continue(arg)

    # 'q' would normally raise BdbQuit inside the program; make it detach.
    do_quit = do_q = do_exit = do_EOF = do_detach


class ReversePdb(DetachMixin, pdb.Pdb):
    """Standard-library pdb, talking over a socket, detaching on quit."""

    def __init__(self, io):
        # nosigint: don't hijack the program's Ctrl-C handler
        # readrc:   don't pick up a stray ~/.pdbrc inside the container
        super().__init__(stdin=io, stdout=io, nosigint=True, readrc=False)
        self._io = io


class ReverseIPdb(DetachMixin, TerminalPdb):
    """IPython's debugger over a pty, detaching on quit.

    Constructed by ``pty_bridge.run`` with stdin/stdout bound to the pty slave
    and prompt_toolkit I/O in ``pt_session_options``; the launcher also sets
    ``_ripdb_close`` to tear the bridge down on detach.
    """
