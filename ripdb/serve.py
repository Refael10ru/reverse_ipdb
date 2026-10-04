"""The catcher: a listener that accepts reverse-pdb sessions.

Equivalent to ``socat readline TCP-LISTEN:4444,reuseaddr`` but with local
line editing/history (via readline), a parsed banner, and an optional
reconnect loop.

Usage::

    python -m ripdb.serve [--host HOST] [--port PORT] [--keep]

Handles one session at a time. With ``--keep`` it re-listens after each
session detaches, which pairs with the single-shell behaviour in the lib.
"""

import argparse
import contextlib
import selectors
import socket
import sys

with contextlib.suppress(ImportError):  # readline is absent on some platforms
    import readline  # noqa: F401  (import enables line editing on sys.stdin)


def _pump(conn):
    """Shuttle bytes between the local terminal and the connected session.

    Returns when either side closes. stdin -> socket and socket -> stdout run
    through a selector so a keypress and incoming output never block each
    other.
    """
    conn.setblocking(False)
    sel = selectors.DefaultSelector()
    sel.register(conn, selectors.EVENT_READ, "sock")
    stdin_fileno = sys.stdin.fileno()
    sel.register(stdin_fileno, selectors.EVENT_READ, "stdin")
    stdin_open = True

    try:
        while True:
            for key, _ in sel.select():
                if key.data == "sock":
                    try:
                        data = conn.recv(4096)
                    except BlockingIOError:
                        continue
                    if not data:
                        return  # remote detached / closed
                    sys.stdout.write(data.decode("utf-8", "replace"))
                    sys.stdout.flush()
                elif stdin_open:  # stdin
                    line = sys.stdin.readline()
                    if not line:  # local EOF (Ctrl-D) -> detach, then drain
                        try:
                            conn.sendall(b"detach\n")
                        except OSError:
                            return
                        # Stop watching stdin but keep draining the socket so
                        # the remote's final output isn't lost.
                        sel.unregister(stdin_fileno)
                        stdin_open = False
                        continue
                    try:
                        conn.sendall(line.encode("utf-8"))
                    except OSError:
                        return
    finally:
        sel.close()


def serve(host="0.0.0.0", port=4444, keep=False):
    """Listen on host:port and hand each incoming session to the terminal."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(1)
        print(f"*** ripdb listening on {host}:{port} "
              f"({'keep-alive' if keep else 'one-shot'}) — Ctrl-C to quit",
              file=sys.stderr)
        while True:
            conn, addr = listener.accept()
            print(f"*** session from {addr[0]}:{addr[1]}", file=sys.stderr)
            with conn:
                _pump(conn)
            print("*** session ended", file=sys.stderr)
            if not keep:
                return


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ripdb.serve",
        description="Catch reverse-connecting pdb sessions.",
    )
    parser.add_argument("--host", default="0.0.0.0",
                        help="interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=4444,
                        help="port to listen on (default: 4444)")
    parser.add_argument("--keep", action="store_true",
                        help="keep listening for a new session after each detach")
    args = parser.parse_args(argv)
    try:
        serve(args.host, args.port, args.keep)
    except KeyboardInterrupt:
        print("\n*** bye", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
