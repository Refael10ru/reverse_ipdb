"""Tests for target-side dial logic: resolution, fail-open, shell lock, banner."""

import contextlib
import socket
import threading

import pytest

from ripdb import client


def test_resolve_target_defaults(monkeypatch):
    monkeypatch.delenv("DEBUG_HOST", raising=False)
    monkeypatch.delenv("DEBUG_PORT", raising=False)
    assert client.resolve_target() == (client.DEFAULT_HOST, client.DEFAULT_PORT)


def test_resolve_target_env(monkeypatch):
    monkeypatch.setenv("DEBUG_HOST", "10.0.0.9")
    monkeypatch.setenv("DEBUG_PORT", "9999")
    assert client.resolve_target() == ("10.0.0.9", 9999)


def test_resolve_target_args_win(monkeypatch):
    monkeypatch.setenv("DEBUG_HOST", "10.0.0.9")
    assert client.resolve_target(host="1.2.3.4", port=1234) == ("1.2.3.4", 1234)


def test_banner_is_pty_tagged():
    line = client.banner()
    assert line.startswith("*** ripdb/pty ")
    assert "pid=" in line and "thread=" in line and line.endswith("\n")


def test_dial_no_listener_returns_none_and_releases_lock():
    # Port 1 refuses fast -> fail open, and the lock must be released.
    assert client.dial(host="127.0.0.1", port=1) is None
    assert client._shell_lock.acquire(blocking=False) is True
    client._shell_lock.release()


def test_dial_holds_lock_until_release():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    accepted = []
    t = threading.Thread(target=lambda: accepted.append(srv.accept()))
    t.start()
    try:
        dialed = client.dial(host="127.0.0.1", port=port)
        assert dialed is not None
        sock, release = dialed
        # Lock held during the session: a second dial must no-op.
        assert client.dial(host="127.0.0.1", port=port) is None
        release()
        assert client._shell_lock.acquire(blocking=False) is True
        client._shell_lock.release()
        sock.close()
    finally:
        t.join()
        for s in accepted:
            s[0].close()
        srv.close()


@pytest.fixture(autouse=True)
def _reset_lock():
    # Guard against a leaked lock from a failed assertion in another test.
    yield
    if client._shell_lock.locked():
        with contextlib.suppress(RuntimeError):
            client._shell_lock.release()
