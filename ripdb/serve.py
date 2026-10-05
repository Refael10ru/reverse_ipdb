"""The catcher: a listener that fans in reverse-pdb sessions.

Built for code spread across many containers: each one dials OUT to this one
listener. Incoming containers are accepted immediately (so none is ever
refused — each stays paused at its ``set_trace``) and queued; you walk them
one at a time, with a live roster of who is waiting.

Usage::

    python -m ripdb.serve [--host HOST] [--port PORT] [--keep]

Without ``--keep`` the listener serves the first container and exits. With
``--keep`` it keeps serving: detach from one and you drop straight into the
next one waiting.
"""

import argparse
import contextlib
import queue
import socket
import sys
import threading

with contextlib.suppress(ImportError):  # readline is absent on some platforms
    import readline  # noqa: F401  (import enables line editing on sys.stdin)


def _note(msg):
    """Print a roster line to stderr, flushed so it shows up live."""
    print(f"*** {msg}", file=sys.stderr, flush=True)


def _read_banner(conn):
    """Read the target's first line (its id banner) one byte at a time.

    Byte-at-a-time so we never over-read into the debugger output that
    follows — those bytes must stay in the socket for _pump to stream later.
    """
    buf = bytearray()
    while not buf.endswith(b"\n"):
        try:
            chunk = conn.recv(1)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
    return buf.decode("utf-8", "replace").strip().lstrip("* ").strip()


def _pump(conn):
    """Shuttle bytes between the local terminal and the connected session.

    A background thread copies the socket to stdout (so output and the banner
    stream in on their own), while the foreground copies stdin to the socket.
    Local EOF (Ctrl-D) sends ``detach`` so the debugged program continues.
    """
    def to_stdout():
        while data := conn.recv(4096):
            sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()

    reader = threading.Thread(target=to_stdout, daemon=True)
    reader.start()
    with contextlib.suppress(OSError):
        for line in sys.stdin:
            conn.sendall(line.encode("utf-8"))
        conn.sendall(b"detach\n")  # local EOF -> let the program run on
    reader.join()  # drain any final output before the session ends


def serve(host="0.0.0.0", port=4444, keep=False):
    """Fan in reverse-pdb sessions: accept all, serve one at a time.

    A background thread accepts every incoming container (reading its banner
    and queueing it, so nothing is refused and each stays paused). The
    foreground pops them in arrival order and drives one at a time.
    """
    sessions = queue.Queue()
    stopping = threading.Event()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(128)  # roomy backlog so a burst of containers isn't refused
        _note(f"ripdb listening on {host}:{port} "
              f"({'keep-alive' if keep else 'one-shot'}) — Ctrl-C to quit")

        def acceptor():
            while not stopping.is_set():
                try:
                    conn, addr = listener.accept()
                except OSError:
                    return  # listener closed -> we're shutting down
                ident = _read_banner(conn) or f"{addr[0]}:{addr[1]}"
                if stopping.is_set():
                    conn.close()
                    return
                sessions.put((conn, ident))
                _note(f"queued: {ident}  ({sessions.qsize()} waiting)")

        threading.Thread(target=acceptor, daemon=True).start()

        try:
            while True:
                conn, ident = sessions.get()
                waiting = sessions.qsize()
                suffix = f"  ({waiting} still waiting)" if waiting else ""
                _note(f"attached: {ident}{suffix}")
                with conn:
                    _pump(conn)
                _note(f"detached: {ident}")
                if not keep:
                    return
        finally:
            stopping.set()
            with contextlib.suppress(OSError):
                listener.close()  # unblock the acceptor's accept()
            while True:
                try:
                    pending, _ = sessions.get_nowait()
                except queue.Empty:
                    break
                with contextlib.suppress(OSError):
                    pending.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ripdb.serve",
        description="Fan in reverse-connecting pdb sessions from many containers.",
    )
    parser.add_argument("--host", default="0.0.0.0",
                        help="interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=4444,
                        help="port to listen on (default: 4444)")
    parser.add_argument("--keep", action="store_true",
                        help="after a detach, drop into the next waiting container "
                             "instead of exiting")
    args = parser.parse_args(argv)
    try:
        serve(args.host, args.port, args.keep)
    except KeyboardInterrupt:
        print("\n*** bye", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
