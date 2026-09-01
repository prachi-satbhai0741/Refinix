# Device Specifications — AegisForge / SovereignMesh Team

Hardware inventory for the six team devices, collected for **model selection and
capability-pack assignment** (see [`prd.md`](prd.md) §11–12). This expands the
tentative 4-device table in `prd.md` §12 to the full six-device fleet.

- **Collected:** 2026-09-01
- **Status:** raw hardware confirmed where reported; items marked _(confirm)_ were
  not captured by the command each member ran and must be filled before final
  model placement.
- **Rule:** treat every capability/model note below as a **hypothesis** until
  benchmarked on the actual device (`prd.md` §19 measurement plan).

> **Reading VRAM correctly.** `systeminfo`, `Get-ComputerInfo`, and
> `Win32_VideoController.AdapterRAM` report GPU memory through a signed 32-bit
> field and silently wrap above 4 GB, so an 8 GB card reports as 4 GB or 2 GB.
> Every VRAM figure below marked _(measured)_ comes from `nvidia-smi`, which
> reads the real value. Do not trust a VRAM number sourced from `systeminfo`.

---

## Summary table

| Member | Machine | OS | CPU | Cores/Threads | RAM | Dedicated GPU | GPU VRAM | Free storage |
|---|---|---|---|---|---|---|---|---|
| Aditya | MacBook Air (M5, 13″, 2026) | macOS 26.x | Apple M5 | 10C (4P+6E) / 10 | 16 GB unified | — (10-core Apple GPU, shares RAM) | shared (unified) | ~470 GB of 512 GB _(confirm)_ |
| Sahil | Lenovo LOQ 15IRX9 (83DV) | Windows 11 Home SL (25H2) | Intel Core i5-13450HX | 10C (6P+4E) / 16 | 24 GB | _(confirm — ships w/ RTX 4050 6 GB or 4060 8 GB)_ | _(confirm)_ | _(confirm)_ |
| Vedant | ASUS V16 (V3607VH) | Windows 11 Home SL | Intel Core 7 240H | 10C / 16 | 16 GB DDR5-5600 | NVIDIA RTX 5050 Laptop | **8 GB** _(measured)_ | 191 GB of 477 GB |
| Yug | HP Victus 15-fa1xxx | Windows 11 Home SL | Intel Core i5-12450H | 8C / 12 | 16 GB DDR4-3200 | NVIDIA RTX 2050 | 4 GB _(recheck)_ | ~700 GB of 1 TB _(confirm)_ |
| Prachi | HP Victus 15-fa1xxx | Ubuntu 24.04.4 LTS | Intel Core i5-13420H | 8C / 12 | 16 GB | NVIDIA RTX 2050 (GA107) | 4 GB _(recheck)_ | ~357 GB of 512 GB |
| Tanvi | Dell Inspiron 15 3520 | Windows 11 Home SL (25H2) | Intel Core i5-1235U | 10C (2P+8E) / 12 | 16 GB | — (Intel Iris Xe iGPU only) | — | _(confirm)_ |

**Fleet at a glance:** 1 × macOS (Apple Silicon), 4 × Windows, 1 × Linux.
Dedicated NVIDIA GPUs on 4 machines: one **measured at 8 GB** (Vedant), two
reported at 4 GB but sourced from tools affected by the wrapping bug above
(Yug, Prachi — recheck with `nvidia-smi`), and one unknown (Sahil, likely
6–8 GB). Two machines are iGPU/CPU-only (Tanvi; and the Mac's unified-memory
GPU). No machine exceeds **8 GB discrete VRAM**, so the whole catalogue must be
planned around **≤8 GB VRAM, Q4 quantization, bounded context** — matching the
standing guidance for 8 GB GPUs in `prd.md` §12.

---

## Per-device detail

### Aditya — MacBook Air (M5, 13-inch, 2026) — PRD v1 coordinator
- **SoC:** Apple M5 (3 nm) — 10-core CPU (4 performance + 6 efficiency), 10-core GPU, 16-core Neural Engine
- **Unified memory:** 16 GB, bandwidth **153 GB/s** (shared across CPU/GPU/NE)
- **Storage:** 512 GB SSD (soldered)
- **OS:** macOS 26.x
- **Runtime fit:** MLX (native Apple Silicon) or Ollama/llama.cpp with Metal
- **Planning note:** This is the fixed **coordinator + UI** per `prd.md` §6.3.
  Unified memory means model weights, KV cache, and the OS all share 16 GB —
  budget conservatively (a Q4 4B model is roughly 3–4 GB, leaving headroom for
  embeddings and the app). Good home for the **core chat/agent model** and
  **local embeddings/RAG**; not for a 9B+ model at usable speed. Figures come
  from Apple's published 13-inch M5 tech specs, not measured on the device.

