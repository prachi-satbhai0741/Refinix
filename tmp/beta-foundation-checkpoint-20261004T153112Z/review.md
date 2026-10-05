# Refinix Beta Foundation checkpoint — 2026-10-04

Preserved partial implementation; NEEDS FIX on the specific source issues below before Foundation acceptance. This is a review of interrupted work, not a final verdict on the owner or a claim that the Beta was supposed to be finished. Continue the existing four-section plan; no architecture restart is required.

## Recovery snapshot

Repository: `/Users/adityatadge/Documents/GitHub/AegisForge`; branch `aditya`; HEAD `8c6d7a9fe1c15106fc542792e32e8b36e0bd34db`.

`current-source-and-evidence.tar.gz` preserves 64 files: all tracked dirty file contents, authority entrypoints, scoped untracked Foundation source and completed parity evidence. `working-tree.patch` records tracked changes against HEAD. `manifest.json` records each captured file's SHA-256 and the archive hash. Every archive member was checked against its manifest and current source. This is a mixed dirty tree containing pre-existing user/docs/site work; do not attribute or stage it all as the owner's implementation.

Models, engine binaries, dependency environments, private application data, and untracked site media/tmp content are excluded from the archive. They remain in their original locations. Their exclusion is deliberate; do not commit them. `local-input-integrity.json` records freshly rehashed local engine/model inputs without copying those binaries into source recovery.

Keep this checkpoint until work is safely preserved elsewhere. For recovery, inspect/extract into a separate empty directory first and compare against current files. Do not overwrite a newer working tree, reset files, or apply the patch automatically. No Git write was performed.

## What is source-present

Section 1 / Phase 1 is partial: database-root ownership, private-copy schema admission and schema 13 model-install records; managed llama.cpp selection/fetch/supervision and stream facade; typed readiness, candidate hardware tiers, hidden Beta mesh controls, OS webview preflight; a shared native build driver, dependency locks, PyInstaller spec, Inno installer and Linux templates. Existing frontend, coordinator and orchestration are retained. Five unused helpers and duplicate status work were removed; current references were checked. Cleanup is already underway, not merely postponed until the end.

Implementation source is concentrated in `backend/coordinator/{ownership,engine,local_engine,runtime_llamacpp,readiness,build_info,db,server,runtime,device,models,repo}.py`, `backend/contracts/profiles.py`, `desktop/{lifecycle,shell,__main__,refinix,packaging_plan,build,setup_py2app}.py`, `desktop/engine/`, the platform build templates/locks, `frontend/app/`, and `scripts/{qualify_execution,engine_parity}.py`. Exact archived paths are in the manifest.

The authoritative resume point is `docs/beta-execution-handoff.md`, “Approved execution addendum — 2026-10-04” at line 1283, with `AGENTS.md`, `CLAUDE.md`, `docs/PROJECT.md`, `tasks.md` and focused model/security/release authorities. The old proposals are history. Four sections map to Phase 1, Phase 2, local Phase 4, and Phase 5. Phase 3/distributed and peer Phase 4 are deferred. No subagents or finer task tree.

## Specific source findings

These are static findings; no reproduction test or application call was run by the review agent. Recommended checks below belong in the owner's next authorized coherent implementation/verification batch.

1. **P1 — A database symlink in another directory can receive a different ownership lock.** [ownership.py:36](/Users/adityatadge/Documents/GitHub/AegisForge/backend/coordinator/ownership.py:36) derives the lock from `abspath(state_path).parent`, and `covers` compares the same spelling. A real database and a symlink to it under another parent therefore acquire distinct lock files. Production `--state` entrypoints do not canonicalize that database target. This defeats the actual-store lifetime guard for those aliases. Canonicalize the selected store consistently before computing ownership/storage paths, or refuse unsupported aliases clearly; retain legitimate independent roots and old default lock compatibility. Check two spellings of one store, including sidecar locations, without touching real user data.

2. **P1 — Engine shutdown can discard ownership evidence while the process remains alive.** [engine.py:502](/Users/adityatadge/Documents/GitHub/AegisForge/backend/coordinator/engine.py:502) clears `self.process` before termination, ignores a second wait timeout or an OS error, deletes the durable process record and returns true. [engine.py:558](/Users/adityatadge/Documents/GitHub/AegisForge/backend/coordinator/engine.py:558) kills an orphan after a wait failure, then removes the record without waiting for confirmed exit. A following load can start another engine with the survivor untracked. Preserve proven process identity and report blocked cleanup until exit is confirmed; do not use this result as update/recovery exclusivity. Check failed termination, post-kill timeout and retained records, in addition to the existing successful-stop/recycled-PID cases.

3. **P2 — The empty-store admission shortcut accepts a foreign versioned SQLite file.** [db.py:232](/Users/adityatadge/Documents/GitHub/AegisForge/backend/coordinator/db.py:232) accepts a nonzero-size SQLite file with no tables and application_id 0 as new without inspecting `user_version`. An empty foreign database with a nonzero `user_version` is therefore admitted and later receives Refinix DDL/version writes. The approved addendum explicitly requires refusal of foreign versioned SQLite stores; the present test covers that only when a `notes` table exists. Preserve the documented missing/zero-length new-store behavior, refuse this foreign case byte-for-byte, and add that acceptance fixture. Also normalize malformed `meta` table errors into typed admission refusal: the query at line 238 is outside the SQLite-error conversion block.

