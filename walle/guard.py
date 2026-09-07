"""Cheap, purely-defensive network guard.

Wall-E v1 makes no network calls by design (see agent.yaml notes): it only
reads local files, runs local subprocesses (`jarvis health`,
`git status --porcelain`), and calls stdlib `shutil.disk_usage`. That means
it doesn't need Ultron's real network-lockdown machinery (Ultron actually
opens sockets during binary/firmware analysis and has to actively prevent
exfiltration; Wall-E never opens one in the first place).

This module is a lightweight assertion, not a sandbox: it monkeypatches
`socket.socket.connect` to raise if anything in-process ever tries to open
an outbound connection while the guard is active, so a future contributor
who accidentally adds a network call gets a loud failure instead of a
silent privacy regression. It is intentionally NOT applied globally at
import time -- call `network_guard()` as a context manager around the
`report` command's body (see cli.py) rather than wiring it into every
test/import path.
"""

from __future__ import annotations

import socket
from contextlib import contextmanager


class NetworkCallBlocked(RuntimeError):
    """Raised if code running under `network_guard()` tries to open a
    socket connection. Wall-E v1 has no legitimate reason to do this."""


@contextmanager
def network_guard():
    original_connect = socket.socket.connect

    def _blocked_connect(self, address, *args, **kwargs):  # noqa: ANN001
        raise NetworkCallBlocked(
            f"Wall-E attempted a network connection to {address!r}, but "
            "Wall-E v1 is documented as making zero network calls "
            "(agent.yaml). This guard exists to catch that as a loud "
            "failure rather than a silent privacy regression."
        )

    socket.socket.connect = _blocked_connect  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[assignment]
