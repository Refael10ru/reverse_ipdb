"""Long-running example: attach on demand, detach, re-attach later.

Simulates a daemon/worker that loops forever. Each iteration calls
set_trace(). When no listener is running the loop just keeps going; start a
listener and the NEXT iteration drops you into a shell.

Pair it with the reconnect listener so you can attach, detach, and attach
again without restarting anything:

    uv run ripdb-serve --keep               # terminal 1 (stays up across detaches)
    uv run python examples/daemon_loop.py   # terminal 2

At the prompt, inspect `tick`, then `detach`; the loop runs on and offers you
the shell again on the next tick. Ctrl-C here stops the daemon.
"""

import os
import time

import ripdb

HOST = os.environ.get("DEBUG_HOST", "127.0.0.1")
PORT = int(os.environ.get("DEBUG_PORT", "4444"))


def main():
    tick = 0
    print("daemon running — start `ripdb-serve --keep` to attach, Ctrl-C to stop")
    while True:
        tick += 1
        ripdb.set_trace(host=HOST, port=PORT)  # no-op until a listener appears
        print(f"tick {tick}")
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
