"""Tests for SocketIO: fail-open behaviour and the on_close hook."""

import socket

from ripdb.transport import SocketIO


def _pair():
    a, b = socket.socketpair()
    return a, b


def test_roundtrip_write_read():
    a, b = _pair()
    io_a = SocketIO(a)
    io_b = SocketIO(b)
    io_a.write("hello\n")
    io_a.flush()
    assert io_b.readline() == "hello\n"
    io_a.close()
    io_b.close()


def test_readline_returns_empty_on_peer_close():
    a, b = _pair()
    io_a = SocketIO(a)
    b.close()
    # Peer gone: readline must return "" (EOF -> pdb detaches), never raise.
    assert io_a.readline() == ""
    assert io_a.dead is True
    io_a.close()


def test_write_after_death_is_dropped_not_raised():
    a, b = _pair()
    io_a = SocketIO(a)
    b.close()
    io_a.readline()  # marks dead
    # Must not raise even though the peer is gone.
    assert io_a.write("ignored") == len("ignored")
    io_a.flush()
    io_a.close()


def test_on_close_fires_exactly_once():
    a, b = _pair()
    calls = []
    io_a = SocketIO(a, on_close=lambda: calls.append(1))
    io_a.close()
    io_a.close()
    assert calls == [1]
    b.close()


def test_isatty_is_false():
    a, b = _pair()
    io_a = SocketIO(a)
    assert io_a.isatty() is False
    io_a.close()
    b.close()
