"""Tests for the public API surface: default routing and aliasing."""

import ripdb
from ripdb import api, pty_bridge
from ripdb.debugger import DetachMixin, ReverseIPdb


def test_set_trace_and_alias():
    assert ripdb.set_trace is api.set_trace
    assert ripdb.set_trace_ipython is ripdb.set_trace


def test_pdb_variant_is_gone():
    # The line-based pdb path was dropped; only IPython-over-pty remains.
    assert not hasattr(ripdb, "set_trace_pdb")


def test_set_trace_routes_to_pty_bridge(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        pty_bridge, "run",
        lambda frame, host=None, port=None: captured.update(
            frame=frame, host=host, port=port),
    )
    ripdb.set_trace(host="h.example", port=1234)
    assert captured["host"] == "h.example"
    assert captured["port"] == 1234
    assert hasattr(captured["frame"], "f_lineno")  # a real caller frame


def test_reverse_ipdb_detaches_on_quit():
    assert issubclass(ReverseIPdb, DetachMixin)
    assert ReverseIPdb.do_quit is DetachMixin.do_detach
    assert ReverseIPdb.do_EOF is DetachMixin.do_detach
