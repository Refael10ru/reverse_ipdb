"""Tests for target-side connect logic: resolution, fail-open, shell lock."""

import contextlib
import socket
import threading

import pytest

from ripdb import client


def test_resolve_target_defaults(monkeypatch):
    monkeypatch.delenv("DEBUG_HOST", raising=False)
    monkeypatch.delenv("DEBUG_PORT", raising=False)
    host, port = client.resolve_target()
    assert host == client.DEFAULT_HOST
    assert port == client.DEFAULT_PORT


def test_resolve_target_env(monkeypatch):
    monkeypatch.setenv("DEBUG_HOST", "10.0.0.9")
    monkeypatch.setenv("DEBUG_PORT", "9999")
    assert client.resolve_target() == ("10.0.0.9", 9999)


def test_resolve_target_args_win(monkeypatch):
    monkeypatch.setenv("DEBUG_HOST", "10.0.0.9")
    assert client.resolve_target(host="1.2.3.4", port=1234) == ("1.2.3.4", 1234)


def test_connect_no_listener_returns_none_and_releases_lock():
    # Nothing listening on this port -> fail open, lock must be released.
    io = client.connect(host="127.0.0.1", port=1)  # port 1: refused fast
    assert io is None
    assert client._shell_lock.acquire(blocking=False) is True
    client._shell_lock.release()


def _listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    return srv, srv.getsockname()[1]


def test_connect_holds_lock_until_close():
    srv, port = _listener()
    accepted = []
    t = threading.Thread(target=lambda: accepted.append(srv.accept()))
    t.start()
    try:
        io = client.connect(host="127.0.0.1", port=port)
        assert io is not None
        # Lock held during the session: a second connect must no-op.
        assert client.connect(host="127.0.0.1", port=port) is None
        io.close()  # releases the lock via on_close
        assert client._shell_lock.acquire(blocking=False) is True
        client._shell_lock.release()
    finally:
        t.join()
        for s in accepted:
            s[0].close()
        srv.close()


def test_connect_sends_banner():
    srv, port = _listener()
    box = {}

    def _accept():
        conn, _ = srv.accept()
        box["line"] = conn.makefile("r").readline()
        box["conn"] = conn

    t = threading.Thread(target=_accept)
    t.start()
    try:
        io = client.connect(host="127.0.0.1", port=port)
        assert io is not None
        t.join(timeout=5)
        assert box["line"].startswith("*** ")
        assert "pid=" in box["line"] and "thread=" in box["line"]
        io.close()
    finally:
        if "conn" in box:
            box["conn"].close()
        srv.close()


@pytest.fixture(autouse=True)
def _reset_lock():
    # Guard against a leaked lock from a failed assertion in another test.
    yield
    if client._shell_lock.locked():
        with contextlib.suppress(RuntimeError):
            client._shell_lock.release()
