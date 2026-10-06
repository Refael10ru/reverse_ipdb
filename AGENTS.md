# AGENTS.md — integrating & extending ripdb

Orientation for an agent (or human) picking this up. For usage prose see
[README.md](README.md); for the completion internals see
[docs/completion.md](docs/completion.md) and [docs/api-layers.md](docs/api-layers.md).

## What it is

A **reverse** debugger: the process being debugged dials **out** to a listener
you run, and you get an IPython shell (with tab/dot-completion) over the
socket. Built for code spread across many containers that you can't connect
*in* to — they all dial one listener and you walk them from a roster.

## Public API (target side)

```python
import ripdb
ripdb.set_trace()          # default: IPython over a pty -> completion/history/colour
ripdb.set_trace_pdb()      # stdlib pdb, line-based, pure stdlib, no completion
ripdb.set_trace_ipython()  # explicit alias of set_trace()
```

All three accept the same keyword-only args and resolve **arg → env → default**:

| arg    | env          | default                | meaning                         |
|--------|--------------|------------------------|---------------------------------|
| `host` | `DEBUG_HOST` | `host.docker.internal` | listener host to dial           |
| `port` | `DEBUG_PORT` | `4444`                 | listener port                   |
| `frame`| —            | caller's frame         | where to stop (rarely passed)   |

Guarantees callers rely on — **do not break these**:

- **Fail-open.** No listener reachable within ~1s → the call is a no-op and the
  program runs on untouched. Never raise into the debugged program.
- **One shell at a time.** A module-level lock means the first thread/process to
  reach a breakpoint gets the shell; concurrent arrivals no-op. Released when
  the session's socket/pty closes.
- **Detach, don't kill.** `q` / `quit` / `exit` / EOF / `detach` remove
  breakpoints, tear down the connection, and `continue` — they never raise
  `BdbQuit` into the program.
- **Non-POSIX fallback.** No `os.openpty` → `set_trace()` transparently uses the
  line-based pdb path.

## Listener (your machine)

```sh
uv run ripdb-serve --keep          # fan-in: serve one container, detach, next…
python -m ripdb.serve --keep       # same, without uv
socat STDIO,raw,echo=0 TCP-LISTEN:4444,reuseaddr   # minimal, single session
```

`ripdb-serve` accepts every container immediately (none refused), shows a live
roster (`queued:` / `attached:` / `detached:`), and for IPython sessions puts
your terminal in raw mode so completion works. Use a **raw** listener — `nc`
mangles completion (line-buffered + local echo).

## Wire protocol (keep stable across both sides)

1. Target connects and sends one banner line:
   `*** ripdb/<mode> <host> pid=<pid> thread=<name>\n`, where `<mode>` is
   `pty` or `line`. A line without the `ripdb/` prefix is treated as `line`
   (so raw `socat`/`nc` targets still work).
2. **pty mode only:** the listener replies with one size line `"<cols> <rows>\n"`;
   the target sets the pty winsize (defaults to 80×24 if none arrives within
   `SIZE_TIMEOUT`). Then the stream is a raw vt100 terminal both ways.
3. **line mode:** plain text; the listener bridges stdin↔socket, and local EOF
   sends `detach`.

## Module map

```
ripdb/
  api.py         entry points; routes set_trace -> pty (or pdb fallback)
  client.py      dial() + shell lock + banner(); resolve_target()
  pty_bridge.py  POSIX: open pty, run TerminalPdb on it, pump <-> socket, teardown
  debugger.py    ReverseIPdb (TerminalPdb) + ReversePdb (pdb) + DetachMixin
  transport.py   SocketIO: line-mode file-like socket that never raises in-program
  serve.py       fan-in listener: accept-all + roster + raw/line pump per session
```

Completion mechanism, in one line: IPython's `TerminalPdb.cmdloop` rebinds its
`IPCompleter` to the live frame before each prompt, and we run that prompt on a
pty so TAB reaches `prompt_toolkit`. See `docs/completion.md`.

## Dev workflow

```sh
uv sync                 # venv + deps + dev tools (pytest/ruff/mypy)
uv run ruff check .     # lint   (also auto-run in CI)
uv run mypy             # types
uv run pytest -q        # tests
```

CI (`.github/workflows/ci.yml`) runs all three on push/PR for Python 3.11–3.12.
Keep the gate green.

## Regression anchors (what the tests pin)

- `tests/test_completion.py` — **echo-proof** dot-completion: an attribute name
  assembled at runtime (`zqzzmark`, absent from the source) must appear only
  *after* TAB, proving the completer evaluated the live object; and the target
  must exit 0 after detach (no leaked prompt_toolkit threads). If you touch
  `pty_bridge.py` or the protocol, this is the test that matters.
- `tests/test_serve.py` — banner/mode parsing and "many containers all queued,
  none refused".
- `tests/test_api.py` — defaults, aliasing, pdb-fallback no-op.
- `tests/test_transport.py` / `tests/test_client.py` — fail-open, lock release,
  SocketIO never raising.

## Gotchas

- **"Completion doesn't work" is almost always a stale install or a non-raw
  listener.** New build → banner shows `ripdb/pty` and the roster prints
  `queued:`/`attached:`; old build → bannerless `ripdb/...` and `session from`.
  Fix: `git pull && uv sync`. And use `ripdb-serve` (or `socat …,raw,echo=0`).
- A completion **menu** (several candidates) stays open until dismissed; clear
  the line (Ctrl-U) before typing `detach`.
- Mid-session terminal **resize** isn't propagated — size is sent once at attach.
- IPython is a hard dependency (it brings prompt_toolkit); runtime deps = just
  IPython, everything else stdlib.
