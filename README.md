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

This project is managed with [uv](https://docs.astral.sh/uv/):

```sh
uv sync                   # create the venv and install deps (incl. dev tools)
uv run ripdb-serve        # run the listener
uv run python -m ripdb ...# or run anything inside the environment
```

Prefer plain pip? `pip install -e .` still works (the dev tools live in the
`dev` dependency group: `uv sync` installs them, or `pip install pytest ruff
mypy`).

## Use

**In the target** (container/daemon/worker), point it at your machine and drop a
breakpoint in the code:

```python
import ripdb
ripdb.set_trace()                          # host/port from DEBUG_HOST / DEBUG_PORT
ripdb.set_trace(host="10.0.0.5", port=4444)  # or set them explicitly
```

`set_trace()` drops into the **IPython** debugger by default. If you'd rather
use the standard-library `pdb`, call `ripdb.set_trace_pdb()` instead.
(`ripdb.set_trace_ipython()` is kept as an explicit alias of `set_trace()`.)

Configuration resolves **argument → environment variable → default**:

| Setting | Env var      | Default               |
|---------|--------------|-----------------------|
| host    | `DEBUG_HOST` | `host.docker.internal`|
| port    | `DEBUG_PORT` | `4444`                |

**On your machine**, catch the session. Either use the bundled listener:

```sh
uv run ripdb-serve               # one session, then exit
uv run ripdb-serve --keep        # keep listening after each detach
uv run ripdb-serve --port 4444   # pick the port
# (or: python -m ripdb.serve, once the package is installed)
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
- **Small surface.** IPython (the default debugger) is the only runtime
  dependency; everything else is stdlib.

## Security

`set_trace()` opens a `pdb` shell to whoever connects on the port — and a `pdb`
shell can run arbitrary code in the target process. There is **no authentication**.
Only enable it on trusted networks (loopback, a private debug interface, an SSH
tunnel), never on a public port. Leaving a `ripdb.set_trace()` enabled on an
exposed port is equivalent to leaving a remote code-execution endpoint open.

For how these modules stack into layers and which guarantee each one owns, see
[docs/api-layers.md](docs/api-layers.md).

## Package layout

```
ripdb/
  __init__.py    public API re-exports (set_trace, set_trace_pdb, set_trace_ipython)
  api.py         the entry points
  client.py      target side: resolve host/port, dial out, single-shell lock
  debugger.py    ReversePdb + ReverseIPdb + detach-on-quit mixin
  transport.py   SocketIO: file-like socket wrapper that never raises into the program
  serve.py       the catcher: python -m ripdb.serve
examples/        runnable scripts for trying it locally (see examples/README.md)
tests/           pytest suite (unit + end-to-end over a real socket)
```

## Examples

See [examples/](examples/) for runnable scripts — a basic breakpoint, the
single-shell lock across threads, and attach/detach against a long-running
daemon. Start a listener (`uv run ripdb-serve`) then, e.g., `uv run python
examples/basic.py`.

## Tests

```sh
uv run pytest          # tests
uv run ruff check .    # lint
uv run mypy            # type-check
```
