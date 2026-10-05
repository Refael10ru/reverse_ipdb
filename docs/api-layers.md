# API layers

`ripdb` is organised as **four thin layers** on the target side, stacked so
that each one depends only on the layer directly below it. A fifth component,
the listener, is the remote *peer* of the stack rather than another layer in
it — it lives on your machine, at the far end of the socket.

```
            TARGET PROCESS                                  YOUR MACHINE
 ┌───────────────────────────────────┐
 │ 1. Public API      api.py          │   what you call: ripdb.set_trace()
 │        │                           │
 │        ▼                           │
 │ 2. Session         client.py       │   decide IF a session happens:
 │        │                           │   resolve host/port, dial out,
 │        │                           │   fail-open, single-shell lock
 │        ▼                           │
 │ 3. Debugger        debugger.py     │   the pdb/IPython shell + detach
 │        │                           │   semantics (q/EOF -> continue)
 │        ▼                           │
 │ 4. Transport       transport.py    │   bytes on the wire; never raises
 │        │                           │   into the debugged program
 └────────┼──────────────────────────┘
          │  TCP (pdb protocol over a socket)      ┌────────────────────────┐
          └───────────────────────────────────────│  Listener   serve.py   │
                                                   │  the peer: accepts the │
                                                   │  session, bridges your │
                                                   │  terminal to the socket│
                                                   └────────────────────────┘
```

A breakpoint travels **down** the stack (1 → 4), crosses the socket, and the
listener drives it from the other end.

---

## Layer 1 — Public API (`api.py`, re-exported from `__init__.py`)

The only surface callers touch.

- `set_trace(*, host=None, port=None, frame=None)` — **IPython** debugger (the default)
- `set_trace_pdb(*, host=None, port=None, frame=None)` — stdlib `pdb`
- `set_trace_ipython` — explicit alias of `set_trace`

**Responsibility:** be the entry point and nothing more. The `_launch` helper
picks the debugger class (Layer 3) and asks Layer 2 for a connection; if there
is none, it returns immediately (the no-op / fail-open contract). Otherwise it
hands the connection to Layer 3 and starts the trace.
It holds no sockets, no configuration logic, and no debugger behaviour of its
own — so the public contract stays stable even if the layers beneath change.

## Layer 2 — Session / connection (`client.py`)

Decides **whether a debugging session should happen at all**, before any
debugger exists.

- `resolve_target()` — host/port precedence: **argument → env var → default**.
- `connect()` — dials the listener with a short timeout and **fails open**
  (returns `None`) when nobody is listening.
- The module-level **single-shell lock** — the first thread to reach a
  breakpoint wins the shell; concurrent arrivals get `None` and pass through.
  The lock is held for the whole session and released via the transport's
  close hook.

This is the layer that enforces the two headline guarantees — *no listener →
no-op* and *one shell at a time* — and it does so without importing the
debugger, so the policy is testable on its own.

## Layer 3 — Debugger (`debugger.py`, `pty_bridge.py`)

The interactive behaviour, built on the stdlib/IPython debuggers.

- `ReverseIPdb` (over IPython's `TerminalPdb`) is the default. `pty_bridge.py`
  launches it on a **pseudo-terminal** so `prompt_toolkit` engages and
  computes **tab/dot-completion** against the live frame; two pump threads
  shuttle the pty master to/from the socket, and a teardown hook closes the
  pty, shuts down the prompt thread, and releases the shell lock on detach.
- `ReversePdb` (over `pdb.Pdb`) is the line-based fallback (`set_trace_pdb`,
  or any non-POSIX target).
- `DetachMixin` — redefines `q` / `quit` / `exit` / EOF to **detach and
  continue** instead of raising `BdbQuit` into the program; both flavours set
  `nosigint=True` / `readrc=False` so the debugger neither hijacks the
  program's Ctrl-C handler nor reads a stray `~/.pdbrc` from the container.

## Layer 4 — Transport (`transport.py` for line mode; the pty for IPython)

The byte pipe between the debugger and the socket.

- `SocketIO` — the line-mode wrapper whose defining property is that a **dead
  connection never raises into the debugged program**: writes are dropped,
  reads return EOF (which the debugger reads as detach). Fires an `on_close`
  hook so Layer 2 can release the shell lock exactly once.
- For IPython the pty plays this role: `pty_bridge`'s pump is the byte pipe,
  and its teardown is what releases the lock.

This is the lowest layer and the only one that touches the raw socket object.

---

## The peer — Listener (`serve.py`)

Not part of the target-side stack; it runs on **your** machine as the other
end of the socket (`python -m ripdb.serve`, or a plain `socat`/`nc`). A
background acceptor thread fans in **every** connecting container at once —
reading each one's banner and queueing it so none is refused — while the
foreground serves them one at a time with a live roster (`--keep` to advance
into the next instead of exiting). It reads each banner's mode: IPython/pty
sessions get a raw-mode pass-through (terminal size sent, bytes forwarded via
select, so completion and special keys work); line sessions get the simple
stdin/stdout bridge. It is documented alongside the layers because it speaks
the same wire protocol, but it depends on none of the layers above and ships
no shared code with them.

## Why these boundaries

Each guarantee lives in exactly one layer, so it can be reasoned about and
tested in isolation:

| Guarantee                              | Layer that owns it |
|----------------------------------------|--------------------|
| Stable public call surface             | 1 — Public API     |
| No listener → no-op; one shell at a time | 2 — Session       |
| Quit detaches instead of killing       | 3 — Debugger       |
| A broken link never crashes the program | 4 — Transport     |

Dependencies only ever point downward (1→2→3→4), and the listener sits off to
the side, connected solely by the socket.
