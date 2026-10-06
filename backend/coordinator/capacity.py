"""Memory budgets for Refinix's own work, and hardware-aware recommendations.

Three facts are kept apart because they behave differently:

* **unified memory** (Apple silicon): one pool shared by the CPU and GPU;
* **discrete GPU**: device memory beside host RAM, with layers offloaded to
  host memory when the device is full;
* **CPU only**: host RAM.

Every number here is an *estimate* unless it came from a runtime's own report
(Ollama's `/api/ps`, a measured preset). Estimates guide recommendations,
routing preference and a bounded admission queue; they are never presented as
measurements, and the only refusal they cause is for a load that is grossly
larger than the computer (`TOO_LARGE`), so a person is not made to wait for
the operating system to fail. Everything else either runs or waits visibly,
and an actual load failure is reported in the runtime's own words.

The reservation table counts Refinix-owned work only, in two parts:

* a **resident** reservation per runtime and model instance, for the weights
  and runtime state of a model being loaded. It is dropped once a fresh
  observation shows the model resident (the observation now accounts for it)
  and is *not* released when a job ends, because a resident model outlives
  the work that loaded it;
* a **per-job** reservation for the working state a request adds when it
  has to load its model, released when that job ends. A resident model's
  state was allocated at load for the window it was loaded with, so only a
  request for that same window adds none; any other window makes the runtime
  reload the model (Ollama on any `num_ctx` change, the Refinix engine on any
  settings change) and allocate that window's state again. Once a fresh
  observation shows the model loaded at a reservation's window, the memory
  reading includes that state too, and the reservation stops counting it.

A request that needs nothing beyond what is already loaded is admitted: there
is no allocation for it to wait for.

One job may use more than one model (a page-reading model, then the model
that writes the answer), each under its own reservation in the job's group.
Its uses of one model are sequential, so they do not add up: only what a new
use needs beyond what the group already holds for that model is reserved.

Fresh readings of available memory include other applications, Ollama's
other clients and models already resident; Refinix observes them and never
manages them.

Standard library only.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

GIB = 1024 ** 3
MIB = 1024 ** 2

UNIFIED, DISCRETE, CPU = "unified", "discrete", "cpu"
GOOD, MARGINAL, TOO_LARGE, UNKNOWN = "good", "marginal", "too_large", "unknown"
FIT_LABELS = {GOOD: "Good fit (estimated)", MARGINAL: "Marginal — may be slow or "
              "need other apps closed (estimated)",
              TOO_LARGE: "Too large for this computer (estimated)",
              UNKNOWN: "Fit unknown — memory could not be read"}

# Runtime buffers beyond the weight files, and a request's growing state.
# Conservative, labelled estimates: a model's file size is not its peak memory
# and no generic attention formula is applied to architectures nobody here
# measured. The measured Qwen3.5-4B managed preset peaked at 4.29 GiB for
# 2.74 GB of weights at an 8192 window (profiles.py), which these bound above.
RESIDENT_FACTOR = 1.15
STATE_FLOOR = 512 * MIB
STATE_FACTOR = 0.25          # of the weights, per 8192-token window
HEADROOM_FRACTION = 0.10
HEADROOM_FLOOR = 1 * GIB
STATE_HEADROOM = 256 * MIB
WAIT_SECONDS = 180.0
POLL_SECONDS = 0.5


def resident_estimate(weights_bytes: int | None) -> int | None:
    if not weights_bytes:
        return None
    return int(weights_bytes * RESIDENT_FACTOR)


def state_estimate(weights_bytes: int | None, window: int) -> int:
    if not weights_bytes:
        return STATE_FLOOR
    return max(STATE_FLOOR, int(weights_bytes * STATE_FACTOR * window / 8192))


def pool(facts: dict | None) -> dict:
    """Which memory a model would use here, from observed hardware facts."""
    facts = facts or {}
    total = facts.get("memory_total_bytes")
    available = facts.get("memory_available_bytes")
    devices = facts.get("engine_devices") or []
    gpu = [d for d in devices
           if str(d.get("id", "")).upper().startswith(("CUDA", "VULKAN"))
           and isinstance(d.get("memory_mib"), (int, float)) and d["memory_mib"] > 0]
    if facts.get("os_family") == "macos" and facts.get("architecture") == "arm64":
        kind, device = UNIFIED, None
    elif gpu:
        kind = DISCRETE
        device = max(int(d["memory_mib"]) * MIB for d in gpu)
    else:
        kind, device = CPU, None
    capacity = None
    if isinstance(total, int):
        capacity = total + (device or 0) if kind == DISCRETE else total
    return {"kind": kind, "host_total_bytes": total if isinstance(total, int) else None,
            "host_available_bytes": available if isinstance(available, int) else None,
            "device_bytes": device, "capacity_bytes": capacity}


def headroom(memory: dict) -> int:
    capacity = memory.get("capacity_bytes") or 0
    return max(HEADROOM_FLOOR, int(capacity * HEADROOM_FRACTION))


def fit(weights_bytes: int | None, memory: dict, *, window: int = 8192) -> str:
    """Recommendation label for a model of this size on this computer."""
    capacity = memory.get("capacity_bytes")
    if not capacity or not weights_bytes:
        return UNKNOWN
    need = (resident_estimate(weights_bytes) or 0) + state_estimate(weights_bytes, window)
    if weights_bytes > capacity * 0.95:
        return TOO_LARGE
    if need <= capacity * 0.75:
        return GOOD
    return MARGINAL if need <= capacity * 0.95 else TOO_LARGE


def grossly_oversized(weights_bytes: int | None, memory: dict) -> bool:
    """The weights alone exceed everything this computer has to hold them."""
    capacity = memory.get("capacity_bytes")
    return bool(capacity and weights_bytes and weights_bytes > capacity)


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------

FIT_ORDER = {GOOD: 0, MARGINAL: 1, UNKNOWN: 2, TOO_LARGE: 3}
HINT_ORDER = ("general", "vision", "code", "reasoning")
INITIAL = 6


def recommend(entries: list, memory: dict, *, free_disk: int | None = None,
              installed: set[str] = frozenset()) -> dict:
    """Up to six starting choices for this computer, then everything else.

    A recommendation is a starting point, not an allowlist: every entry is
    returned, larger ones with a warning, and choosing one is never blocked
    except by an actual disk shortage or an unsupported format.
    """
    rows = []
    for entry in entries:
        weights = entry.weights_bytes()
        label = fit(weights, memory)
        storage = entry.storage_bytes or 0
        disk_short = (free_disk is not None and entry.id not in installed
                      and storage + GIB > free_disk)
        rows.append({"id": entry.id, "fit": label, "fit_label": FIT_LABELS[label],
                     "estimated": True, "disk_short": disk_short,
                     "hints": list(entry.hints), "weights_bytes": weights,
                     "storage_bytes": storage, "installed": entry.id in installed})
    order = sorted(rows, key=lambda r: (FIT_ORDER[r["fit"]], -(r["weights_bytes"] or 0)
                                        if r["fit"] == GOOD else (r["weights_bytes"] or 0),
                                        r["id"]))
    initial, used = [], set()
    for hint in HINT_ORDER:
        pick = next((r for r in order if r["id"] not in used and hint in r["hints"]
                     and r["fit"] in (GOOD, MARGINAL)), None)
        if pick is not None:
            initial.append(pick)
            used.add(pick["id"])
    for row in order:
        if len(initial) >= INITIAL:
            break
        if row["id"] not in used and row["fit"] != TOO_LARGE:
            initial.append(row)
            used.add(row["id"])
    initial = initial[:INITIAL]
    more = [row for row in order if row["id"] not in used]
    return {"initial": initial, "more": more, "memory": memory,
            "note": ("Recommendations use this computer's memory and each model's "
                     "published size. They are estimates, not measurements; you "
                     "can choose any model, including larger ones.")}


# --------------------------------------------------------------------------
# The reservation table
# --------------------------------------------------------------------------

@dataclass
class Reservation:
    job_id: str
    key: str
    origin: str
    resident_bytes: int          # 0 when the model was already resident
    state_bytes: int
    group: str = ""              # the job this use belongs to
    window: int = 0              # the context window the state is for
    created: float = field(default_factory=time.monotonic)


@dataclass
class Decision:
    outcome: str                 # admit | wait | refuse
    reason: str
    need_bytes: int | None = None
    free_bytes: int | None = None
    estimated: bool = True


class Ledger:
    """Refinix-owned memory decisions, made one at a time across both runtimes."""

    def __init__(self, *, observe=None, clock=time.monotonic, sleep=time.sleep):
        self._lock = threading.Lock()
        self._reservations: dict[str, Reservation] = {}
        self._observe = observe or (lambda: None)     # () -> available bytes | None
        self._clock = clock
        self._sleep = sleep

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [vars(r).copy() for r in self._reservations.values()]

    def mark_resident(self, loaded) -> None:
        """A fresh observation shows these models resident: it now counts them.

        `loaded` maps each key to the window its loaded instance holds (None
        when not reported). The weights are counted by the observation from
        now on; so is the working state of a reservation for that same
        window. A set of keys marks the weights only.
        """
        windows = loaded if isinstance(loaded, dict) else dict.fromkeys(loaded)
        with self._lock:
            for item in self._reservations.values():
                if item.key in windows:
                    item.resident_bytes = 0
                    if windows[item.key] is not None and windows[item.key] == item.window:
                        item.state_bytes = 0

    def release(self, job_id: str) -> None:
        with self._lock:
            self._reservations.pop(job_id, None)

    def release_group(self, group: str) -> None:
        """Everything one job holds, whatever models it used."""
        with self._lock:
            for job_id in [k for k, r in self._reservations.items()
                           if k == group or r.group == group]:
                del self._reservations[job_id]

    def _pending(self) -> int:
        return sum(r.resident_bytes + r.state_bytes for r in self._reservations.values())

    def decide(self, *, job_id: str, key: str, origin: str, weights_bytes: int | None,
               window: int, resident: bool, memory: dict,
               loaded_window: int | None = None, group: str | None = None,
               enforce_wait: bool = True) -> Decision:
        """One admission decision, atomic with every other Refinix decision.

        `resident` means a fresh observation already shows the model loaded;
        `loaded_window` is the window that loaded instance holds, when the
        runtime reports it. `group` names the job this use belongs to (the
        reservation's own id when omitted). `enforce_wait` is False for
        Ollama, whose own scheduler queues and offloads: its reservation is
        still recorded so a Refinix-engine load decided at the same moment
        cannot spend the same memory.
        """
        if grossly_oversized(weights_bytes, memory):
            return Decision("refuse", (
                f"This model's files alone (about {weights_bytes / GIB:.1f} GB) are "
                f"larger than this computer's memory for models (about "
                f"{memory['capacity_bytes'] / GIB:.1f} GB, estimated), so it was not "
                "loaded. A smaller or more compressed version may fit."),
                weights_bytes, memory.get("capacity_bytes"))
        # Both runtimes allocate a loaded model's context state when it loads
        # (a fixed window per slot), so a request for the window a resident
        # model already holds adds no new working memory. Any other window, or
        # one the runtime did not report, reloads it: the same mapped weights,
        # but that window's working state again. Loading a model that is not
        # resident needs its weights' room and its working state.
        holds_window = resident and loaded_window == window
        resident_need = 0 if resident else (resident_estimate(weights_bytes) or 0)
        state_need = 0 if holds_window else state_estimate(weights_bytes, window)
        group = group or job_id
        with self._lock:
            held = [r for r in self._reservations.values()
                    if r.group == group and r.key == key and r.job_id != job_id]
            if held:
                resident_need = max(0, resident_need - max(r.resident_bytes for r in held))
                state_need = max(0, state_need - max(r.state_bytes for r in held))
            need = resident_need + state_need
            available = self._observe()
            if available is None:
                available = memory.get("host_available_bytes")
            pending_resident = sum(r.resident_bytes for r in self._reservations.values())
            pending_state = sum(r.state_bytes for r in self._reservations.values())
            # Both runtimes memory-map model weights: file-backed pages the
            # operating system can reclaim, so they are bounded by the total
            # this computer has for models, not by what is free this instant.
            # What must be free now is a request's working state.
            capacity_ = memory.get("capacity_bytes")
            weights_room = (None if not capacity_ else
                            capacity_ - pending_resident - headroom(memory))
            if available is None:
                self._reservations[job_id] = Reservation(job_id, key, origin,
                                                         resident_need, state_need, group,
                                                         window)
                return Decision("admit", "Available memory could not be read; "
                                "the runtime will report a real shortfall.", need, None)
            free = available - pending_state - STATE_HEADROOM
            # Nothing new to allocate is never a reason to wait, however the
            # readings and reservations happen to add up.
            fits = need == 0 or (
                state_need <= free
                and (weights_room is None or resident_need <= weights_room))
            if fits or not enforce_wait:
                self._reservations[job_id] = Reservation(job_id, key, origin,
                                                         resident_need, state_need, group,
                                                         window)
                return Decision("admit", "", need, free)
            if weights_room is not None and resident_need > weights_room:
                why = (f"Waiting for memory: loading this model needs about "
                       f"{resident_need / GIB:.1f} GB beside models Refinix is already "
                       "loading (estimated).")
            else:
                why = (f"Waiting for memory: this request needs about "
                       f"{state_need / GIB:.1f} GB of working memory and about "
                       f"{max(free, 0) / GIB:.1f} GB is free (estimated).")
            return Decision("wait", why, need, free)

    def acquire(self, *, should_cancel=None, timeout: float = WAIT_SECONDS,
                refresh=None, **kwargs) -> Decision:
        """`decide`, waiting a bounded time while the answer is `wait`.

        `refresh`, when given, re-reads whether the model is loaded, and with
        which window, before each retry: another job may load it while this
        one waits, and a decision kept on the first reading would wait for
        memory the loaded model no longer needs.
        """
        deadline = self._clock() + timeout
        while True:
            decision = self.decide(**kwargs)
            if decision.outcome != "wait":
                return decision
            if should_cancel is not None and should_cancel():
                return Decision("cancelled", "cancelled while waiting for memory")
            if self._clock() >= deadline:
                return Decision("refuse", decision.reason.replace(
                    "Waiting for memory", "Not enough free memory") +
                    " Close other apps or wait for running work to finish, then try "
                    "again.", decision.need_bytes, decision.free_bytes)
            self._sleep(POLL_SECONDS)
            fresh = None
            if refresh is not None:
                try:
                    fresh = refresh()
                except Exception:                          # noqa: BLE001
                    fresh = None
            if fresh:
                kwargs.update(resident=bool(fresh.get("resident")),
                              loaded_window=fresh.get("loaded_window"))
                if fresh.get("resident"):
                    self.mark_resident({kwargs["key"]: fresh.get("loaded_window")})