### Sahil — Lenovo LOQ 15IRX9 (model 83DV)
- **CPU:** Intel Core i5-13450HX (13th-gen HX) — 10 cores (6P+4E) / 16 threads
- **RAM:** 24 GB — **most RAM in the fleet**
- **GPU:** _not reported by `Get-ComputerInfo`._ The LOQ 15IRX9 ships with either an **RTX 4050 (6 GB)** or an **RTX 4060 (8 GB)** — **confirm which** with `nvidia-smi`
- **Storage:** _not reported — confirm total and free_
- **OS:** Windows 11 Home Single Language (build 26200, 25H2), UEFI, Hyper-V present
- **Network:** Wi-Fi + Ethernet
- **Planning note:** Highest CPU and RAM in the fleet. If the GPU is the RTX 4060
  8 GB it matches Vedant's machine for VRAM, and the extra 8 GB of system RAM
  makes it the better host once layers spill to CPU. **Strong coding-worker
  candidate, pending GPU and storage confirmation.**

### Vedant — ASUS V16 (V3607VH) — measured directly, 2026-09-01
- **CPU:** Intel Core 7 240H — 10 cores / 16 threads, 2.5 GHz base
- **RAM:** 16 GB DDR5-5600 (single SK Hynix DIMM — **single-channel**; second slot free)
- **GPU (discrete):** NVIDIA RTX 5050 Laptop, **8 GB VRAM** — 8151 MiB measured
  via `nvidia-smi`, driver 592.00 / 32.0.15.9200
- **GPU (integrated):** Intel Graphics, shares system memory dynamically
- **Storage:** 512 GB NVMe SSD (Micron MTFDKBA512QGN) — **191 GB free of 477 GB**
- **OS:** Windows 11 Home Single Language (build 26200), VBS/Hyper-V active
- **Network:** **Wi-Fi only** — Realtek 8852BE Wi-Fi 6 at 866 Mbps. Confirmed to
  have **no Ethernet adapter at all** (only Wi-Fi and Bluetooth PAN are present).
- **Corrects `prd.md` §12,** which lists this machine as an **RTX 5060**. The
  installed GPU is an **RTX 5050 Laptop**.
- **Planning note:** 8 GB VRAM is joint-highest in the fleet and enough to hold a
  **7B-Q4 coding model largely on-GPU**. Two caveats: single-channel DDR5 halves
  memory bandwidth, so any CPU offload runs slower than the spec sheet suggests,
  and 191 GB free limits the machine to roughly 3–5 model files at once. Needs a
  USB-Ethernet adapter to take part in a wired distributed demo.

### Yug — HP Victus 15-fa1xxx
- **CPU:** Intel Core i5-12450H — 8 cores / 12 threads
- **RAM:** 16 GB DDR4-3200
- **GPU (discrete):** NVIDIA RTX 2050, 4 GB reported — **recheck with `nvidia-smi`**; iGPU Intel UHD
- **Storage:** ~1 TB KIOXIA NVMe SSD — **most storage in the fleet**
- **OS:** Windows 11 Home Single Language, Hyper-V active
- **Network:** Wi-Fi 6E (Intel AX211) + **Realtek Gigabit Ethernet** (wired LAN capable)
- **Planning note:** A 4 GB RTX 2050 fits a 3–4B Q4 model or a small OCR/vision
  model. The 1 TB disk makes this the natural **model-cache and OCR/vision
  worker**, and having Ethernet makes it reliable for the wired demo.

