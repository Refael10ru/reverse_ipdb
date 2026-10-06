"""madbg example: the same scenario as basic.py, but with tab-completion.

madbg is a separate tool (not a ripdb dependency) that gives the target a
full remote IPython TTY — so `order.` + TAB, history, and line editing all
work. It is "forward": the target listens and you connect in. See
docs/completion.md for why ripdb can't do this and when to prefer each.

    # terminal 1 — the target; `--with madbg` pulls madbg in just for this run
    uv run --with madbg python examples/madbg_example.py

    # terminal 2 — connect in (needs madbg on your PATH: pipx install madbg)
    madbg connect 127.0.0.1 3513

Then at the `ipdb>` prompt try tab-completion:  order.<TAB>  ·  tot<TAB>

Outbound-only container? Keep this script as-is and bridge with an SSH
reverse tunnel (see docs/completion.md), then `madbg connect localhost 3513`.
"""

import os

import madbg

# Where the target listens for an incoming madbg client.
IP = os.environ.get("MADBG_IP", "127.0.0.1")
PORT = int(os.environ.get("MADBG_PORT", "3513"))


def total_price(order):
    total = sum(item["qty"] * item["price"] for item in order)
    # Blocks here until a `madbg connect` client attaches, then drops into
    # ipdb. (For a long-running daemon you'd use madbg.set_trace_on_connect(),
    # which keeps running and only breaks if/when a client connects.)
    madbg.set_trace(ip=IP, port=PORT)
    return total


def main():
    order = [
        {"name": "widget", "qty": 3, "price": 2.5},
        {"name": "gadget", "qty": 1, "price": 9.0},
    ]
    print(f"waiting for `madbg connect {IP} {PORT}` ...")
    print("total:", total_price(order))


if __name__ == "__main__":
    main()
