# Device Specifications — AegisForge / SovereignMesh Team

Hardware inventory for the six team devices, collected for **model selection and
capability-pack assignment**. This document is the team's reference for what the
fleet actually is; [model-catalog.md](model-catalog.md) owns model and pack
policy.

- **Collected:** 2026-09-01
- **Status:** reported inventory covers all six devices; only values marked
  measured have local command evidence. Remaining gaps are free disk space,
  installed runtimes, the Mac GPU-core configuration, and two VRAM figures
  needing a `nvidia-smi` recheck.
- **Rule:** treat every capability and model note below as a **hypothesis** until
  benchmarked on the actual device under
  [evaluation.md](evaluation.md#5-measurement-plan).

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
| Aditya | MacBook Air (M5, 13″, 2026) | macOS 26.x | Apple M5 | 10C (4P+6E) / 10 | 16 GB unified | — (8- or 10-core Apple GPU; confirm locally) | shared (unified) | ~470 GB / 512 GB _(confirm)_ |
| Sahil | Lenovo LOQ 15IRX9 (83DV) | Windows 11 Home SL (26200) | Intel Core i5-13450HX | 10C (6P+4E) / 16 | 24 GB DDR5-4800 (2 × 12 GB, dual-channel) | NVIDIA RTX 3050 Laptop | **6 GB** | _(confirm)_ / 477 GB |
| Vedant | ASUS V16 (V3607VH) | Windows 11 Home SL (26200) | Intel Core 7 240H | 10C / 16 | 16 GB DDR5-5600 (1 × 16 GB, single-channel) | NVIDIA RTX 5050 Laptop | **8 GB** _(measured)_ | 191 GB / 477 GB |
| Yug | HP Victus 15-fa1xxx | Windows 11 Home SL | Intel Core i5-12450H | 8C / 12 | 16 GB DDR4-3200 | NVIDIA RTX 2050 | 4 GB _(recheck)_ | ~700 GB / 1 TB _(confirm)_ |
| Prachi | HP Victus 15-fa1xxx | Ubuntu 24.04.4 LTS | Intel Core i5-13420H | 8C / 12 | 16 GB | NVIDIA RTX 2050 (GA107) | 4 GB _(recheck)_ | ~357 GB / 477 GB |
| Tanvi | Dell Inspiron 15 3520 | Windows 11 Home SL (26200) | Intel Core i5-1235U | 10C (2P+8E) / 12 | 16 GB | — (Intel Iris Xe iGPU only) | — | _(confirm)_ / 477 GB |

**Fleet at a glance:** 1 × macOS (Apple Silicon), 4 × Windows, 1 × Linux.
Four machines have a dedicated NVIDIA GPU. VRAM ranks **Vedant 8 GB → Sahil
6 GB → Yug and Prachi 4 GB each**, with the two 4 GB figures still sourced from
tools affected by the saturation bug above. Two machines are iGPU or CPU-only
(Tanvi, and the Mac's unified-memory GPU).

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
- **OS:** macOS 26.x
- **Runtime fit:** MLX (native Apple Silicon) or Ollama/llama.cpp with Metal
- **Network:** Wi-Fi only; the Air has no Ethernet port (USB-C adapter needed)
- **Planning note:** This is the planned **primary workspace + UI** for the
  alpha, not a permanent installation role. The dynamic node model is in
  [architecture.md](architecture.md#2-installation-and-runtime-responsibilities).
  Unified memory means model weights, KV cache, and the OS all share 16 GB —
  budget conservatively (a Q4 4B model is roughly 3–4 GB, leaving headroom for
  embeddings and the app). Good home for the **core chat/agent model** and
  **local embeddings/RAG**; not for a 9B+ model at usable speed. Apple's
  published 13-inch M5 specifications list both GPU configurations; the exact
  GPU-core count and free storage are not measured on this device.

### Sahil — Lenovo LOQ 15IRX9 (model 83DV)
- **CPU:** 13th Gen Intel Core i5-13450HX — 10 cores (6P+4E) / 16 threads, 2.4 GHz base
- **RAM:** **24 GB DDR5-4800, dual-channel** — 2 × 12 GB Ramaxel RMSB3400KB06IVF-4800 (Controller0 + Controller1). **Most RAM and the widest memory bus in the fleet.**
- **GPU (discrete):** **NVIDIA GeForce RTX 3050 6GB Laptop GPU — 6 GB VRAM**, driver 32.0.15.8186. The 6 GB is from the GPU's own SKU name; `AdapterRAM` reported 4 GB, which is the saturation artifact described above.
- **GPU (integrated):** Intel UHD Graphics (RaptorLake-S Mobile), driver 32.0.101.7026
- **Storage:** Samsung MZAL8512HDLU-00BL2, 477 GB NVMe SSD, Healthy — **free space not captured**
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
- **GPU (discrete):** NVIDIA RTX 5050 Laptop, **8 GB VRAM** — 8151 MiB measured via `nvidia-smi`, driver 592.00 / 32.0.15.9200
- **GPU (integrated):** Intel Graphics, shares system memory dynamically
- **Storage:** 512 GB NVMe SSD (Micron MTFDKBA512QGN) — **191 GB free of 477 GB**
- **OS:** Windows 11 Home Single Language (build 26200), VBS/Hyper-V active
- **Display:** 1920 × 1200 @ 144 Hz
- **Network:** **Wi-Fi only** — Realtek 8852BE Wi-Fi 6 at 866 Mbps. Confirmed to have **no Ethernet adapter at all** (only Wi-Fi and Bluetooth PAN present).
- **Planning note:** **The only 8 GB GPU in the fleet**, and enough to hold a
  **7B-Q4 coding model almost entirely on-GPU** — the decisive advantage for the
  coding-worker role. Two caveats: single-channel DDR5 limits memory bandwidth,
  so anything that spills to CPU runs slower than the spec sheet suggests
  (populating the free DIMM slot would improve this), and temporary workspaces
  plus model caches still need reserved disk headroom. Its 191 GB free is ample
  for the prototype's selected model set. Needs a USB-Ethernet adapter for a
  wired demo.

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
- **GPU (discrete):** NVIDIA RTX 2050 (GA107), 4 GB reported — **NVIDIA driver
  not loaded** (`driver: N/A`); a compatible NVIDIA driver is needed before
  `nvidia-smi` can confirm VRAM and before native NVIDIA GPU inference. Install
  the full CUDA Toolkit only if the selected runtime or build explicitly
  requires it.
- **GPU (integrated):** Intel UHD (i915), drives the display
- **Storage:** 512 GB WD SN810 NVMe — **~357 GB free** (119.8 GB used of 477 GB)
- **OS:** Ubuntu 24.04.4 LTS, GNOME 46
- **Network:** Wi-Fi (Intel) + Realtek Gigabit Ethernet; **Docker already installed** (docker0 and bridges present)
- **Planning note:** The only Linux box, and Docker is already running, making it
  the **strongest fit for the sandboxed code-execution worker** under
  [security.md](security.md#8-filesystem-and-sandbox).
  Native Docker with networking disabled is cleanest here, and the sandbox role
  does not need a GPU. **Action:** install a compatible NVIDIA driver if GPU
  inference is wanted; add `nvidia-container-toolkit` only when passing the GPU
  into Docker.

### Tanvi — Dell Inspiron 15 3520
- **CPU:** 12th Gen Intel Core i5-1235U (U-series, low-power) — 10 cores (2P+8E) / 12 threads, 1.3 GHz base
- **RAM:** 16 GB (15.69 GB usable)
- **GPU:** **Intel Iris Xe Graphics only — no discrete GPU confirmed**, driver 32.0.101.7085, so CPU inference only
- **Storage:** Micron 2400A NVMe, 477 GB SSD, Healthy — **free space not captured**
- **Motherboard / BIOS:** Dell 0RNNT7 rev A00; BIOS 1.42.0 (2026-05-27)
- **OS:** Windows 11 Home Single Language (build 26200)
- **Display:** 1920 × 1080 @ 120 Hz
- **Network:** **Realtek 8821CE 802.11ac (Wi-Fi 5) at 390 Mbps — the slowest link in the fleet.** Ethernet unconfirmed: the adapter listing filtered to connected adapters only, so a disconnected port would not have appeared.
- **Planning note:** Lowest inference capability in the fleet — a 15 W U-series
  CPU with a 1.3 GHz base and no dGPU. Best used for **CPU-friendly light
  tasks**: small chat, ASR/voice, a retrieval/embeddings host, or a standby
  coordinator. The slow Wi-Fi link also makes it a poor choice for any role that
  ships large context or files across the network.

---

## Tentative capability-pack mapping (hypothesis — benchmark before committing)

| Capability pack ([model-catalog.md](model-catalog.md#2-baseline-and-conditional-packs)) | Best-fit device | Why |
|---|---|---|
| Main engine + primary alpha workspace | Aditya (M5 Air) | MLX and unified memory may suit a small main model; the app may still use this or paired compute |
| Coding worker | **Vedant (RTX 5050, 8 GB)** | The only 8 GB GPU; holds a 7B-Q4 coding model almost entirely in VRAM |
| Reasoning / large-model worker | **Sahil (RTX 3050 6 GB + 24 GB dual-channel)** | Best CPU-offload host in the fleet; runs a larger model partly on CPU without collapsing |
| Code sandbox execution | Prachi (Ubuntu + Docker) | Native Linux Docker with networking disabled; no GPU required |
| OCR / vision worker | Yug (RTX 2050, 1 TB) | 4 GB VRAM fits a small OCR/vision model; most disk, and has Ethernet |
| Embeddings / RAG | Aditya (coordinator) or Tanvi | Small footprint; can run alongside chat or CPU-only |
| ASR / voice (optional) | Tanvi (CPU) | A small ASR model runs acceptably on CPU; suits the weakest node |

Constraint reminder: **no device exceeds 8 GB discrete VRAM.** Plan every model as
**Q4, bounded context, task-specific output limits** under
[model-catalog.md](model-catalog.md#9-hardware-policy). Do not rely on advertised
128K context windows without local quality and memory tests.

---

## Still needed before final model placement

1. **Free disk space** on Aditya, Sahil, Yug, and Tanvi. Record each approved
   model's exact size. Keep the initial catalogue to 3–5 models per worker for
   prototype simplicity, not as a hard storage-capacity claim.
   Windows: `Get-PSDrive C | Select-Object Used,Free`. macOS/Linux: `df -h /`.
2. **Yug and Prachi — re-read VRAM with `nvidia-smi`.** Their 4 GB figures came
   from tools affected by the saturation bug noted at the top of this document.
   Prachi needs the NVIDIA driver installed first.
3. **Prachi — decide GPU or CPU** for her node and, if GPU, install a compatible
   NVIDIA driver. Add `nvidia-container-toolkit` only for GPU inference inside
   Docker.
4. **Sahil — verify App Control for Business does not block a local runtime.**
   Smart App Control is enforced on that machine and can refuse unsigned
   binaries. This gates whether the node can run llama.cpp or Ollama at all.
5. **Everyone — installed AI runtime** (Ollama / LM Studio / llama.cpp / MLX) and
   version, plus the **driver and runtime-reported CUDA compatibility** on
   NVIDIA machines.
6. **Tanvi — confirm whether the Inspiron has an Ethernet port**, and plan
   USB-Ethernet adapters for Aditya and Vedant, who definitely have none.