4. **P2 — Package input/reuse identity is incomplete.** [build.py:102](/Users/adityatadge/Documents/GitHub/AegisForge/desktop/build.py:102) records Python descriptors/path but no interpreter hash/origin; Inno Setup is just `present`; SDK/toolchain identity is incomplete. [build.py:133](/Users/adityatadge/Documents/GitHub/AegisForge/desktop/build.py:133) does not include the requested trust root in the reuse digest, although it changes the embedded identity later. Same-labelled replacement interpreter/tool bytes or a changed trust root may consequently reuse an old artifact. Include material effective build inputs and trust-root identity; require a nonempty valid artifact list for reuse. These are gaps against the existing approved identity contract, not a request for another build framework.

5. **P2 — Ubuntu tiers do not check the distribution.** [profiles.py:179](/Users/adityatadge/Documents/GitHub/AegisForge/backend/contracts/profiles.py:179) checks Linux family and VERSION_ID tuple only. `device.os_version` reads the distribution ID but hardware matching loses it as a structured field. A Fedora version such as 41 satisfies a numeric Ubuntu floor of 24.04 when other facts match. Retain/check Ubuntu identity before those tier presets are registered. No managed preset is registered yet, so this has not currently admitted a qualified managed run.

Before native builds, also inspect the Windows identity-extraction path at [build.py:438](/Users/adityatadge/Documents/GitHub/AegisForge/desktop/build.py:438): it runs the full product installer/uninstaller under a temporary `/DIR`, using the ordinary AppId. A temporary folder alone does not establish isolation of installer registration/shortcuts/application closing. Use a disposable native runner or a proven extraction mechanism. No such install was run here; effects on an existing Windows installation remain unverified.

## Evidence actually checked in this review

- Freshly read source/caller diffs across DB ownership/admission, facade/engine, readiness, hardware profiles, native shell/startup, build driver/templates and frontend controls; inspected related tests without running them. Existing Graphify data served as navigation only, never as current implementation proof.
- Parsed 30 captured Python files with `ast.parse`; no imports or application execution. Syntax parsing does not establish runtime correctness.
- Rehashed the 2,740,937,888-byte Qwen3.5-4B Q4_K_M weights and 672,423,616-byte F16 projector; both match the catalogue pins. Verified all 60 local macOS engine manifest entries and the manifest's engine-pins digest. These local integrity checks do not establish workflow/release acceptance or independently certify every publisher claim.
- Read the completed parity JSON, which explicitly has `release_accepted=false`. The background run's result is now available; AC-20261004-007's “still running” status is historical. The timestamp in that JSON is the run's recorded generation/start value, not a demonstrated finish time.

| Managed workflow fixture | Reasoning disabled | Reasoning enabled |
|---|---:|---:|
| Chat strict single-line fixture | 0/3 | 3/3 |
| Code | 3/3 | 3/3 |
| Approval note | 3/3 | 0/3 |
| General document | 3/3 | 2/3 |
| Page reading | 0/3 | not tested |

The strict Chat failures are response-shape failures, not proof that ordinary Chat is completely broken. Reasoning-enabled approval notes exhausted the output budget with no answer; the same-bytes Ollama baseline also failed 0/3. Page reading missed identifiers `NG-2026-0417` and `SOP-MECH-014`. Do not register a broad preset or OCR scope by ignoring those failures; adjust/debug within the existing workflow plan and preserve comparable evidence.

On the observed M5/16 GiB Mac with an 8192-token window, the report records managed median 34.945 tok/s versus Ollama 25.18 tok/s and warm median TTFT 0.0745 versus 0.0989 seconds. These are fixture measurements, not universal model speed/accuracy claims. Stop, post-stop usability and refusal of overflow were recorded. Peak observed RSS was 4,606,459,904 bytes; socket snapshots found only loopback with zero observer errors. The observer explicitly says snapshots can miss short connections: observation is not egress enforcement.

The owner's reported checks (AC-20261004-007) include coordinator 1252, desktop 91, build 17, frontend 192, engine 36, readiness 12 and ownership/admission 24; these were not rerun by this review agent. Worker FastAPI and two launcher IP-drift failures were reported separately. Do not turn historical reported counts into fresh review-agent test passes.

## Planning correction and pending work

K23/O.6 in the older handoff overstate the macOS conclusion: blanket RLIMIT_AS/RLIMIT_DATA non-enforcement and native impossibility were not established. Current [Apple XNU resource-limit source](https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/kern/kern_resource.c) dispatches those setters to `vm_map_set_size_limit` and `vm_map_set_data_limit` (lines 1560 and 1426). This does not qualify the installed Darwin build, aggregate process-tree limits or the complete sandbox. Keep the accepted Beta decision: native Mac validation is unqualified/deferred under present constraints. Record version-specific evidence before making a stronger statement. Protected authorities/handoff were not edited in this review.

Section 2–4 work remains: graphical model provisioning/removal/import, local routing/fallback and capacity admission, instructions/memory/retrieval integration, scan qualification, qualified local sandbox/proof/recovery, final packages and verified update/rollback. `PRESETS` is empty and no managed workflow profile is registered. `.github/workflows/package.yml` is absent. Native Windows/Ubuntu artifacts, clean-device observations, final Mac package, N/N+1/engine-change update sets, signatures and release acceptance are unproven. Their absence is expected interrupted work, not evidence of a macOS-only product plan.

The owner should resume Section 1, incorporate these findings in the same batch, inspect the completed parity report, then proceed through the approved sections. Reuse source; remove only proven unwanted code; preserve deferred distributed code and unrelated dirty changes. Do not manufacture readiness by weakening qualification or sandbox checks. The user will resume the implementation owner after its limit resets; handoffs should be copyable text and Computer Use avoided unless necessary.

This review authorized preservation/memory writes only. It did not execute application tests, live models, installers, downloads, migrations, host changes, Git/Actions writes, source fixes or protected documentation edits. Historical execution/check permissions must be reconciled with the resumed owner's current user request and its instruction rules; a saved plan is not new authorization.
