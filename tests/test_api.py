"""Tests for the public API surface: defaults, aliasing, and class wiring."""

import ripdb
from ripdb import api
from ripdb.debugger import ReverseIPdb, ReversePdb


def test_ipython_is_the_default():
    # set_trace() must route to the IPython flavour.
    assert ripdb.set_trace is api.set_trace
    assert ripdb.set_trace_ipython is ripdb.set_trace


def test_pdb_variant_exported():
    assert hasattr(ripdb, "set_trace_pdb")
    assert ripdb.set_trace_pdb is api.set_trace_pdb


def test_launch_uses_requested_class(monkeypatch):
    # _launch must instantiate the class it is given, with the dialed io.
    launched = {}

    class FakeIO:
        pass

    class FakeDbg:
        def __init__(self, io):
            launched["io"] = io

        def set_trace(self, frame):
            launched["frame"] = frame

    fake_io = FakeIO()
    monkeypatch.setattr(api, "connect", lambda host, port: fake_io)
    sentinel_frame = object()
    api._launch(FakeDbg, None, None, sentinel_frame)
    assert launched == {"io": fake_io, "frame": sentinel_frame}


def test_launch_is_noop_without_listener(monkeypatch):
    # connect() returning None must short-circuit before any debugger is built.
    monkeypatch.setattr(api, "connect", lambda host, port: None)

    def _boom(io):
        raise AssertionError("debugger must not be constructed with no listener")

    monkeypatch.setattr(api, "ReverseIPdb", _boom)
    api.set_trace()  # must simply return


def test_classes_share_detach_mixin():
    # Both flavours get the detach-on-quit behaviour.
    from ripdb.debugger import DetachMixin
    assert issubclass(ReverseIPdb, DetachMixin)
    assert issubclass(ReversePdb, DetachMixin)
