"""Tests for the fan-in listener: banner parsing and no-container-refused."""

import socket
import threading
import time

from ripdb import serve as serve_mod


def test_read_banner_parses_mode_without_overreading():
    a, b = socket.socketpair()
    # Banner line followed immediately by debugger output on the same stream.
    a.sendall(b"*** ripdb/pty host pid=1 thread=MainThread\n> frame\n(Pdb) ")
    mode, ident = serve_mod._read_banner(b)
    assert mode == "pty"
    assert ident == "host pid=1 thread=MainThread"
    # The bytes after the banner must still be readable (not consumed).
    rest = b.recv(4096)
    assert rest == b"> frame\n(Pdb) "
    a.close()
    b.close()


def test_read_banner_defaults_to_line_without_prefix():
    a, b = socket.socketpair()
    a.sendall(b"some-host pid=9\n")
    mode, ident = serve_mod._read_banner(b)
    assert mode == "line"
    assert ident == "some-host pid=9"
    a.close()
    b.close()


def test_read_banner_empty_on_immediate_close():
    a, b = socket.socketpair()
    a.close()
    assert serve_mod._read_banner(b) == ("line", "")
    b.close()


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_simultaneous_containers_are_all_queued_none_refused():
    """The core fan-in guarantee: many containers connecting at once all get
    accepted and queued; none is refused and dropped."""
    port = _free_port()
    queued = []

    # Capture roster notices instead of printing them.
    original_note = serve_mod._note
    serve_mod._note = lambda msg: queued.append(msg)

    # Run serve in keep mode in a background thread; we never drive a session,
    # we only assert the acceptor queues everyone.
    t = threading.Thread(target=serve_mod.serve, args=("127.0.0.1", port, True), daemon=True)
    t.start()
    try:
        # Wait for the listener to be up.
        deadline = time.time() + 5
        conns = []
        while time.time() < deadline and not any("listening" in m for m in queued):
            time.sleep(0.02)

        # Fire several "containers" at once.
        for i in range(5):
            c = socket.create_connection(("127.0.0.1", port), timeout=2)
            c.sendall(f"container-{i} pid={100 + i} thread=MainThread\n".encode())
            conns.append(c)

        # All five must show up as queued (none refused).
        deadline = time.time() + 5
        while time.time() < deadline:
            if sum("queued:" in m for m in queued) >= 5:
                break
            time.sleep(0.02)

        queued_lines = [m for m in queued if "queued:" in m]
        assert len(queued_lines) == 5, queued_lines
        for i in range(5):
            assert any(f"container-{i} pid={100 + i}" in m for m in queued_lines)
    finally:
        serve_mod._note = original_note
        for c in conns:
            c.close()
