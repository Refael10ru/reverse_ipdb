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

- `set_trace(*, host=None, port=None, frame=None)`
- `set_trace_ipython(*, host=None, port=None, frame=None)`

**Responsibility:** be the entry point and nothing more. It asks Layer 2 for a
connection; if there is none, it returns immediately (the no-op / fail-open
contract). Otherwise it hands the connection to Layer 3 and starts the trace.
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

## Layer 3 — Debugger (`debugger.py`)

The interactive behaviour, built on the stdlib/IPython debuggers.

- `ReversePdb` (over `pdb.Pdb`) and `ReverseIPdb` (over IPython's `Pdb`).
- `DetachMixin` — redefines `q` / `quit` / `exit` / EOF to **detach and
  continue** instead of raising `BdbQuit` into the program, and sets
  `nosigint=True` / `readrc=False` so the debugger neither hijacks the
  program's Ctrl-C handler nor reads a stray `~/.pdbrc` from the container.

It receives a ready file-like object from Layer 4 and uses it as both stdin
and stdout; it knows nothing about sockets, timeouts, or connection policy.

## Layer 4 — Transport (`transport.py`)

The byte pipe between the debugger and the socket.

- `SocketIO` — a file-like wrapper whose defining property is that a **dead
  connection never raises into the debugged program**: writes are dropped,
  reads return EOF (which the debugger reads as detach).
- Fires an `on_close` hook so Layer 2 can release the shell lock exactly once
  when the session ends.

This is the lowest layer and the only one that touches the raw socket object.

---

## The peer — Listener (`serve.py`)

Not part of the target-side stack; it runs on **your** machine as the other
end of the socket (`python -m ripdb.serve`, or a plain `socat`/`nc`). It
accepts one session at a time and bridges your terminal to the socket
(readline editing, banner, `--keep` reconnect, draining the socket on local
EOF). It is documented alongside the layers because it speaks the same wire
protocol, but it depends on none of the four layers above and ships no shared
code with them.

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
