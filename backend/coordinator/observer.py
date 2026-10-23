"""What Refinix's own processes connected to while one piece of work ran.

Observation, not enforcement. Nothing here blocks traffic; it records what
two sources saw during a bounded window, so a Proof Card can say "observed"
with its exact coverage instead of either claiming zero egress or saying
nothing:

* **The coordinator process** — a Python audit hook (`sys.addaudithook`) sees
  every `socket.connect`, `socket.sendto` and name lookup this process makes,
  whichever library makes it. Installed once per process; it only appends to
  a bounded in-memory list and never raises.
* **The Refinix engine process** — its sockets are listed with `psutil` every
  `INTERVAL_SECONDS`. A connection opened and closed between two samples is
  missed, which the coverage note says.

Other programs on the computer, and the operating system itself, are not
observed. A window with an observer error reports itself as such.

Addresses are classified as loopback, local network (private, link-local and
unique-local ranges) or public. Unix-domain sockets are local IPC and are not
network flows.
"""

from __future__ import annotations

import ipaddress
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone

INTERVAL_SECONDS = 0.25
OBSERVER = "Refinix process observer"
COVERAGE_NOTE = (
    "Observed Refinix's own processes only, for the whole window: every "
    "connection the coordinator opened, including other Refinix activity at the "
    "same time such as a model download you started, and the engine's sockets "
    "sampled every 0.25 s, so a very short engine connection can be missed. "
    "Other programs on this computer were not observed, and nothing was "
    "blocked: this is observation, not enforcement.")

_EVENTS: deque = deque(maxlen=20_000)
_EVENTS_LOCK = threading.Lock()
_INSTALLED = False


def _stamp(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify(host) -> str | None:
    """loopback | lan | public for an IP address; None when it is not one."""
    try:
        address = ipaddress.ip_address(str(host).split("%", 1)[0])
    except ValueError:
        return None
    if getattr(address, "ipv4_mapped", None):
        address = address.ipv4_mapped
    if address.is_loopback or address.is_unspecified:
        return "loopback"
    if address.is_private or address.is_link_local:
        return "lan"
    return "public"


def _hook(event: str, args) -> None:
    if event not in ("socket.connect", "socket.sendto", "socket.getaddrinfo"):
        return
    try:
        if event == "socket.getaddrinfo":
            host, port = args[0], args[1]
        else:
            address = args[1]
            if not isinstance(address, tuple):
                return                                     # Unix socket: local IPC
            host, port = address[0], address[1]
        with _EVENTS_LOCK:
            _EVENTS.append((time.monotonic(), event, str(host), port))
    except Exception:                                      # noqa: BLE001
        pass                                               # never disturb the caller


def install() -> None:
    """Start recording this process's connections. Idempotent; cannot be undone."""
    global _INSTALLED
    with _EVENTS_LOCK:
        if _INSTALLED:
            return
        _INSTALLED = True
    sys.addaudithook(_hook)


def installed() -> bool:
    return _INSTALLED


class Window:
    """One bounded observation: `start()`, the work, then `stop()`."""

    def __init__(self, *, node_id: str, engine_pid=None, interval: float = INTERVAL_SECONDS,
                 connections=None):
        self.node_id = node_id
        self.engine_pid = engine_pid or (lambda: None)
        self.interval = interval
        self._connections = connections or _engine_connections
        self._stop = threading.Event()
        self._thread = None
        self._flows: dict[tuple, str] = {}
        self._engine_samples = 0
        self._engine_seen = False
        self._errors = 0
        self._started = self._ended = None
        self._t0 = None

    def start(self) -> "Window":
        install()
        self._started, self._t0 = time.time(), time.monotonic()
        self._thread = threading.Thread(target=self._sample, name="refinix-observer",
                                        daemon=True)
        self._thread.start()
        return self

    def _sample(self) -> None:
        while not self._stop.is_set():
            self._sample_once()
            self._stop.wait(self.interval)
        self._sample_once()

    def _sample_once(self) -> None:
        pid = None
        try:
            pid = self.engine_pid()
        except Exception:                                  # noqa: BLE001
            pid = None
        if pid is None:
            return
        try:
            remotes = self._connections(pid)
        except Exception:                                  # noqa: BLE001
            self._errors += 1
            return
        self._engine_samples += 1
        self._engine_seen = True
        for host, port in remotes:
            kind = classify(host)
            if kind:
                self._flows[("engine", host, port)] = kind

    def stop(self) -> dict:
        """End the window and return what was observed in it."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(5)
        self._ended = time.time()
        t1 = time.monotonic()
        with _EVENTS_LOCK:
            events = [e for e in _EVENTS if self._t0 <= e[0] <= t1]
        lookups = set()
        for _t, event, host, port in events:
            if event == "socket.getaddrinfo":
                if classify(host) is None and host not in ("localhost", ""):
                    lookups.add(host)
                continue
            kind = classify(host)
            if kind:
                self._flows[("coordinator", host, port)] = kind
        counts = {"loopback": 0, "lan": 0, "public": 0}
        for kind in self._flows.values():
            counts[kind] += 1
        interfaces = ["coordinator process sockets"]
        if self._engine_seen:
            interfaces.append("engine process sockets (sampled)")
        return {
            # Whole seconds, rounded outward, so the recorded window always
            # contains the observed one and is never empty.
            "observer": OBSERVER, "started_at": _stamp(int(self._started)),
            "ended_at": _stamp(max(int(self._started) + 1, -int(-self._ended // 1))),
            "node_id": self.node_id, "interfaces": interfaces,
            "public_outbound_flows": counts["public"],
            "trusted_lan_connections": counts["lan"],
            "loopback_connections": counts["loopback"],
            "public_name_lookups": sorted(lookups)[:16],
            "engine_samples": self._engine_samples,
            "observer_errors": self._errors + (0 if installed() else 1),
            "coverage_note": COVERAGE_NOTE,
        }


def _engine_connections(pid: int) -> list[tuple[str, int]]:
    """Remote (host, port) of every inet socket the engine process holds."""
    import psutil
    found = []
    for connection in psutil.Process(pid).net_connections(kind="inet"):
        if connection.raddr:
            found.append((connection.raddr.ip, connection.raddr.port))
    return found
