"""reverse_ipdb — a reverse-connecting pdb.

``reverse_ipdb.set_trace()`` dials OUT from the target process to a listener you
run, instead of trying to attach a terminal to a process that hasn't got
one (containers, daemons, CI workers).

In the target::

    import reverse_ipdb
    reverse_ipdb.set_trace()                       # uses DEBUG_HOST / DEBUG_PORT
    reverse_ipdb.set_trace(host="10.0.0.5", port=4444)

On your machine::

    python -m reverse_ipdb.serve                   # or: socat STDIO,raw,echo=0 TCP-LISTEN:4444

No listener -> set_trace() is a no-op and the program keeps running.
"""

from reverse_ipdb.api import docker_set_trace, set_trace, set_trace_ipython

__all__ = ["set_trace", "set_trace_ipython", "docker_set_trace"]
__version__ = "0.1.0"
