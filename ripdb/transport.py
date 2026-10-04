"""File-like wrapper over a socket used as the debugger's stdin/stdout.

The whole point of this wrapper is that a dead connection must never raise
into the program being debugged. Writes to a broken socket are dropped and
reads return EOF, which pdb interprets as ``do_EOF`` and detaches cleanly.
"""


class SocketIO:
    """A file-like object over a socket.

    Once the connection dies, ``dead`` is set and every further operation is
    a quiet no-op (writes dropped, reads return ""), so the debugged program
    keeps running instead of crashing on a broken pipe.
    """

    def __init__(self, sock, on_close=None):
        self._sock = sock
        self._f = sock.makefile("rw", buffering=1, encoding="utf-8", errors="replace")
        self.dead = False
        self._on_close = on_close

    def write(self, s):
        if not self.dead:
            try:
                self._f.write(s)
            except OSError:
                self.dead = True
        return len(s)

    def flush(self):
        if not self.dead:
            try:
                self._f.flush()
            except OSError:
                self.dead = True

    def readline(self):
        if not self.dead:
            try:
                line = self._f.readline()
                if line:
                    return line
            except OSError:
                pass
            self.dead = True
        return ""  # pdb sees EOF -> do_EOF -> detach

    def isatty(self):
        return False

    def close(self):
        self.dead = True
        for obj in (self._f, self._sock):
            try:
                obj.close()
            except OSError:
                pass
        if self._on_close is not None:
            cb, self._on_close = self._on_close, None
            try:
                cb()
            except Exception:
                pass
