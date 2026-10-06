"""Tests for the public API surface: defaults, aliasing, and routing."""

import ripdb
from ripdb import api, client, pty_bridge
from ripdb.debugger import DetachMixin, ReverseIPdb, ReversePdb


def test_ipython_is_the_default():
    # set_trace() is the IPython-over-pty flavour; _ipython is its alias.
    assert ripdb.set_trace is api.set_trace
    assert ripdb.set_trace_ipython is ripdb.set_trace


def test_pdb_variant_exported():
    assert hasattr(ripdb, "set_trace_pdb")
    assert ripdb.set_trace_pdb is api.set_trace_pdb


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
    # A real caller frame must be passed (so pdb stops in the caller).
    assert hasattr(captured["frame"], "f_lineno")


def test_set_trace_pdb_is_noop_without_listener(monkeypatch):
    # connect() returning None must short-circuit before any debugger is built.
    monkeypatch.setattr(client, "connect", lambda host, port: None)
    built = []
    monkeypatch.setattr(
        "ripdb.debugger.ReversePdb",
        lambda io: built.append(io) or (_ for _ in ()).throw(AssertionError("built")),
    )
    ripdb.set_trace_pdb()  # must simply return
    assert built == []


def test_both_flavours_detach_on_quit():
    assert issubclass(ReverseIPdb, DetachMixin)
    assert issubclass(ReversePdb, DetachMixin)
    # q/EOF are remapped to detach on both.
    assert ReverseIPdb.do_quit is DetachMixin.do_detach
    assert ReversePdb.do_EOF is DetachMixin.do_detach
