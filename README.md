# ripdb — reverse-connecting pdb

Debugging a process that has no terminal — a container, a daemon, a CI worker — is
awkward: you can't attach a shell to something that isn't reading from one. `ripdb`
flips the direction. Instead of *you* attaching *in*, the target process **dials out**
to a listener you run and hands you a `pdb` shell over the socket.

```
┌──────────────────────────┐        TCP connect() OUT        ┌──────────────────────────┐
│  TARGET PROCESS           │ ──────────────────────────────►│  YOUR MACHINE            │
│  import ripdb             │                                 │  python -m ripdb.serve   │
│  ripdb.set_trace()        │ ◄──────── pdb over socket ─────►│  (gives you the shell)   │
└──────────────────────────┘                                 └──────────────────────────┘
```

If nobody is listening, `set_trace()` is a **no-op** and the program runs on untouched.

## Install

```sh
pip install -e .          # from this repo
pip install -e ".[dev]"   # plus pytest / ruff / mypy for development
```

## Use

**In the target** (container/daemon/worker), point it at your machine and drop a
breakpoint in the code:

```python
import ripdb
ripdb.set_trace()                          # host/port from DEBUG_HOST / DEBUG_PORT
ripdb.set_trace(host="10.0.0.5", port=4444)  # or set them explicitly
```

Configuration resolves **argument → environment variable → default**:

| Setting | Env var      | Default               |
|---------|--------------|-----------------------|
| host    | `DEBUG_HOST` | `host.docker.internal`|
| port    | `DEBUG_PORT` | `4444`                |

For the IPython debugger, use `ripdb.set_trace_ipython()`.

**On your machine**, catch the session. Either use the bundled listener:

```sh
python -m ripdb.serve            # one session, then exit
python -m ripdb.serve --keep     # keep listening after each detach
ripdb-serve --port 4444          # same thing, console script
```

…or a plain socket tool, no install required:

```sh
socat readline TCP-LISTEN:4444,reuseaddr
# or:  nc -l 4444
```

The bundled `serve` adds local line editing/history (readline), a parsed banner
showing which host/pid/thread connected, and `--keep` to re-listen automatically.

## In the shell

It's ordinary `pdb` — `p`, `n`, `s`, `c`, `bt`, `l`, evaluate expressions, etc.
One difference: **quitting detaches instead of killing your program.**

| Command             | Effect                                             |
|---------------------|----------------------------------------------------|
| `detach` / `q` / Ctrl-D | remove breakpoints, close the socket, **let the program continue** |
| `c` (continue)      | resume; the trace stays armed for later breakpoints |

This is deliberate: a stray `q` over a flaky debugging link should never raise
`BdbQuit` into production code.

## Design notes

- **Fail-open.** Can't connect within ~1s → `set_trace()` returns and the program
  is unaffected. A connection that dies mid-session never raises into the debugged
  program: writes are dropped, reads return EOF (which `pdb` treats as detach).
- **One shell at a time.** The first thread to hit a breakpoint takes the shell;
  concurrent arrivals pass straight through. The lock is held for the whole session
  and released when the socket closes.
- **No surprises in the target.** It doesn't hijack the program's Ctrl-C handler
  (`nosigint`) and doesn't read a stray `~/.pdbrc` from inside the container
  (`readrc=False`).
- **Small surface.** The only runtime dependency is IPython (for the
  `set_trace_ipython()` flavour); everything else is stdlib.

## Security

`set_trace()` opens a `pdb` shell to whoever connects on the port — and a `pdb`
shell can run arbitrary code in the target process. There is **no authentication**.
Only enable it on trusted networks (loopback, a private debug interface, an SSH
tunnel), never on a public port. Leaving a `ripdb.set_trace()` enabled on an
exposed port is equivalent to leaving a remote code-execution endpoint open.

## Package layout

```
ripdb/
  __init__.py    public API re-exports (set_trace, set_trace_ipython)
  api.py         the entry points
  client.py      target side: resolve host/port, dial out, single-shell lock
  debugger.py    ReversePdb + ReverseIPdb + detach-on-quit mixin
  transport.py   SocketIO: file-like socket wrapper that never raises into the program
  serve.py       the catcher: python -m ripdb.serve
tests/           pytest suite (unit + end-to-end over a real socket)
```

## Tests

```sh
pip install -e ".[dev]"
python -m pytest
```
