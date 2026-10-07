"""Basic example: one breakpoint, inspect some locals.

Run the listener first (in another terminal):

    uv run reverse_ipdb-serve

then run this:

    uv run python examples/basic.py

At the `ipdb>` prompt you get the full IPython debugger, including
**tab/dot-completion** against the live frame — try:

    order[0].<TAB>   ·   ord<TAB>   ·   p total   ·   pp order   ·   bt

Type `detach` (or Ctrl-D) to let the program finish.

Use `reverse_ipdb-serve` as the listener (it puts your terminal in raw mode so
completion works). With no listener running, the breakpoint is a no-op and
the script just prints its result.
"""

import os

import reverse_ipdb

# Point at the local listener by default; override with DEBUG_HOST/DEBUG_PORT.
HOST = os.environ.get("DEBUG_HOST", "127.0.0.1")
PORT = int(os.environ.get("DEBUG_PORT", "4444"))


def total_price(order):
    total = sum(item["qty"] * item["price"] for item in order)
    # Pause here so you can inspect `order` and `total` before they're returned.
    reverse_ipdb.set_trace(host=HOST, port=PORT)
    return total


def main():
    order = [
        {"name": "widget", "qty": 3, "price": 2.5},
        {"name": "gadget", "qty": 1, "price": 9.0},
    ]
    print("total:", total_price(order))


if __name__ == "__main__":
    main()
