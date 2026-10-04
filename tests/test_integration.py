"""End-to-end: a subprocess hits set_trace, we catch it and drive the shell."""

import socket
import subprocess
import sys
import textwrap


TARGET = textwrap.dedent(
    """
    import ripdb
    def work():
        secret = 42
        ripdb.set_trace(host="127.0.0.1", port={port})
        print("RESUMED", secret)
    work()
    """
)


def test_set_trace_roundtrip_and_detach():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, "-c", TARGET.format(port=port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        conn, _ = srv.accept()
        f = conn.makefile("rw", buffering=1, encoding="utf-8")

        banner = f.readline()
        assert banner.startswith("*** ") and "pid=" in banner

        # Inspect a local variable through the reverse shell.
        f.write("p secret\n")
        f.flush()
        # Read until we see the value pdb printed back.
        saw_value = False
        for _ in range(50):
            line = f.readline()
            if not line:
                break
            if "42" in line:
                saw_value = True
                break
        assert saw_value, "did not see 'p secret' output over the socket"

        # Detach: program must continue, not raise BdbQuit.
        f.write("detach\n")
        f.flush()
        conn.close()

        out, _ = proc.communicate(timeout=10)
        assert "RESUMED 42" in out
        assert proc.returncode == 0
    finally:
        srv.close()
        if proc.poll() is None:
            proc.kill()


def test_no_listener_is_noop():
    # Port 1 refuses immediately; set_trace must be a no-op and program exits 0.
    src = "import ripdb; ripdb.set_trace(host='127.0.0.1', port=1); print('OK')"
    out = subprocess.run(
        [sys.executable, "-c", src],
        capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0
    assert "OK" in out.stdout
