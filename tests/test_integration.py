"""End-to-end: with no listener, set_trace is a clean no-op.

The full pty + dot-completion + clean-exit path is covered by test_completion.py.
"""

import subprocess
import sys


def test_no_listener_is_noop():
    # Port 1 refuses immediately; set_trace must be a no-op and the program exits 0.
    src = "import reverse_ipdb; reverse_ipdb.set_trace(host='127.0.0.1', port=1); print('OK')"
    out = subprocess.run(
        [sys.executable, "-c", src],
        capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0
    assert "OK" in out.stdout
