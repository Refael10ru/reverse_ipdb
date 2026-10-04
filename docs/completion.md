# Tab-completion & the full IPython experience

`ripdb` itself does **not** offer tab-completion, and that's a deliberate
trade-off rather than a missing feature. This page explains why, and how to
get completion when you need it.

## Why ripdb has no completion

Completion needs two things in the same place: the **keystrokes** (your TAB
press) and the **namespace** to complete against (the live frame's locals,
globals, and attributes). In a reverse-debugging setup they're on opposite
ends of the socket:

- The TAB key is pressed on **your** listener terminal.
- The frame being completed lives in the **target** process.

`readline` and `prompt_toolkit` — the libraries that implement completion —
only ever drive the real terminal of their *own* process. On the target that
"terminal" is our socket, which isn't a TTY, so `prompt_toolkit` can't even
put it into raw mode. That's why `ripdb` gives you a plain, line-based
`ipdb>` prompt with no completion: it keeps the tool tiny, dependency-light,
and pure dial-out.

Bridging the gap properly means giving the target a **pseudo-terminal (pty)**
so `prompt_toolkit` is happy, and turning your listener into a raw byte
pass-through. That's a real chunk of machinery — and it already exists as a
separate project.

## Use madbg when you want completion

[**madbg**](https://github.com/kmaork/madbg) ("mad debugger") implements
exactly that: it hands the debugged process a full remote TTY via a pty and
runs the IPython debugger with **tab-completion, history, line editing, and
signal handling** intact. It ships its own client, so there's nothing to
build.

```sh
pip install madbg      # or: uv pip install madbg
```

In the target process:

```python
import madbg
madbg.set_trace(ip="0.0.0.0", port=3513)   # default is 127.0.0.1:3513
```

On your machine:

```sh
madbg connect <target-host> 3513
```

madbg also offers `madbg.set_trace_on_connect()` (run until a client
connects, then break), `madbg.post_mortem()`, and attaching to an
already-running process by PID. See its README for the full API.

### The catch: madbg is "forward", ripdb is "reverse"

This is the key difference:

| | direction | who opens the port |
|---|---|---|
| **ripdb** | reverse — the target **dials out** to your listener | your machine listens |
| **madbg** | forward — the target **listens**, the client connects **in** | the target listens |

So madbg works out of the box when you can reach the target's port — the
process runs on your host, or the container published it (`docker run -p
3513:3513 …`), or you're on the same network.

### madbg from an outbound-only container (SSH reverse tunnel)

ripdb exists precisely because many containers only allow **outbound**
connections, which is the one case madbg's forward model can't reach
directly. If the container can open an outbound SSH connection to your
machine, bridge the two with a reverse tunnel:

```sh
# 1) in the target process
import madbg; madbg.set_trace(port=3513)        # listens on container's localhost:3513

# 2) from inside the container, forward its port back to your machine
ssh -N -R 3513:localhost:3513 you@your-machine  # your-machine:3513 -> container:3513

# 3) on your machine
madbg connect localhost 3513
```

Now your `madbg connect` reaches the container's debugger through the tunnel,
with full completion.

## Which to use

- **Reach the target's port (or can open an SSH tunnel), and want
  completion / history / a real IPython feel?** Use **madbg**.
- **Strictly outbound-only, no SSH, and you just need to poke at state
  quickly with the smallest possible footprint?** Use **ripdb** — you give up
  completion, but it's a few hundred lines of stdlib that dials straight out
  to a `ripdb-serve` (or `socat`/`nc`) listener.

They're complementary: reach for ripdb when you want minimal and dial-out,
reach for madbg when you want the full debugger experience.
