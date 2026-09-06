# Device Specifications — AegisForge / Refinix — Team Rokunin Sync

Hardware inventory for the six team devices, collected for **model selection and
capability-pack assignment**. This document is the team's reference for what the
fleet actually is; [model-catalog.md](model-catalog.md) owns model and pack
policy.

- **Collected:** 2026-09-01; Vedant's device re-measured 2026-09-02; all six devices supplied read-only inventory on 2026-09-03 (dates to be confirmed).
- **Status:** All six people supplied inventory, though with incomplete fields. Later C02 output records versions, native inference and model integrity for the macOS coordinator and Ubuntu worker. Tool paths alone on other devices do not prove readiness; no Kubernetes runtime gate has passed.
- **Rule:** treat every capability and model note below as a **hypothesis** until
  benchmarked on the actual device under
  [evaluation.md](evaluation.md#5-measurement-plan).

---

## First configuration — the only two devices on the critical path

Execution identifies human actions by **device role**, never by team member.
The first configuration uses two of the six inventoried machines:

| Device role | Machine in this inventory | Role |
|---|---|---|
| **macOS coordinator** | MacBook Air `Mac17,3`, macOS 26.6.2 (25G83), arm64 | Primary workspace and UI, canonical state, approvals, local main-engine inference |
| **Ubuntu worker** | HP Victus, Ubuntu 24.04.4 LTS, x86_64 | Candidate single-node K3s host, worker image build, Redis, sandboxed code execution |

The four Windows machines remain **off the critical path**. Add an execution
device only for a measured need with a new device-based setup checkpoint;
Windows execution support remains unverified. OCR belongs to C08 on the
Mac/Ubuntu configuration, not to a separate required device. Any Windows
machine may still build any module. The retained
[qualification script](../scripts/qualify-ocr-worker.ps1) is deferred; it is
not a C07 prerequisite. See [tasks.md](../tasks.md#numbered-execution-tasks).

> **Reading VRAM correctly.** `systeminfo`, `Get-ComputerInfo`, and
> `Win32_VideoController.AdapterRAM` report GPU memory through a 32-bit field
> that saturates at 4 GB, so any card with more than 4 GB reports as 4 GB and
> shared-memory iGPUs report as 2 GB. This is confirmed across three machines in
> this fleet: an 8 GB card and a 6 GB card both reported 4 GB. Read VRAM with
> `nvidia-smi`, or from the GPU's own product name, never from `systeminfo`.

---

## Summary table

| Member | Machine | OS | CPU | Cores/Threads | RAM | Dedicated GPU | GPU VRAM | Storage (free / total) |
|---|---|---|---|---|---|---|---|---|
| Aditya | MacBook Air (M5, 13″, 2026) | macOS 26.6.2 (build 25G83) | Apple M5 (Mac17,3) | 10C (4P+6E) / 10 | 16 GiB unified _(measured)_ | — (8- or 10-core Apple GPU; confirm locally) | shared (unified) | /: 340 GiB free / 460 GiB _(measured)_ |
| Sahil | Lenovo LOQ 15IRX9 (83DV) | Windows 11 Home SL (26200) | Intel Core i5-13450HX | 10C (6P+4E) / 16 | ~24 GB (25463480320 bytes) _(measured)_ | NVIDIA GeForce RTX 3050 6GB Laptop GPU | **6144 MiB** _(measured)_ | C: ~54.7 GB free / 162.8 GB used. D: ~287 GB free / 4.6 GB used _(measured)_ |
| Vedant | ASUS V16 (V3607VH) | Windows 11 Home SL (26200) | Intel Core 7 240H | 10C / 16 | ~16 GB (16763662336 bytes) _(measured)_ | NVIDIA GeForce RTX 5 [truncated in output] | **8 GB** _(historical)_ | C: ~42.9 GB free / 467.5 GB used _(measured)_ |
| Yug | HP Victus 15-fa1xxx | Windows 11 Home SL (26200) | Intel Core i5-12450H | 8C / 12 | ~16.8 GB (16802910208 bytes) _(measured)_ | NVIDIA RTX 2050 _(historical)_ | 4 GB _(historical)_ | C: 14.2 GB free / 363.7 GB used. D: ~276 GB free / 43.3 GB used _(measured)_ |
| Prachi | HP Victus 15-fa1xxx | Ubuntu 24.04.4 LTS (Noble) | Intel Core i5-13420H | 8C / 12 | 15 GiB _(measured)_ | NVIDIA GeForce RTX 2050 | **4096 MiB** _(measured)_ | /: 115G free / 246G total _(measured)_ |
| Tanvi | Dell Inspiron 15 3520 | Windows 11 Home SL (26200) | Intel Core i5-1235U | 10C (2P+8E) / 12 | ~16.8 GB (16849293312 bytes) _(measured)_ | — (Intel Iris Xe iGPU only) | — | C: ~22.1 GB free / 213 GB used. D: ~125.7 GB free. E: ~125.7 GB free _(measured)_ |


**Fleet at a glance:** 1 × macOS (Apple Silicon), 4 × Windows, 1 × Linux.
Four machines have a dedicated NVIDIA GPU. VRAM ranks **Vedant 8 GB (historical) → Sahil
6 GB (measured) → Yug and Prachi 4 GB each (measured on Prachi)**. Vedant's recent output was truncated ("NVIDIA GeForce RTX 5"), which does not reconfirm his GPU; the 8 GB measurement is retained as historical evidence. Yug's missing `nvidia-smi` output does not establish that he lacks a GPU. Two machines are iGPU or CPU-only (Tanvi, and the Mac's unified-memory GPU).

**No machine exceeds 8 GB discrete VRAM, and only one reaches it.** Plan the
whole catalogue around **≤8 GB VRAM, Q4 quantization, and bounded context**.

**Wired networking:** Ethernet is present on Yug, Prachi, and Sahil (Sahil's is
currently unplugged). Vedant has no Ethernet adapter at all, the MacBook Air has
no Ethernet port, and Tanvi's is unconfirmed. A wired demo needs USB-Ethernet
adapters for at least the Mac and Vedant.

---

## Per-device detail

### Aditya — MacBook Air (M5, 13-inch, 2026) — primary alpha workspace
- **SoC:** Apple M5 — 10-core CPU (4 performance + 6 efficiency), 8- or
  10-core GPU configuration **to confirm locally**, 16-core Neural Engine
- **Unified memory:** 16 GB, bandwidth **153 GB/s** (shared across CPU/GPU/NE)
- **Storage:** 512 GB SSD (soldered)
- **OS:** macOS 26.6.2 (build 25G83)
- **Runtime fit:** MLX (native Apple Silicon) or Ollama/llama.cpp with Metal
- **Network:** Wi-Fi only; the Air has no Ethernet port (USB-C adapter needed)
- **Installed runtimes** _(initial snapshot, 2026-09-03, before inference)_:
  Homebrew `python3` **3.14.6** at `/opt/homebrew/bin/python3`; Docker CLI
  **29.7.2** with the **daemon not running** (`desktop-linux` context socket
  absent); `kubectl` client **v1.36.1** (`darwin/arm64`, kustomize v5.8.1) with
  **no cluster contacted**; Ollama client **0.32.14**, initially with its server
  stopped; no `k3s`, `llama-cli` or `llama-server` on `PATH`. The inventory's
  `ollama list` subsequently launched the app; the later measurement observed
  its server listening on `127.0.0.1:11434`.
- **Later C02 direct-engine check:** the installed Ollama bundle contains
  `/Applications/Ollama.app/Contents/Resources/llama-server`, despite no binary
  on `PATH`. Its version is `0.1.0-dev`, build 1, commit `7e4c0a968`.
  The requester ran the bounded comparison and reported stopping the temporary
  server with Ctrl+C; no additional runtime was installed. See
  [the binary fingerprint and results](evaluation.md#measured--bundled-engine-on-the-macos-coordinator-2026-09-03).
- **Installed model** _(measured 2026-09-03)_: one artifact in
  `~/.ollama/models` — `qwen3.5:4b-q4_K_M`, GGUF, `Q4_K_M`, `model_type` 4.7B,
  Apache-2.0 licence layer, 3,389,971,840 B weights (3.2 GB store total),
  pulled 2026-08-08 from `registry.ollama.ai/library/qwen3.5`. All four blobs
  re-hashed on this device and matched their content-addressed SHA-256 names.
  Integrity verified. Bounded `/api/chat` inference was subsequently measured
  on this device on 2026-09-03; see
  [the recorded timings and response hash](evaluation.md#51-od-03-runtime-comparison).
  Output quality remains unverified; Ubuntu's later native inference is
  recorded in its device entry below.
- **Planning note:** This is the planned **primary workspace + UI** for the
  alpha, not a permanent installation role. The dynamic node model is in
  [architecture.md](architecture.md#2-installation-and-runtime-responsibilities).
  Unified memory means model weights, KV cache, and the OS all share 16 GB —
  budget conservatively (a Q4 4B model is roughly 3–4 GB, leaving headroom for
  embeddings and the app). Good home for the **core chat/agent model** and
  **local embeddings/RAG**; not for a 9B+ model at usable speed. Apple's
  GPU-core count is not measured on this device.

### Sahil — Lenovo LOQ 15IRX9 (model 83DV)
- **CPU:** 13th Gen Intel Core i5-13450HX — 10 cores (6P+4E) / 16 threads, 2.4 GHz base
- **RAM:** **24 GB DDR5-4800, dual-channel** — 2 × 12 GB Ramaxel RMSB3400KB06IVF-4800 (Controller0 + Controller1). **Most RAM and the widest memory bus in the fleet.**
- **GPU (discrete):** **NVIDIA GeForce RTX 3050 6GB Laptop GPU — 6144 MiB VRAM** (measured via `nvidia-smi`), driver 581.86.
- **GPU (integrated):** Intel UHD Graphics (RaptorLake-S Mobile), driver 32.0.101.7026
- **Storage:** C: drive ~54.7 GB free / 162.8 GB used. D: drive ~287 GB free / 4.6 GB used.
- **Installed runtimes:** paths for python.exe (`Program Files\Python313`) and py.exe found. Python3 path points to a `WindowsApps` alias. Runtime/container tools (Docker, kubectl, Ollama) were not found by the C01 probe.
- **Motherboard / BIOS:** Lenovo LNVNB161216 (SDK0T76485 WIN); BIOS NECN34WW (2024-04-10)
- **OS:** Windows 11 Home Single Language (build 26200); VBS and HVCI running
- **Display:** 1920 × 1080 @ 60 Hz
- **Network:** Intel Wi-Fi 6 AX203 (585 Mbps, connected) **+ Realtek PCIe GbE Ethernet (present, currently unplugged)** → wired-capable
- **Planning note:** Second-highest VRAM at 6 GB, but the **best CPU-offload host
  in the fleet** — 24 GB of dual-channel DDR5 gives it roughly double the
  effective memory bandwidth of Vedant's single-channel 16 GB when layers spill
  out of VRAM. That makes it the natural home for a **larger model running
  partly on CPU**, or a reasoning pack, rather than competing for the pure-VRAM
  coding role.
- **Flag:** `systeminfo` reports **App Control for Business policy: Enforced**
  (Smart App Control). This can block unsigned binaries, which may prevent
  llama.cpp or an Ollama install from running. **Verify before assigning a
  runtime to this node.**

### Vedant — ASUS V16 (V3607VH) — measured directly, 2026-09-01
- **CPU:** Intel Core 7 240H — 10 cores / 16 threads, 2.5 GHz base
- **RAM:** 16 GB DDR5-5600 (single SK Hynix DIMM — **single-channel**; second slot free)
- **GPU (discrete):** Truncated in output to "NVIDIA GeForce RTX 5". The previous 8 GB measurement is retained as historical evidence.
- **GPU (integrated):** Intel Graphics, shares system memory dynamically
- **Storage:** C: drive ~42.9 GB free / 467.5 GB used _(measured)_.
- **OS:** Windows 11 Home Single Language (build 26200), VBS/Hyper-V active
- **Display:** 1920 × 1200 @ 144 Hz
- **Network:** **Wi-Fi only** — Realtek 8852BE Wi-Fi 6 at 866 Mbps. Confirmed to have **no Ethernet adapter at all** (only Wi-Fi and Bluetooth PAN present).
- **Planning note:** **The only 8 GB GPU in the fleet**, and enough to hold a
  **7B-Q4 coding model almost entirely on-GPU** — the decisive advantage for the
  coding-worker role. Two caveats: single-channel DDR5 limits memory bandwidth,
  so anything that spills to CPU runs slower than the spec sheet suggests
  (populating the free DIMM slot would improve this), and temporary workspaces
  plus model caches still need reserved disk headroom. Only **43 GB is free**,
  which fits the selected model set (~9 GB) but leaves little margin once a WSL2
  virtual disk and container images are added, so clear space before
  provisioning. Needs a USB-Ethernet adapter for a wired demo.
- **Installed runtimes** _(measured)_: paths for Docker and kubectl were found. The python and python3 paths are Microsoft Store aliases (`WindowsApps`), which do not prove a usable interpreter is installed. WSL2 carries both an **Ubuntu** and a `docker-desktop` distro (historical note).
  Ubuntu distro means this machine can host the network-disabled sandbox through
  Docker Engine inside WSL2 without Docker Desktop. No `.wslconfig` exists, so
  WSL2 may claim up to half of system RAM and starve a local model runtime.

### Yug — HP Victus 15-fa1xxx
- **CPU:** Intel Core i5-12450H — 8 cores / 12 threads
- **RAM:** ~16.8 GB _(measured)_
- **GPU (discrete):** NVIDIA RTX 2050, 4 GB reported _(historical)_. **Missing `nvidia-smi` output** (this does not establish that he lacks a GPU).
- **Storage:** C: drive 14.2 GB free / 363.7 GB used. D: drive ~276 GB free / 43.3 GB used. E: drive ~196 GB free.
- **OS:** Windows 11 Home Single Language (build 26200)
- **Network:** Wi-Fi 6E (Intel AX211) + **Realtek Gigabit Ethernet** (wired LAN capable)
- **Installed runtimes:** paths for python.exe (`Python313`), py.exe, Docker, kubectl, and Ollama were found. Python3 path points to a `WindowsApps` alias.
- **Planning note:** **Flag:** Very limited space on C: (14.2 GB). The D: drive has 276 GB free, identifying it as a possible storage destination requiring confirmation, not an instruction to move anything. Ethernet makes it reliable for the wired demo.

### Prachi — HP Victus 15-fa1xxx (Linux)
- **CPU:** Intel Core i5-13420H — 8 cores / 12 threads (Raptor Lake)
- **RAM:** 15 GiB total; 8.8 GiB available in the later C02 snapshot
  (9.5 GiB in the earlier snapshot); 4 GiB swap, unused _(measured)_
- **GPU (discrete):** NVIDIA GeForce RTX 2050, **4096 MiB VRAM** _(measured via `nvidia-smi`)_, driver **580.173.02**. (Supersedes the old "NVIDIA driver not loaded" note. A responding host driver still does not establish GPU access inside Kubernetes; that requires separate configuration and verification).
- **GPU (integrated):** Intel UHD (i915), drives the display
- **Storage:** /: **115G free**, 118G used / 246G total _(measured)_
- **OS:** Ubuntu 24.04.4 LTS, GNOME 46; kernel `7.0.0-30-generic`, x86_64
- **Network:** Wi-Fi selected; `wlo1` UP, `eno1` DOWN. The requester confirmed
  availability and intended membership of the trusted LAN; actual connectivity
  and pairing remain untested.
- **Directory / privileges:** `~/SIH/AegisForge` (`/home/prachi/SIH/AegisForge`),
  bash; account belongs to `sudo`, `docker` and `ollama` groups. The requester
  reports that sudo requires a password; no privilege change was made.
- **Python:** `/usr/bin/python3` **3.12.3**, `/usr/bin/pip3`. System-interpreter
  metadata reports `typing-extensions==4.10.0`; Pydantic, pydantic-core,
  annotated-types and typing-inspection are not installed there. This is not a
  repository-venv check; no host dependency install is needed for the stdlib
  measurement. Worker dependencies belong to the pinned C04 image.
- **Docker:** `/usr/local/bin/docker` **29.6.1**, build `8900f1d`; local daemon
  active/enabled, root:docker socket accessible. Local `info`: **29.6.1**,
  **overlayfs**, cgroup **2**, **x86_64**. Existing Docker networks remain in use.
- **Ollama:** `/usr/local/bin/ollama`, client/server **0.33.2**, active and
  listening on `127.0.0.1:11434`. No allowlisted service settings were returned;
  that is not proof the unit has no other settings. Existing `qwen3:4b` occupied
  a 2.4G store before the selected `qwen3.5:4b-q4_K_M` was downloaded. Both use
  `/usr/share/ollama/.ollama/models`. The returned manifest and four blob checks
  all reported `OK`; the manifest digest matches the
  [catalogue](model-catalog.md#31-od-05--the-first-selected-model-set).
- **Native inference:** four recorded requests completed; cold TTFT **16.0149 s**,
  warm median **0.3369 s**, **10.14 tok/s**. Benchmark GPU output names the runner
  `/usr/local/lib/ollama/llama-server`; follow-up `ps` reports runner RSS
  **2157.4 MiB** and daemon RSS **54.7 MiB**. This corrects the script's misleading
  `rss_mb: 69.7`. See [timings and memory limits](evaluation.md#measured--ollama-on-the-ubuntu-worker-2026-09-03).
- **Kubernetes / GPU containers:** `/snap/bin/kubectl` **v1.36.3**, kustomize
  **v5.8.1**; no `k3s` on PATH, service inactive. Driver package
  `nvidia-driver-580-open` **580.173.02-0ubuntu0.24.04.1**, GPU compute capability
  **8.6**. No `nvidia-ctk` or NVIDIA container package was detected. Native
  inference works; GPU access in a container and cluster readiness are unverified.
- **Ports:** snapshot showed `127.0.0.1:11434`; no TCP listener observed on
  contract ports **8443/30443**. A future bind and Kubernetes forwarding still
  require the C05 check.
- **C02 open item — wildcard listener:** the same snapshot showed `*:8080`,
  with no identified owner or purpose. This is a non-loopback bind; actual LAN
  reachability was not tested. The Ubuntu worker operator must identify the
  process and intended exposure before enabling worker LAN access or reusing
  port 8080 for a direct-engine comparison. Do not stop an unidentified service.
  This item is separate from C05's contract-port and forwarding checks.
- **Planning note:** The only Linux box, making it the **alpha single-node K3s host and sandboxed code-execution worker** under
  [security.md](security.md#8-filesystem-and-sandbox).
  The mentor-aligned baseline uses Docker to build pinned images and K3s to run
  the worker, Redis, and validation Pods. The cluster and sandbox roles do not
  require a GPU. **Action:** add `nvidia-container-toolkit` only when passing the GPU into a container.

### Tanvi — Dell Inspiron 15 3520
- **CPU:** 12th Gen Intel Core i5-1235U (U-series, low-power) — 10 cores (2P+8E) / 12 threads, 1.3 GHz base
- **RAM:** 16 GB (15.69 GB usable)
- **GPU:** **Intel Iris Xe Graphics only — no discrete GPU confirmed**, so CPU inference only
- **Storage:** C: drive ~22.1 GB free / 213 GB used. D: drive ~125.7 GB free. E: drive ~125.7 GB free.
- **OS:** Windows 11 Home Single Language (build 26200)
- **Network:** Realtek 8821CE 802.11ac (Wi-Fi 5) at 433.3 Mbps.
- **Installed runtimes:** paths for python.exe (`Python314`), py.exe, and Ollama found. Python3 path points to a `WindowsApps` alias.
- **Planning note:** Lowest inference capability in the fleet — a 15 W U-series
  CPU with a 1.3 GHz base and no dGPU. Best used for **CPU-friendly light
  tasks**: small chat, ASR/voice, a retrieval/embeddings host, or a standby
  coordinator. The slow Wi-Fi link also makes it a poor choice for any role that
  ships large context or files across the network.

---

## Tentative capability-pack mapping (hypothesis — off the critical path)

Nothing in this table is part of the first configuration. It records which
machine *might* suit a future pack once one is measured; it assigns no work, no
download and no checkpoint. Read it after
[First configuration](#first-configuration--the-only-two-devices-on-the-critical-path).

| Capability pack ([model-catalog.md](model-catalog.md#2-baseline-and-conditional-packs)) | Best-fit device | Why |
|---|---|---|
| Main engine + primary alpha workspace | Aditya (M5 Air) | MLX and unified memory may suit a small main model; the app may still use this or paired compute |
| Coding worker | **Vedant (RTX 5050, 8 GB)** | The only 8 GB GPU; holds a 7B-Q4 coding model almost entirely in VRAM |
| Reasoning / large-model worker | **Sahil (RTX 3050 6 GB + 24 GB dual-channel)** | Best CPU-offload host in the fleet; runs a larger model partly on CPU without collapsing |
| Kubernetes worker, Redis, and code sandbox | Prachi (Ubuntu + Docker/K3s) | Single Linux host for the mentor-aligned Pods, Services, Redis, NetworkPolicies, and validation Jobs; no GPU required for the first spine |
| OCR / vision worker | Yug (RTX 2050, 1 TB) | 4 GB VRAM fits a small OCR/vision model; most disk, and has Ethernet |
| Embeddings / RAG | Aditya (coordinator) or Tanvi | Small footprint; can run alongside chat or CPU-only |
| ASR / voice (optional) | Tanvi (CPU) | A small ASR model runs acceptably on CPU; suits the weakest node |

Constraint reminder: **no device exceeds 8 GB discrete VRAM.** Plan every model as
**Q4, bounded context, task-specific output limits** under
[model-catalog.md](model-catalog.md#9-hardware-policy). Do not rely on advertised
128K context windows without local quality and memory tests.

---

## Still needed before final model placement

These are human actions, not permanent coding assignments. The
[shared checkpoint plan](../tasks.md#numbered-execution-tasks) owns when
execution stops and resumes. Existing measurements above keep their original
dates. Do not treat a planned placement as runtime proof.

**C02 closeout:** environment evidence and bounded native inference have been
returned for both devices. The requester selected Wi-Fi and confirmed the
Ubuntu worker's availability, trusted-LAN participation and passworded sudo.
Controlled cold-start and Ubuntu direct-engine comparisons were explicitly
deferred on 2026-09-03; Ollama remains selected. C01/C02 were accepted on
2026-09-04. The Ubuntu `*:8080` listener was identified as Jenkins and stays
untouched. Its exposure review remains open before worker LAN access; it does
not invalidate the recorded loopback inference. Apple GPU-core count remains
an inventory gap without blocking the observed native path. Actual LAN
connectivity and pairing are later gates.

**Off the critical path — do not action unless a measured need selects the
device:**

Windows machines: no model download or inference installation is assigned.
The truncated `RTX 5…` GPU line and the missing `nvidia-smi` output are
recorded gaps, not blockers. If evidence later selects one of these machines,
the next handoff names that device and supplies the exact approved
instructions, including a storage destination where free space is tight.

Note: Ollama appearing on four machines is inventory, not a runtime-selection
decision. The Ubuntu worker's NVIDIA driver responds, so no driver reinstall is
assumed and the full CUDA Toolkit is **not** required unless the selected
runtime or build actually needs it. Any future dependency must follow the chosen
runtime's real requirements.

## Checkpoint C01: read-only inventory

Use the following on the named person's **own machine**, from any directory,
when C01 requests the inventory. These commands read local metadata; they do not
install tools, start services, change permissions or download models. Do not
add `sudo`, elevate PowerShell or install a missing command to finish this list.
A missing tool or permission error is useful evidence to return.

### Aditya — macOS Terminal, zsh

```sh
sw_vers
uname -m
sysctl hw.model hw.memsize
df -h /
command -v python3 docker kubectl k3s ollama llama-cli
```

### Yug, Sahil, Vedant and Tanvi — Windows PowerShell

Each person runs this block on their own Windows machine:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-CimInstance Win32_Processor | Select-Object Name
Get-PSDrive -PSProvider FileSystem | Select-Object Name, Used, Free
Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, LinkSpeed
Get-Command python, python3, py, docker, kubectl, ollama, llama-cli -ErrorAction SilentlyContinue | Select-Object Name, Source
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
}
```

A Python entry under `WindowsApps` can be a Microsoft Store alias. Report it as
such; this command list does not prove that a usable interpreter is installed.
Tanvi need not have `nvidia-smi`; absence is expected without an NVIDIA GPU.

### Prachi — Ubuntu Terminal, bash

```sh
cat /etc/os-release
uname -srmo
free -h
df -h /
command -v python3 docker k3s kubectl ollama llama-cli nvidia-smi
if command -v nvidia-smi >/dev/null 2>&1
then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
fi
```

### What each person returns

Send the outputs to their agent or Aditya with the collection date and their
name. Also state: machine availability, installed runtime/model versions already
known from local records or the application's About screen, whether Docker is
already running, and intended Wi-Fi/Ethernet availability. Mark unknown values
as unknown. Do not include credentials, tokens, full environment dumps or
private documents. Terminal metadata and an installed binary path alone do not
prove that a model or container can run.

The next checkpoint will supply reviewed installation/startup/self-test commands
for the actual chosen versions and paths. Do not substitute guessed commands,
unpinned downloads or policy bypasses for a missing prerequisite.

## Checkpoint C02: read-only environment evidence

C01 established *what the machines are*. C02 needs *what is actually installed
and running* on the two critical-path devices only. These commands read local
state. They do not install, download, deploy, elevate, change host settings, or
**start a stopped service** — a stopped service is a valid answer, and the point
of asking is to record it rather than change it.

Throughout, keep four states apart:

| State | What proves it |
|---|---|
| **Executable present** | a path on `PATH` |
| **CLI version** | the binary's own `--version` |
| **Server available** | a process listening on its port, or the service reported active |
| **Successful inference** | a real bounded request that returns tokens |

An earlier state never implies a later one. A path proves nothing about a
running server; a running server proves nothing about a working model.

> **Do not use the Ollama CLI to take inventory.** Fourteen of its
> subcommands — `list`, `ps`, `show`, `run`, `pull`, `stop`, `cp`, `create`,
> `rm`, `push`, `login`, `logout`, `signin`, `signout` — attach
> `PreRunE: checkServerHeartbeat`, which calls `startApp` when the connection is
> refused. **`ollama list` therefore starts a stopped Ollama.** It did exactly
> that on the coordinator on 2026-09-03. Only the root command (`ollama
> --version`) and `serve` skip the heartbeat, so `--version` is safe: it reports
> the client version and warns instead of starting anything. Take model
> inventory from the filesystem and server state from a listening socket.
> Source: [`cmd/cmd.go` at v0.32.14](https://github.com/ollama/ollama/blob/v0.32.14/cmd/cmd.go).

### macOS coordinator — Terminal, zsh, any directory

Already collected on 2026-09-03 and recorded above. Reproduce with:

```sh
sw_vers; uname -m; sysctl -n hw.model hw.memsize hw.ncpu
df -h /
command -v python3 docker kubectl k3s ollama llama-cli llama-server
python3 --version
docker --version; docker context ls; docker info --format '{{.ServerVersion}}'
kubectl version --client -o yaml
ollama --version                     # root command: no heartbeat, cannot start the app
lsof -nP -iTCP:11434 -sTCP:LISTEN || echo "ollama server not listening"
curl -sS --max-time 3 http://127.0.0.1:11434/api/version || echo "no server to query"
du -sh ~/.ollama/models
find ~/.ollama/models/manifests -type f
cd ~/.ollama/models/blobs && for f in sha256-*; do
  printf '%s %s\n' "$(openssl dgst -sha256 -r "$f" | awk '{print $1}')" "${f#sha256-}"
done
```

### Ubuntu worker — Terminal, bash, any directory (no `sudo`)

Run each block and return its output verbatim. If a command is missing or
refuses, that output *is* the evidence — do not install anything to complete it.

```sh
# 1. Identity, privileges and capacity
pwd
id; groups; uname -srmo
cat /etc/os-release
free -h
df -h / /var /home 2>/dev/null

# 2. Python interpreter and the AF-001 pinned dependencies
command -v python3 pip3
python3 -VV
python3 - <<'PY'
import importlib.metadata as md
for name in ("pydantic","pydantic-core","annotated-types",
             "typing-extensions","typing-inspection"):
    try:
        print(f"{name}=={md.version(name)}")
    except md.PackageNotFoundError:
        print(f"{name}: not installed")
PY

# 3. Docker — endpoint and daemon status, without starting it
command -v docker
docker --version
systemctl is-active docker; systemctl is-enabled docker
ls -l /var/run/docker.sock 2>/dev/null || echo "no /var/run/docker.sock"
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock info \
  --format '{{.ServerVersion}} {{.Driver}} {{.CgroupVersion}} {{.Architecture}}'

# 4. Inference runtime — version, server, models and their real location
command -v ollama llama-cli llama-server
OLLAMA_HOST=http://127.0.0.1:11434 ollama --version  # no startup heartbeat
systemctl is-active ollama 2>/dev/null || echo "no ollama unit"

# Allowlisted settings only. Never print whole Environment= or ExecStart= lines:
# a unit may carry HTTPS_PROXY credentials, registry tokens or other secrets, and
# this transcript is returned verbatim.
systemctl cat ollama 2>/dev/null \
  | grep -oE '(OLLAMA_HOST|OLLAMA_MODELS|OLLAMA_KEEP_ALIVE|OLLAMA_CONTEXT_LENGTH|OLLAMA_NUM_PARALLEL)=[^"[:space:]]*' \
  || echo "no allowlisted OLLAMA_* settings found"

# One successful snapshot for runtime and contract ports; keep ss errors visible.
if c02_listeners="$(ss -H -ltn '( sport = :11434 or sport = :8080 or sport = :8443 or sport = :30443 )')"; then
  if [ -n "$c02_listeners" ]; then
    printf '%s\n' "$c02_listeners"
  else
    echo "No TCP listeners observed on 11434/8080/8443/30443."
  fi
else
  echo "ss probe failed; listener state unavailable."
fi
# Model inventory from disk, never from `ollama list` (it starts a stopped server).
curl -q --noproxy '*' --fail --silent --show-error --max-time 3 \
  http://127.0.0.1:11434/api/version || echo "no server to query"
for d in "$HOME/.ollama/models" /usr/share/ollama/.ollama/models /var/lib/ollama/models; do
  [ -d "$d" ] && { echo "== $d"; du -sh "$d"; find "$d/manifests" -type f 2>/dev/null; }
done

# 5. Kubernetes tooling (provisioning itself is C05, not C02)
command -v k3s kubectl
kubectl version --client -o yaml 2>&1 | head -12
systemctl is-active k3s 2>/dev/null || echo "no k3s unit"
# The snapshot above includes contract ports 8443/30443. No observed listener
# does not prove a future bind or exclude an existing Kubernetes forwarding rule.

# 6. GPU — host driver only
nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version,compute_cap --format=csv,noheader
command -v nvidia-ctk
dpkg -l 2>/dev/null | grep -iE 'nvidia-container|nvidia-driver-[0-9]' | awk '{print $2, $3}'

# 7. Link presence only — do not paste IP addresses
ip -brief link show | awk '{print $1, $2}'
```

### What the Ubuntu worker returns

The command output above, plus three plain answers:

1. Is this device available for the first configuration?
2. Will it join the agreed trusted LAN, over Wi-Fi or Ethernet? State the
   intended link — **no IP addresses, hostnames, tokens or credentials.**
   If any command still surfaces a proxy URL, token, key or password, redact it
   before sending and say which command produced it.
3. Is the account in the `docker` group, and is passwordless `sudo` available if
   a later checkpoint needs it? State it; do not change it now.

Success looks like a complete, honest transcript including failures. Failure
looks like a missing block, a substituted command, or a service started to make
an entry appear. "Not installed", "inactive" and "permission denied" are all
valid, useful results.
