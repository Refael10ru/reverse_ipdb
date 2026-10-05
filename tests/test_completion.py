"""End-to-end: IPython-over-pty gives real dot-completion, and the target
process exits cleanly after detach (no leaked prompt_toolkit threads)."""

import re
import socket
import subprocess
import sys
import textwrap
import time

TARGET = textwrap.dedent(
    """
    import ripdb
    class Cfg:
        magic_attribute = 1
        another_attr = 2
    def main():
        cfg = Cfg()
        ripdb.set_trace(host="127.0.0.1", port={port})   # pty + IPython (default)
        print("RESUMED")
    main()
    """
)

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[=>]|\x1b\][^\x07]*\x07")


def _recv_until(sock, needle, timeout=15):
    """Accumulate from sock until `needle` appears in the ANSI-stripped text."""
    sock.settimeout(0.3)
    buf = bytearray()
    end = time.time() + timeout
    while time.time() < end:
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        if needle in ANSI.sub("", buf.decode("utf-8", "replace")):
            return buf.decode("utf-8", "replace"), True
    return buf.decode("utf-8", "replace"), False


def test_dot_completion_and_clean_exit():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, "-c", TARGET.format(port=port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        srv.settimeout(15)
        conn, _ = srv.accept()

        # 1) banner must announce pty mode
        banner = bytearray()
        conn.settimeout(10)
        while not banner.endswith(b"\n"):
            b = conn.recv(1)
            if not b:
                break
            banner += b
        assert banner.decode().startswith("*** ripdb/pty"), banner

        # 2) send our terminal size, then wait for the prompt to come up
        conn.sendall(b"80 24\n")
        _, got_prompt = _recv_until(conn, "ipdb>")
        assert got_prompt, "never saw the ipdb> prompt"

        # 3) type a dotted prefix + TAB; completion must resolve the attribute
        conn.sendall(b"cfg.magic\t")
        out, completed = _recv_until(conn, "magic_attribute")
        assert completed, f"TAB did not complete to magic_attribute; saw:\n{out!r}"

        # 4) abort the line and detach, letting the program continue
        conn.sendall(b"\x03")        # Ctrl-C: clear the current input
        time.sleep(0.3)
        conn.sendall(b"detach\r")

        # 5) the program must resume AND the process must exit cleanly
        stdout, _ = proc.communicate(timeout=15)
        assert "RESUMED" in stdout, stdout
        assert proc.returncode == 0, f"exit={proc.returncode}\n{stdout}"
    finally:
        srv.close()
        if proc.poll() is None:
            proc.kill()