### Prachi — HP Victus 15-fa1xxx (Linux)
- **CPU:** Intel Core i5-13420H — 8 cores / 12 threads (Raptor Lake)
- **RAM:** 16 GB (15.26 GB available)
- **GPU (discrete):** NVIDIA RTX 2050 (GA107), 4 GB reported — **NVIDIA driver not loaded** (`driver: N/A`); the proprietary driver and CUDA toolkit are needed before GPU inference, and before `nvidia-smi` can confirm real VRAM
- **GPU (integrated):** Intel UHD (i915), drives the display
- **Storage:** 512 GB WD SN810 NVMe — **~357 GB free** (119.8 GB used of 476.9 GiB)
- **OS:** Ubuntu 24.04.4 LTS, GNOME 46
- **Network:** Wi-Fi (Intel) + Realtek Gigabit Ethernet; **Docker already installed** (docker0 and bridges present)
- **Planning note:** The only Linux box, and Docker is already running, making it
  the **strongest fit for the sandboxed code-execution worker** (`prd.md` §16.6).
  Native Docker with networking disabled is cleanest here, and the sandbox role
  does not need a GPU. **Action:** install the NVIDIA driver and
  `nvidia-container-toolkit` only if GPU inference is also wanted on this node.

### Tanvi — Dell Inspiron 15 3520
- **CPU:** Intel Core i5-1235U (U-series, low-power) — 10 cores (2P+8E) / 12 threads
- **RAM:** 16 GB
- **GPU:** **integrated Intel Iris Xe only — no discrete GPU**, so CPU inference only
- **Storage:** _not reported — confirm total and free_
- **OS:** Windows 11 Home Single Language (build 26200, 25H2), Hyper-V present
- **Network:** **Wi-Fi only** (no Ethernet adapter reported)
- **Planning note:** Lowest inference capability in the fleet (U-series CPU, no
  dGPU). Best used for **CPU-friendly light tasks** — small chat, ASR/voice, a
  retrieval/embeddings host, or a standby coordinator — rather than a GPU model
  worker. Fine as a fallback node.

---

## Tentative capability-pack mapping (hypothesis — benchmark before committing)

| Capability pack (`prd.md` §11.4) | Best-fit device | Why |
|---|---|---|
| Core chat / agent + router (coordinator) | Aditya (M5 Air) | Fixed coordinator per §6.3; MLX and unified memory suit a small chat model plus embeddings |
| Coding worker | Vedant (RTX 5050, 8 GB measured) or Sahil (if RTX 4060 8 GB) | The only two candidates that can hold a 7B-Q4 coding model largely in VRAM; Sahil wins on 24 GB system RAM if his GPU is also 8 GB |
| Code sandbox execution | Prachi (Ubuntu + Docker) | Native Linux Docker with networking disabled; no GPU required |
| OCR / vision worker | Yug (RTX 2050, 1 TB) | 4 GB VRAM fits a small OCR/vision model; most disk, and has Ethernet |
| Embeddings / RAG | Aditya (coordinator) or Tanvi | Small footprint; can run alongside chat or CPU-only |
| ASR / voice (optional) | Tanvi (CPU) or Yug | A small ASR model runs acceptably on CPU |

Constraint reminder: **no device exceeds 8 GB discrete VRAM.** Plan every model as
**Q4, bounded context, task-specific output limits** (`prd.md` §12). Do not rely on
advertised 128K context windows without local quality and memory tests.

---

## Still needed before final model placement

1. **Sahil — GPU model and VRAM** (`nvidia-smi`) plus **total and free storage**.
   This decides whether the 7B coding model goes to him or to Vedant.
2. **Tanvi — total and free storage.**
3. **Yug and Prachi — re-read VRAM with `nvidia-smi`.** Their 4 GB figures came
   from tools affected by the 32-bit wrapping bug noted at the top of this
   document; Prachi needs the NVIDIA driver installed first.
4. **Prachi — decide GPU or CPU** for her node and, if GPU, install the NVIDIA
   driver and `nvidia-container-toolkit`.
5. **Everyone — installed AI runtime** (Ollama / LM Studio / llama.cpp / MLX) and
   version, plus the **driver and CUDA version** on NVIDIA machines.
6. **Free-disk confirmation** on Aditya and Yug. Each model file is 3–15 GB, so
   plan for 3–5 models per worker.
7. **Ethernet availability** for the distributed demo — confirmed present on Yug
   and Prachi, confirmed absent on Vedant, reported absent on Tanvi. Vedant and
   Tanvi need USB-Ethernet adapters for a wired demo.
8. **`prd.md` §12 correction** — the ASUS V16 row lists an RTX 5060, but the
   measured GPU is an RTX 5050 Laptop. Fix when the PRD next opens for edit.

_Commands to fill the gaps — Windows:_ `nvidia-smi` and
`Get-PSDrive C | Select-Object Used,Free`. _Linux:_ `nvidia-smi` and `df -h /`.
_macOS:_ `df -h /`.
