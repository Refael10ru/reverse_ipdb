"""Concurrency example: the single-shell lock in action.

Several worker threads all hit a breakpoint at roughly the same time. Only
the FIRST one to arrive gets the interactive shell; the others find the lock
held, treat set_trace() as a no-op, and run straight through.

    uv run reverse_ipdb-serve                   # terminal 1
    uv run python examples/threads.py    # terminal 2

You'll get exactly one `ipdb>` prompt (the full IPython debugger, with
tab-completion). Inspect `worker_id` — try `worker<TAB>` — then `detach`
(or Ctrl-D); every thread still finishes.
"""

import os
import threading
import time

import reverse_ipdb

HOST = os.environ.get("DEBUG_HOST", "127.0.0.1")
PORT = int(os.environ.get("DEBUG_PORT", "4444"))


def worker(worker_id):
    time.sleep(0.05 * worker_id)  # stagger slightly
    reverse_ipdb.set_trace(host=HOST, port=PORT)  # only the first caller gets the shell
    print(f"worker {worker_id} done")


def main():
    threads = [threading.Thread(target=worker, args=(i,), name=f"w{i}") for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("all workers finished")


if __name__ == "__main__":
    main()
