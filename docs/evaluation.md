# Evaluation, Prototype Plan, and Demonstration

Evidence snapshots below retain their recorded dates and scope. Current requirements and execution
gates come from [PROJECT.md](PROJECT.md) and [tasks.md](../tasks.md), not historical PRD/P-task labels.
The [2026-10-04 runtime finding](#runtime-ownership-20261004) is a user report plus current source
inspection; it does not establish fresh device, inference, packaged-runtime or release acceptance.

## Current status

<a id="beta-01-segment-1"></a>
### Beta 0.1 Segment 1 — 2026-10-10

The continuation preserves the existing `aditya` commits and completes the A1 repair batch before
production Beta keys, merges or publication. Native qualification uses disposable packages
`0.1.0-beta.901` and `.902` with throwaway trust keys; they must never be published.

**Repairs checked in this continuation:** sandbox teardown verifies the loop device's backing image
before unmounting it; damaged Ubuntu current-attempt authority blocks admission and preserves
recovery copies; native CI fails on missing/failed reports and qualifier exits; public verification
binds the live website and installed packages to the requested version. Windows native test fixtures
use the actual interpreter, allow legitimate console processes and wait for cleanup. Ubuntu CI
bounds APT index fetches and installation, with one authenticated official-mirror fallback.

**Local offline evidence:** Python 3.14.6 on the development Mac, using an isolated temporary
environment with repository hash-pinned test dependencies and the existing Pydantic environment;
Node for the frontend. Coordinator: 1,656 tests, OK (16 skipped); desktop: 253 tests, OK (6 skipped);
scripts: 75 tests, OK; contracts: 21 tests, OK; frontend: 248 passed. Worker: 217 tests, OK;
deployment fixtures: 140 tests, OK; C07 fixtures: 32 tests, OK. The focused recovery/CI/public
regressions passed 73 tests. `actionlint` passed on all four changed workflows and
`git diff --check` was clean. Initial broad runs were blocked by the tool sandbox's loopback
restriction and a missing test dependency; the approved temporary environment resolved both.
These are source/fixture checks, not native Windows/Linux or device acceptance.

**Earlier hosted run:** [37981019381](https://github.com/prachi-satbhai0741/Refinix/actions/runs/37981019381)
tested `bbf54225d132b78276f3013f80a531dd00eafae3`, before these repairs. Windows failed native unit
tests (Linux-only import and process-count assumption); package/install journeys were skipped.
Linux was cancelled after stalling on the Azure Ubuntu APT mirror, before any build. The Mac lane
reported success under the older summary gate; this does not qualify the repaired tree.

**First repair qualification:** [37988624319](https://github.com/prachi-satbhai0741/Refinix/actions/runs/37988624319)
tested `0aa4645c49cd6da025b05df83a362c49a4d0b3fe`. Linux APT setup passed in 18 seconds and both
packages built; the next checks exposed inherited system AWS/OpenSSL packages conflicting with
the pinned cryptography library. Windows native units passed, both installers built, and package
install/file-list/registration/uninstall passed; the launch check timed out while the app served
requests. The follow-up isolates Ubuntu's `gi`/`cairo` bindings and allows 10 seconds for a status
response in both package and journey checks. Regressions cover toolkit isolation, missing bindings
and delayed status responses without accepting a different data root. Native rerun is pending.

**Remaining:** fresh hosted qualification of one repaired commit on Windows Server 2025, Ubuntu
24.04 and macOS 15/14; production Beta keys/root, member → dev → main, release-byte qualification
and CP-B publication; then the user's device walkthroughs. No production keys, installed user app,
real model runtime, published feed or device acceptance changed in this continuation.

<a id="tester-preview-batch-20261008"></a>
### Tester-preview batch — 2026-10-08

Run by the agent on the development Mac (Apple M5, 16 GB, macOS 26.7.1, Python 3.12) and in
Docker containers on that Mac, against the uncommitted working tree on `aditya` (base
`e234a0a`). These are **build and offline checks**, not device acceptance: no Windows computer
and no clean Ubuntu desktop was available, so every device walkthrough below stays pending.

| Check | Where it ran | Result |
|---|---|---|
| Coordinator, desktop, scripts, contracts suites | Mac | See [the final run](#tester-preview-batch-suites) |
| Frontend suite | Mac (Node) | See [the final run](#tester-preview-batch-suites) |
| Linux-only unit tests (deb root step, update methods, sandbox) | Ubuntu 24.04 amd64 container (emulated), unprivileged user | 66 passed |
| `.deb` update root step against real dpkg 1.22.6 / apt 2.8.3 (`scripts/qualify_deb.py`) | Same container, disposable root environment | 14/14 passed: exact Inst+Conf plan, same-version reinstall, refusal of plans needing other packages, admission on root's copies, install, rollback, held dpkg lock, refusal with other unfinished packages, repair after a killed unpack, unpacked → configured |
| Landlock in the Code sandbox launcher | Ubuntu 24.04 arm64 container (native) | ABI 8 enforced: paths outside the workspace denied, tests inside ran |
| `systemd-run --user` sandbox properties, udisks image mount | — | **Not run**: needs a real Ubuntu desktop session. The Ubuntu sandbox stays provisional |
| Windows setup inside a job, registry undo, Authenticode | — | **Not run**: no Windows computer. Source and fakes only |
| macOS app swap with a Developer ID build | — | **Not run**: no Developer ID identity; the DMG is unsigned and not published |

<a id="tester-preview-batch-suites"></a>
**Final offline run on the Mac** (same tree, Python 3.12, Node): coordinator 1635 passed (5
skipped), desktop 224 passed (1 skipped), scripts 62 passed, contracts 20 passed, frontend 247
passed; `git diff --check` clean. Baseline at `e234a0a` before the batch: coordinator 1584,
desktop 188, scripts with 2 failures (launcher address drift, fixed at its cause), contracts 20,
frontend 242.

**Packages built locally** (not publishable: uncommitted tree, throwaway update trust root):

| Package | Where | Result |
|---|---|---|
| macOS ZIP + DMG, Beta `0.1.0-preview.1`, public build 7, unsigned | the development Mac | Built in 20 s; DMG checksum valid; ad-hoc signature verifies; Gatekeeper rejects it, as expected for an unsigned app; embedded identity preview/build 7/`preview-test`. `LSMinimumSystemVersion` is 26.0 because this Mac's Python is Homebrew's; the release Mac should build with a python.org framework Python to lower it |
| Ubuntu `.deb` (+ AppImage), Beta `0.1.0-preview.1` | Ubuntu 24.04 amd64 container (emulated) | Built in 45 s (`.deb` 58 MB, AppImage 62 MB); see [the container build](#tester-preview-batch-deb) |
| Windows setup | — | **Not built**: needs the hosted Windows runner (`release.yml`) from the reviewed `main` commit |

<a id="tester-preview-batch-deb"></a>
**The Ubuntu package, built the way `release.yml` builds it** (system Python 3.12 with Ubuntu's
GTK/WebKitGTK bindings, the lane's pinned locks, PyInstaller, the pinned engine archives), then
qualified as root in the same throwaway container with `scripts/qualify_deb.py --real`: 23/23
checks passed with dpkg 1.22.6 and APT 2.8.3. They include the 14 update-rule checks above plus,
on the real package, only supported control fields; the program, build identity, file list,
polkit policy and desktop entry present; installation through APT with its dependencies; the
installed tree matching its file list; and the root entry refusing to run without pkexec. A dry run
of `release_assemble.py` and `build-site.sh` on that package produced `SHA256SUMS`, release
notes and download cards offering only the `.deb`.

Building it found four defects in the release workflow, fixed in this batch and covered by
`scripts/test_workflows.py`. The Windows and Ubuntu jobs installed only part of the packaging plan's
locks, so the bundle would have lacked the update client, `psutil` and PDF rendering. The Ubuntu
job lacked `libpython3.12`, without which PyInstaller refuses Ubuntu's Python. The qualification
step used the wrong arguments, interpreter and guard. The `.deb` root-step tests ran before the
lock they need. Docker's amd64 emulation cannot execute AppImages (their header magic fails the
emulator's match), so in the container only, the build ran AppImages from copies with those three
bytes zeroed; hosted x86_64 runners run them directly. The trust root inside these packages was a
throwaway one: they are for checking only and are never published.

**Refinix's own overhead** (`scripts/measure_performance.py`, no model running, Ollama stopped):

| Measure | Result |
|---|---|
| Launch to first answered `/v1/status` | 330 ms |
| `/v1/status` (30 calls) | median 4.3 ms, p95 6.0 ms, 62 KB |
| Idle after 20 s | 0% CPU, 107 MB resident, 3 threads |
| Rendering a 3-page scanned PDF (warm) | 111 ms, about 40 MB peak traced memory |
| 256 MB update package: check / download and stage / offline admission | 19 ms / 326 ms / 200 ms; 512 MB staged including the recovery package |

No Refinix-side cost was large enough to justify an optimisation in this batch. Model time
(first token, OCR) was not measured: no live model ran.

**Removed as dead code** (no caller in source or tests): `db.get_sources`,
`db.get_model_enabled`, `db.model_enablement`, `engine.ManagedEngine._blocked`,
`capacity.Ledger._pending`, `models.entries_for`, `server.preview_model`, `server._engine_kind`,
`server.default_model`, `device.target_identities`. Deferred paired-device, worker, Kubernetes and
Redis code was kept.

**Moved out of the repository** (recoverable, with a hash manifest, in a private archive outside
Git): the former presentation brief and generated PDFs, an old Beta-foundation checkpoint folder
under `tmp/`, and ignored build output. Git history still contains the files that were tracked.

Earlier snapshot, kept for history: source and test bodies re-inspected on **2026-09-16**, at
`942b87deaf9fbb5d070e069ebbe0bb1f74322604` (clean `aditya` before this documentation
change). This supersedes the 2026-09-15 snapshot for **source status**; it is not a
new runtime, package, model, worker or egress verification. No application tests,
models, services, installers or live devices ran in this documentation task.

The existing app is substantially implemented/prototyped. The public Beta is
**not release-ready**: no accepted clean-install profile, supported model lifecycle,
portable peer experience or automatic model/device scheduler is established. The
[task graph](../tasks.md#numbered-execution-tasks) reuses current work, then closes
these gaps before the P14 frontier.

<a id="beta-source-audit"></a>
### Implementation and evidence audit

“Source present” below means the path and relevant test bodies were inspected.
Test existence and recorded past results are separate from fresh runtime proof.

| Capability | Current source and inspected check | Evidence boundary / remaining work |
|---|---|---|
| Desktop and surfaces | `desktop/lifecycle.py`, `shell.py`, `setup_py2app.py`; `frontend/app/` Chat, Code, Settings; `desktop/test_packaging.py` | Existing Mac bundle path packages coordinator/contracts/frontend but excludes worker and inference engine; P02/P03/P13 must qualify complete installer/runtime. Windows/Linux shell branches are not install support |
| Local Chat/context | `server.py` → `context.py` → `runtime.py`; `test_context.py`, `test_reasoning.py`, `test_conversations.py` | Bounded selected history, per-model reasoning, cancellation and persisted attempts exist. Current real quality, failures and final-package parity remain P06/P12/P13 |
| Remote Chat | `server._run_remote` → `dispatch.build_envelope` → `worker/executor._generate`; `test_dispatch.py`, worker `test_executor.py` | Remote Chat currently sends the original request without selected history; worker generation builds a one-message prompt and uses reasoning-off runtime default. UI reasoning/context records do not establish remote parity. P11 must transport bounded context and either honour reasoning or expose it unavailable |
| Model choice/lifecycle | `server.model_inventory`, `select_model`, `db.py`, frontend `appendModelChoices`; `test_execution4c.py` | Persistent per-workflow selection exists for observed models/defaults. Auto is disabled; inventory does not implement curated download/import/cancel/removal/self-tests or full manifests. Installed models are broadly offered for Chat/Code without workload qualification; hard-coded Mac/Ubuntu location labels remain. P04/P05/P10 |
| Scheduling/admission | `dispatch.choose_route`, `db.active_relationship`; `worker/app.py` submit and `_node`; `test_dispatch.py`, `test_worker_app.py` | One active paired-worker route; queue depth descriptive, available memory unknown. Receiver checks `active_attempts(relationship_id)` against MAX_ACTIVE before enqueue; durable receipt/enqueue exists, but this is not atomic device-wide capacity reservation. P10 minimum safe placement; P15 fairness and fleet intelligence |
| Documents and source reuse | `server._request_sources`, `_document_stage`, `docflow.py`, `documents.py`, `retrieval.py`; `test_reliability.py`, `test_documents.py`, `test_execution4a.py` | Local attached-file reading, explicit same-chat reuse/revalidation, FTS5 passages and citation checks, Word/PDF/XLSX writers exist. Documents remain local; native PDF/image rendering uses Quartz/AppKit. Real scan→SOP→artifact quality/layout is P06; hybrid retrieval P16 |
| Recent OCR repairs | `ocr.parse_page_reply`/`read_page`, `docflow.requests_transcription`; `test_ocr.py`, `test_reliability.py` | Old `{text}`-only claim is obsolete: schema now has transcription/unreadable/refusal outcomes, refusal raises an error, and unreadable text remains literal. Source-less transcription stops before routing; the intent heuristic is conservative English. This is implemented guard logic, not broad OCR quality evidence |
| Recent UI/artifact repairs | `server.chat_messages`, `docflow.py`, `frontend/app/app.js`, `markdown.js`; `test-composer.cjs`, `test-rendering.cjs` | Assistant-only artifact ownership, one-submission skills, ordered-list structure and explicit source reuse exist; latest first-chat skill race correction is in source. Package parity and real document depth remain unverified |
| Code proposals and writes | `code_service.py` → `codeflow.py`/`repo.py`/`policy.py`; `test_code_access.py`, `test_remote_code.py`, `test_reliability.py` | Structured proposal schema and bounded completion/failure metrics now exist; the old generic-diagnostics gap is obsolete. Local Apply/Undo uses approvals/backups and says not sandbox tested; remote Apply requires matching passing validation. Descriptor-relative access is required even for reads, a Beta portability gap for P06 |
| Worker transport/recovery | `worker/app.py`, `pairing.py`, `dispatch.py`, `executor.py`, `packages.py`; worker API/executor/package tests | Pairing/revocation, Redis-backed receipts/leases/replay/cancellation and bounded Code packages exist; component READMEs claiming absent/501-only routes were stale. Deployment/current target acceptance remains open; portable packaged receiver is P08 |
| Sandbox | `worker/validate.py`, `jobspec.py`, `kube.py`, `deploy/k3s/50-validation.yaml`; `test_validation.py`, `test_manifests.py` | Restricted Python/unittest validation Job exists; limits and policies in source do not prove runtime enforcement. No universal native desktop sandbox. Qualify an actual eligible profile in P07 and its integrated use in P11 |
| Trust, status and Proof Cards | Coordinator/worker `pairing.py`, `proof.py`, frontend Settings/status; `test_c10.py`, `test-proof-card.cjs` | Pinning/revocation and per-attempt Proof Cards exist; coordinator secrets use macOS Keychain, discovery/guided portable trust missing. `_empty_network()` returns unavailable evidence: no live zero-egress collector is proven. P09/P12 must close these gaps |
| Build/release pipeline | `.github/workflows/ci.yml`, desktop package/tests, worker Dockerfile/locks | Source CI definitions run repository checks on Linux; no inspected hosted result proves this commit passed. No cross-platform signing/publishing/updater pipeline. Prototype version 0.1.0 is not public Beta acceptance |

Paths without a prefix in coordinator rows are under
[backend/coordinator](../backend/coordinator); worker rows under
[backend/worker](../backend/worker). The [frontend](../frontend/app) and
[desktop](../desktop) checks are source-level reproducible assets.

### Recorded checks, not rerun here

The 2026-09-15 P01 counts below remain dated observations of the older baseline.
Later [reliability work](../agent-memory/agentchangelog.md#ac-20260915-004) records
279 focused coordinator and 137 frontend checks, followed by 88 Code/reliability
checks; [review repairs](../agent-memory/agentchangelog.md#ac-20260916-001) record
115 coordinator and 139 frontend checks. Their relevant source/test bodies were
inspected here, but these counts are retained reports, not independently rerun
results. They cannot prove real-model quality, worker deployment, current package
parity, graphical installation or public egress enforcement. In particular, the
older 28-module package/source parity result predates these repairs.

### Contradictions and disposition

| Finding | Resolution / remaining gap |
|---|---|
| Mac-first Beta inferred from a narrow support matrix | Superseded by requester correction: Windows, macOS and Linux are Band A requirements. Full in-app updater remains P19/P23; authenticated manual replacement/recovery is sufficient for Beta |
| P01 waited on every candidate device before P02 | P01 selects profiles in all three OS families; implementation gaps belong to P02–P13, expanded qualification to P18/P22. No untested device is silently marked supported |
| Old P02/P07 both owned packaging/update acceptance; C/E/AF/F boards competed with production sequencing | [Task mapping](../tasks.md#previous-production-gate-mapping) assigns feasibility, implementation, integration and release acceptance once; historical boards remain evidence only |
| Backend/worker/contracts/frontend READMEs said consumers, pairing, workflows or UI were absent, and recommended a React migration | Corrected entry points to current source and canonical authorities; no runtime rewrite. Older handoffs retain their dated reproduction content under an explicit historical banner |
| First-run recommendations implied complete model management | FR-015 and [one catalogue lifecycle](model-catalog.md#persistent-model-management) explicitly cover later operations; current inventory/selector are only a partial base |
| Auto says “after internal hackathon”, model locations imply fixed OS roles | Product requirement is now Beta routing and dynamic device labels; source copy/behaviour remains a P05/P10 implementation gap. Documentation does not silently enable Auto |
| Old OCR refusal and missing Code metrics listed as unfixed | Corrected to inspected typed outcomes and structured diagnostics; remaining work is real quality/coverage and package parity |
| Proof Card described as wholly unimplemented | Builder/UI/tests exist; runtime network fields are unavailable. P12 adds scoped observed evidence, not a fabricated green state |
| A remote sandbox or native inference peer implied all-platform sandbox readiness | Per-capability support; no host-execution fallback. P07 qualifies one real profile, P18/P22 broaden it |

### Repository cleanup disposition

Updated 2026-09-16 after requester-authorised consolidation. The active execution
plan is now P01–P26 only. [Agent execution context](../tasks.md#agent-execution-guide)
links source, tests, authorities and checkpoint fields; [worker operations](worker-operations.md)
consolidates the retained managed-backend build, network, trust and recovery path.

- Removed the superseded C03 implementation and C04 delegation briefs. Durable
  Chat continuity/rendering requirements live in [workflows](workflows.md#chat-continuity-and-rendering);
  worker requirements live in architecture/security and the operational runbook.
  No new acceptance claim is inferred from deleting an old instruction.
- Moved six evidence/reproduction handoffs, the old input template and the retired
  C/E/AF/F task board to `docs/archive/`. [The index](README.md#release-and-historical-material)
  maps old paths to replacements. Archived observations/commands retain historical
  wording; repaired links and retirement notes explain the context. Old image/
  model/pending statements are not a current operational contract.
- Updated CLI help, manifest comments and documentation tests to canonical paths.
  Network-safety checks still inspect the retained historical procedures as well
  as the active runbook; missing required documents must fail rather than skip.
- Preserved all fixtures, hashes, lockfiles, measured pins and reproduction tools.
  Empty `__init__.py` files serve imports/test discovery. The legacy C08 path in
  `fixtures/c07/documents/expected.json` is historical fixture metadata; its bytes
  and provenance remain unchanged rather than rehashing a fixture for cleanup.
- The root README, website/design content and SIH presentation were deferred and
  kept byte-identical to the start of this cleanup. Prior-turn changes remain.
  Ignored outputs/private state were not cleaned. No runtime capability was removed.

The archive is for a specific reproduction question, not normal task startup.
Git history retains the deleted briefs; the request/change ledgers retain their
original dated paths. Do not recreate missing old filenames as placeholder docs.

<a id="p01-baseline"></a>
## P01 — baseline and support contract

Status: **in progress**. The dated baseline below is retained; the 2026-09-16
source audit above supersedes its implementation-gap statements. Current P01
closes on accepted target profiles across all three desktop OS families, not every future OS version or hardware/backend combination.
Historical baseline source commit:
`3bcf479043fc56ca980a8313869c93ebb023ab4c`, clean `aditya` before this documentation
change. No workflow, dependency, runtime or packaging implementation was changed.

### Initial qualification profiles

Qualify the exact available profiles first. These are candidate targets, not
advertised minimum requirements. No older macOS version, other Windows edition,
Intel Mac, ARM Windows/Linux or additional Linux distribution is promised by this
contract. Published capability support stays unverified until its relevant
[production gates](../tasks.md#numbered-execution-tasks) pass.

| Candidate profile | Execution backends to qualify | Current evidence boundary |
|---|---|---|
| macOS 26.6.2, arm64 | Local CPU/Metal; requester and app-managed execution target | OS/architecture observed on 2026-09-15; existing macOS source/package checks below. Real workflows and portable worker still need acceptance |
| Windows 11 Home Single Language, build 26200, x86_64 | CPU-only and available NVIDIA profiles; requester and execution target | Four devices confirmed available by requester on 2026-09-15. OS/build/hardware are the [historical inventory](devicespecifications.md#summary-table), not refreshed readiness evidence |
| Ubuntu 24.04.4 LTS, x86_64 | CPU/NVIDIA; requester, portable execution target and retained managed worker | Historical inventory only; current worker source, runtime and end-to-end execution have not been re-observed |

The public minimum support matrix is currently **unqualified**, including the
minimum RAM/storage and supported toolchains for each enabled capability. The
macOS bundle's `LSMinimumSystemVersion: 12.0` is packaging metadata, not proof of
macOS 12 compatibility. A Windows Home profile cannot be qualified solely with
Windows Sandbox. Homogeneous Windows and macOS peer operation belongs to P08/P09 Beta
qualification without a Linux inference dependency. Remote-only requester support is distinct from local
inference and safe code execution.

<a id="workflow-baseline-and-gaps"></a>
### Workflow baseline and gaps — historical 2026-09-15

The old P03/P04/P06 references in this dated table use the [previous gate mapping](../tasks.md#previous-production-gate-mapping). See the current audit for OCR/Code repairs.

| Shared path | Source observation / existing safeguard | Unresolved production acceptance |
|---|---|---|
| Chat: `server.py` → `context.py` → `runtime.py`; remote `dispatch.py` → worker `executor.py` | Local selected history is bounded and retained; cancellation and restart lifecycles have offline checks. Remote Chat envelopes currently omit selected history, and the executor builds only the original user request; worker reasoning is fixed off | Local/remote follow-up and reasoning parity, real output quality, failure telemetry and context isolation on actual devices; P03/P06 |
| Models and placement: `server.py`, `dispatch.py`, `frontend/app/app.js` | Per-workflow model choices exist; Auto is disabled. One active paired worker is chosen by health/capability/model compatibility; queue depth is descriptive | Qualified second model, task-aware choice, receiver reservations, fair admission and multi-device recovery; P03/P06 |
| Documents: `docflow.py` → `documents.py`/`ocr.py` → `retrieval.py` → artifact writers | Attached-file Chat and Documents are forced local. FTS5 retrieval checks selected-source citations. OCR parses a strict `{text}` object but accepts a structurally valid refusal as text. PDF rendering/writing uses Quartz/AppKit | Real scan/image readings, missing-value/refusal handling, semantic retrieval and corpus lifecycle; cross-platform document/PDF paths; P03 |
| Code: `code_service.py` → `codeflow.py`/`repo.py`/`policy.py`; worker validation | Local Apply requires explicit target/access, verified backups and Undo, and reports **not sandbox tested**. Distributed Apply requires matching passing validation. The local proposal call reports non-clean completion generically without retaining its metrics | Real model proposal reliability, useful diagnostics and qualified standalone sandbox/toolchains. Preserve local versus distributed evidence distinction; P03/P04 |
| Trust: `pairing.py` and Settings | Pinned identity mismatch refuses fallback; revocation is explicit. Coordinator credentials use macOS Keychain and fail closed elsewhere | Portable OS credential storage, graphical discovery/pairing and receiver controls; P05 |
| Desktop/release: `desktop/lifecycle.py`, `shell.py`, `setup_py2app.py` | Existing app manages loopback coordinator/Ollama lifecycle. macOS bundle includes coordinator/contracts, excludes worker and inference engine. Windows/Linux shell branches exist | Dependency-complete installers, app-managed execution agent, signing, clean-device use and N → N+1 recovery; P02/P04/P07 |

Source observations identify work to qualify; they are not real-model failure
measurements. No live inference, worker contact, installation, app rebuild,
deployment or network-enforcement experiment ran for P01.

### Observed local checks — 2026-09-15

Host: macOS 26.6.2, arm64. Repository `.venv`: CPython 3.14.6 and Pydantic,
without FastAPI/HTTPX/Redis/PyObjC/pywebview. Existing `desktop/.venv`: CPython
3.12.13 with Pydantic/PyObjC/pywebview, without FastAPI/HTTPX/Redis. Node 26.7.0.
This differs from CI's Python 3.13 / Node 24; no hosted CI result is inferred.

| Check | Observed result |
|---|---|
| Coordinator discovery under repository `.venv` | 614 tests, OK, 14 skipped. The first restricted run had 11 loopback-bind permission errors; rerun with sandbox allowance passed. Native PDF/renderer and real-model acceptance are not established by the skipped paths |
| Contracts, worker runtime/executor/packages/validation, deployment fixtures and scripts | 338 tests, OK; model/Redis/Kubernetes/host changes are replaced with isolated fixtures/mocks |
| `fixtures.c07.test_fixtures` | 32 tests, OK; hashes, synthetic provenance, raster-only scan and before/after repair on a disposable copy verified; canonical code fixture remains broken |
| Desktop lifecycle/packaging/review checks under `desktop/.venv` | 51 tests, OK after sandbox allowance for the temporary loopback fixture |
| Native `TestRealRenderer` and `TestPdfWriting` under `desktop/.venv` | 9 tests, OK; actual Quartz renders the synthetic scan and writes/reopens synthetic PDFs. No vision-model call or visual layout acceptance included |
| All six frontend Node suites | 129 tests, passed, zero failures/skips; simulated DOM/VM checks, not an operator walkthrough |
| Existing `desktop/dist/Refinix.app` contents | Existing verifier passed across loose packages and Python ZIP; 28 shipped application modules matched current source after normalising bytecode filenames; primary Chat/Code/Settings HTML and `app.js` matched. Version 0.1.0. Entry scripts are not shipped as importable modules and were not included in that parity count |
| Worker API suite | Not run: neither existing Mac environment contains FastAPI/HTTPX. Full worker/CI acceptance remains open; no dependency installed to manufacture a passing result |

The passing coordinator run emitted a ResourceWarning for an isolated HTTPError
fixture; the native PDF run also logged a CoreGraphics diagnostic. No failing
assertion remained. These results do not prove broad
security, zero egress, performance, model accuracy or clean-machine installation.

Reproduce the existing checks from the repository root, using the same existing
environments. Temporary loopback sockets must be permitted for coordinator and
desktop fixtures. Do not run real-model OCR acceptance by assuming that a whole
native coordinator discovery is offline.

```zsh
./.venv/bin/python -B -m unittest discover -s backend/coordinator -p 'test_*.py' -q
./.venv/bin/python -B -m unittest backend.contracts.test_contracts backend.worker.test_worker_runtime backend.worker.test_executor backend.worker.test_packages backend.worker.test_validation deploy.k3s.test_manifests deploy.k3s.host.test_guard deploy.k3s.checks.test_inference_check scripts.test_od03_parser scripts.test_refinix_launcher -q
./.venv/bin/python -B -m unittest fixtures.c07.test_fixtures -q
desktop/.venv/bin/python -B -m unittest desktop.test_lifecycle desktop.test_packaging desktop.test_review_fixes -q
desktop/.venv/bin/python -B -m unittest backend.coordinator.test_ocr.TestRealRenderer backend.coordinator.test_execution4a.TestPdfWriting -q
node --test frontend/app/test-*.cjs
desktop/.venv/bin/python -B -c 'from pathlib import Path; from desktop.test_packaging import setup_module_namespace; setup_module_namespace()["verify_application_contents"](Path("desktop/dist/Refinix.app")); print("bundle contents: PASS")'
```

### Representative fixtures and fixed baseline criteria

Reuse [c07-v1 provenance](../fixtures/c07/provenance.json) and the existing
[document expectations](../fixtures/c07/documents/expected.json) and
[code expectations](../fixtures/c07/code/expected.json). All content is synthetic
under the repository licence. No private corpus or new download is needed.

- Chat: request the exact sentinel `P01_OK`, ask a follow-up about that request,
  cancel another attempt, then quit/reopen. Record actual reply/stop reason,
  selected context, terminal state and retained history; failure stays a failure.
- Documents: use the three-page raster scan plus SOP-MECH-014. Recover expected
  readings on their source pages, preserve missing suction pressure, distinguish
  the 7.9 reading from the 7.1 alarm limit, and produce a readable cited Word/PDF
  artifact. Check field/citation correctness and file layout separately. Passing
  this clean synthetic scan is a floor, not broad OCR accuracy.
- Code: copy `fixtures/c07/code/pumpcheck` outside the repository. Only
  `pumpcheck/limits.py` may change, replacing `>=` with `>`; tests/constants must
  stay unchanged. The six-test fixture must have two failures before repair and
  zero afterwards, and Undo must restore exact bytes. Local proof must continue
  to say not sandbox tested; distributed sandbox acceptance is separate.

Additional image formats, multilingual/degraded scans, large corpora, languages,
memory limits and concurrent workloads need their own fixed representative
thresholds before P03/P04/P06 results are judged.

<a id="p01-proposed-contract"></a>
### Beta support contract — requester correction, 2026-09-18

Windows, macOS and Linux are required for the first downloadable Beta under the
[PRD](prd.md#release-bands). This supersedes the unaccepted Mac-requester/Mac-peer
proposal; no second Mac is a product prerequisite. P01 records baseline and exact
target profiles; P02–P13 implement and qualify them. P18/P22 expand coverage.

| OS family | Candidate / evidence | Required ownership |
|---|---|---|
| macOS | Requester reports Tahoe 26.7, M5, 16 GB unified memory; walkthrough below | Preserve working paths, qualify package/runtime and peer participation: P02–P13 |
| Windows | Windows 11 x86_64 inventory; current device/build readiness not re-observed | Portable document processing, safe Code access, credentials, runtime/receiver and installer: P02/P03/P06/P08/P09/P13 |
| Linux | Ubuntu 24.04.4 LTS x86_64 historical candidate; worker history is not desktop acceptance | Desktop document processing, credentials, runtime/receiver and installer: P02/P03/P06/P08/P09/P13 |

Exact Windows/Linux edition/build/hardware and minimum measured resources remain
qualification inputs. Supported sandbox capability is separate: P07 qualifies
one safe execution profile and P11 integrates its use. No unrestricted host
execution fallback. Missing implementation must not silently remove an OS.
P01 remains in progress until target profiles, representative thresholds and
gap ownership are accepted; it does not wait for every future feature to work.

<a id="p01-manual-20260918"></a>
### Manual Mac walkthrough — supplied 2026-09-18

Requester-reported device: macOS Tahoe 26.7, Apple M5, 16 GB unified memory.
Requester reports rebuilding with `./desktop/setup-macos.command` and testing
inside the app. Screenshots show `qwen3.5:4b-q4_K_M`; exact installed build/model
hash and current package/source parity were not independently established.
These are supplied observations, not an agent rerun or full platform acceptance.

| Check | Observed / reported result | Remaining action |
|---|---|---|
| Chat, cancellation, persistence | Requester reports accurate Chat, working Stop and retained history after reopening | Retain as reported baseline; no need to repeat solely for this documentation change |
| Scan to cited approval note | Screenshot shows refusal of a synthetic approval-note request, mentioning unreadable text and missing countersignature | P04/P06: qualify scan reading and legitimate draft generation; preserve uncertainty without refusing solely because the fixture is synthetic |
| Write Document follow-up | Screenshot labels an uncited model draft. Supplied DOCX text asserts reviewed/approved status, matching specifications and no further corrections; it lacks requested findings/citations | P06: fix explicit source reuse/grounding and unsupported approval claims. File creation is not task success; layout not verified here |
| Source selection | First screenshot visibly includes the scan only; SOP not shown. Follow-up shows no attachments | Two-source acceptance is incomplete. Check new attachments and explicit prior-source reuse; never silently read all historical files. General drafting without sources must not invent approval or imply source verification |
| Code modes / repeated selection | Requester reports only “Approve for me” works satisfactorily, repeated file selection in all modes and “Ask for approval” failing expectations | P06: reproduce exact interaction and correct shared selection/approval flow. Current source requires selected paths in every mode and resets on project/conversation changes; repeated reset within one conversation is not yet reproduced |
| Code Apply/Undo | Screenshot shows an Undo control and “Not sandbox tested — local device mode” | Exact diff, unchanged tests, six-test result and byte-for-byte Undo are unverified; do not mark Code acceptance passed |

The DOCX and screenshots are supplied review evidence, not committed fixtures or
application logs. No live app, model, sandbox or network verification ran during
this review. Embeddings/vector search (P16) improve retrieval; they cannot replace
Quartz/AppKit or fix unsupported claims by themselves. P06 must solve portable
PDF/image processing and grounded drafting independently of that upgrade.

### Next human checkpoint — current runtime evidence

For a necessary follow-up only; successful reported checks above need not be repeated.
**macOS requester, reported Tahoe 26.7 / M5 arm64 / zsh**, directory
`/Users/adityatadge/Documents/GitHub/AegisForge`. Quit any running Refinix first.
Use existing dependencies only and an isolated test database/code copy:

```zsh
cd /Users/adityatadge/Documents/GitHub/AegisForge
P01_WORKSPACE=$(mktemp -d /private/tmp/refinix-p01.XXXXXX)
mkdir "$P01_WORKSPACE/state"
cp -R fixtures/c07/code/pumpcheck "$P01_WORKSPACE/pumpcheck"
printf '%s\n' "$P01_WORKSPACE"
desktop/.venv/bin/python -B -m desktop --state "$P01_WORKSPACE/state/coordinator.sqlite3"
```

Keep `state` and `pumpcheck` as sibling directories: Code refuses any project
inside Refinix's state directory, or any project containing that directory.

Record Settings' actual engine/model/capability state first. If a prerequisite is
missing, return that failure; do not install/download or change the host. Exercise
the criteria above through Chat/Documents/Code, connecting only the disposable
`pumpcheck` copy and explicitly selecting **This device** for Code. Reopen using
only the last command in the same terminal, retaining the database under `state/`.
Return non-secret replies/errors, model/runtime identities, attempt/validation
states and synthetic artifact results. Do not return credentials, certificates,
private database contents or unrelated files.

Rollback: Quit/Command-Q cancels active test work and stops the app-owned local
service and any engine it started; a pre-existing engine is preserved. Canonical
workspace data is outside the test state. Retain the printed test directory for
review rather than deleting evidence during the checkpoint.

**Windows requester/execution candidates and Ubuntu requester/worker candidate:**
before giving setup or reconnection commands, obtain each actual checkout
directory, current OS/architecture, source commit/status and existing runtime
version/capabilities. The historical inventory does not supply current checkout
paths or worker state. No old TLS/IP/Kubernetes setup is implicitly resumed.

For the revised plan, P01 needs current baseline observations/gaps and requester
acceptance of the selected Beta profiles and fixture thresholds. Missing runtime
acceptance is then assigned explicitly to P03–P13, not represented as passed.
Basic Windows/Linux readiness is required in Band A; additional profiles follow in P18/P22; if a retained
worker is selected for Beta, its actual sandbox and integrated execution remain
P07/P11 blockers. This historical checkpoint does not authorise running it now.

<a id="beta-acceptance"></a>
## Beta 0.1 acceptance

These are **required future observations**, not results of this documentation
review. Test the real packaged candidates on the exact Windows, macOS and Linux support matrix.
Use [C07 fixtures](../fixtures/c07/provenance.json), the baseline criteria above
and proportionate existing checks. Freeze quality/latency/resource pass criteria
for each supported profile in P01/P04 before judging its results.

| Area / task | Required evidence before P14 |
|---|---|
| Install and lifecycle — P02/P03/P13 | Nondeveloper installs authenticated package without Python/model-server/queue/certificate commands; hardware detection, dependencies, permission failures, clean launch/relaunch and safe manual replacement/recovery. Record package/source parity and minimum measured resources |
| Persistent models — P04/P05 | After onboarding, browse installed/supported uninstalled entries and provenance/evidence; choose/download a second compatible model, cancel an incomplete download, import offline, reject corrupted/unsupported input, verify/self-test, enable/disable, preview removal consequences and remove safely. Reopen with choices/chats preserved; no silent public calls |
| Local identity — P06 | With peers absent and public egress blocked, real multi-turn Chat and selected scan/SOP produce a readable cited Word artifact; local Code produces the reviewable bounded patch with existing Apply/Undo safeguards and an honest no-sandbox label. Preserve units, missing readings, selected-source boundaries and history |
| Task/model routing — P04/P10 | At least two distinct qualified models over two appropriate task types; Auto chooses according to capabilities/evidence and actual availability/load. Record identity and reason, exercise override and incompatible/unavailable models. A duplicated label for the same weights or manual selection alone does not pass |
| Trusted execution — P08/P09/P11 | At least two real devices/instances using installed packages, graphical discovery and manual-address fallback, explicit two-sided pairing, authorised bounded remote inference, selected Chat context, receiver controls and revocation. Record actual OS/backend roles rather than hard-coded Mac/Ubuntu names |
| Capacity — P10 | A second overlapping request observes a busy/reserved receiver and queues or uses an eligible alternative; simultaneous requests cannot exceed the receiver-wide declared limit. Unknown/stale capacity is not free capacity. Advanced three-device fairness remains P15 |
| Validated Code — P07/P11 | Copy the synthetic code fixture; record before failures and successful repaired result, actual restricted command/stdout/stderr/exit/hash, network/host-file/resource enforcement and matching validation attempt before approved canonical write. Undo restores bytes. At least one sandbox profile passes; native unsupported ones remain unavailable |
| Failures/status — P12 | Cancel and restart; interrupt a paired target; deny an approval; submit invalid files/stale patches; remove/disable a required model safely; exhaust supported capacity. Jobs remain inspectable and no duplicate final write, cross-chat leak or developer database repair occurs. Show model/device/job/validation state accurately |
| Offline proof — P12 | Named enforcement and independent observation window over app/runtime/subprocess and LAN paths, including failure/restart. Retain safe metadata with build, model, device/interface/time and job references. Proof Cards distinguish blocked, observed-zero and unavailable; configuration/unit tests alone do not pass |
| Reviewer/publication — P14 | Operator follows the linked try-it guide, finds the artifact/diff/evidence and understands missing capabilities. Website/PPT Working now/Beta/Planned claims match the immutable artifact. Requester accepts result; publisher separately verifies actual download integrity/access |

No clean profile is accepted yet. A failed exposed workflow blocks that profile's
release until repaired or explicitly removed from the advertised profile without
losing the minimum Beta identity. Reviewers must see any required sandbox-peer
prerequisite before download. A narrow matrix is allowed within each required OS family; Windows, macOS and
Linux may not be dropped from Beta 0.1. Silently weaker safety or substituted
mock/model evidence is not allowed.

## Production acceptance

The gates below define the full production outcome retained for Bands B/C. They are **planned acceptance criteria**,
not results, deadlines or blanket claims of production readiness. The recorded
problem statement is in [docs/README.md](README.md): workstation/server operation,
model auto-selection, documents/images, sandboxed code and offline evidence are
baseline requirements; peer distribution is additional product innovation.

| Area | Required evidence |
|---|---|
| Installation | Clean supported Windows, macOS and Linux OS/architecture profiles can install and launch without terminal assistance, external language/runtime setup or a cloud account. Record signing/permissions, download size, free space, model choice, failures, upgrade/rollback and uninstall/data preservation |
| App publication and updates | On every production-supported platform, build real N and N+1 artifacts and prove install → use → upgrade before claiming production qualification. Verify explicit online check/download, authenticated offline import, interruption, wrong/tampered/stale packages, active jobs, migration failure/recovery and preservation of user work. Complete [production release acceptance](releases.md#production-release-acceptance); no silent network checks |
| Context and corpus lifecycle | Instructions/curated memory persist across restart; users inspect/edit/delete them; selected context respects permissions and token budgets. Legacy data migration preserves records and handles conflicting stores. Corpus change/deletion/revocation invalidates derived retrieval/context without treating document text as policy |
| KV cache and capacity | Compare cold/warm latency, peak memory and output quality with fixed model/runtime/context/concurrency. Exercise simultaneous admissions, low memory, cancellation, idle eviction, model/adapter changes and private-context isolation. Any cache quantisation/reuse/paging feature needs backend-specific correctness and resource evidence |
| Local operation | With public networking blocked, supported chat/reasoning, coding proposals, OCR/image/document understanding, local retrieval and file generation work using only installed dependencies. A standalone sandbox is proven separately on each advertised platform |
| Model selection | At least two qualified model options and two task types demonstrate automatic capability-aware choice, user override and unavailable-model handling. Record why selected, output quality and cost; one shared model alone does not prove model routing |
| Recommendation quality | Six recommendations then Show more; compatible user alternatives and oversized warnings; scores explain benchmarks/normalisation, measured versus estimated inputs, context/memory budget and power preference. No invented percentage accuracy |
| RAG and documents | Public/licensed or synthetic scanned reports and SOP-like fixtures exercise extraction, fields/units, citations, missing evidence and document generation. Measure retrieval recall/relevance and grounded answer quality separately; inspect generated files for readability and layout |
| Safe Code | Reviewable patch, least-privilege approved files, isolated execution, no network/host secrets, resource bounds, validation evidence and authorised canonical writes. Denied/expired approval and stale patch cannot write |
| Peer interoperability | Supported OSes each request and receive real work. A homogeneous peer group works without a Linux member. Guided pairing, unreachable discovery fallback, explicit trust, pause/revoke and receiver notification are observable |
| Concurrent placement | Three devices receive two independent chat requests (Code plus Chat); the second sees current reservations. Test differing installed models, busy/low-memory nodes and simultaneous requests from different coordinators; receiver never over-admits |
| Isolation and recovery | No cross-chat or cross-user context/artifact leakage; enforce permission scope before retrieval/dispatch. Disconnect, crash, cancellation, stale leases and retries reconcile attempts and cannot duplicate canonical writes |
| Managed deployment | A private server executes using the common API; users/admins have distinct authority, quotas and corpus access. Organisation corpus updates/deletion/revocation invalidate indexes and caches; optional Kubernetes is not a client dependency |
| Offline proof | Observe app, subprocesses, runtime, retrieval, discovery and worker traffic under public-network enforcement. Permit only intended authenticated LAN traffic and bounded local discovery. Repeat relevant failures/restarts; logs alone do not establish blocked egress |
| Usability and transparency | Nontechnical operator installs, chooses a model, sends work, connects a peer, cancels and finds artifacts through UI. Status shows actual model/device/stage; receiver can see and stop remote work; absent sensors/evidence remain unavailable |

Publish evidence per **OS version/edition, architecture, runtime build, model hash,
backend and enabled capability**. Exact quality/speed thresholds and score weights
must be fixed for each representative benchmark before results are judged. Hardware
specifications and a small smoke prompt cannot establish broad accuracy. A confidential
MRPL dataset becoming available is an assumption, not a prerequisite or promise.

Optional model adaptation is a separate acceptance track, not a first-publication
gate. Require opt-in/provenance, held-out base-versus-adapter comparisons, unrelated
capability regressions, privacy tests, resource cost and disable/revert evidence
before enabling it. Reward or training-loss improvement alone is insufficient;
see [model adaptation](model-catalog.md#11-personalisation-and-optional-model-adaptation).

## Historical evaluation plan and measurements

The numbered sections below retain prototype acceptance plans and dated measurements.
Their old stage names, fixed device roles and deferred choices do not supersede
production acceptance above. Retain evidence without silently marking later work
passed or treating an old device handoff as authorisation.

## 1. Evidence labels

Use only:

- Planned: accepted requirement with no implementation evidence
- Prototyped: a narrow path ran but does not meet the full acceptance contract
- Verified: the documented check ran on the stated environment and passed
- Deferred: intentionally outside the current release
- Rejected: evaluated and intentionally not selected

Record the date, device, operating system, runtime, model revision, command or
procedure, input class, result, and known limitations. Another agent's summary,
a screenshot without provenance, or a static code inspection is not execution
evidence.

## 2. Task acceptance sequence

The purpose of the alpha is to answer the risks that could kill the product,
not to imitate every ChatGPT feature.

Execute these outcomes through the [numbered tasks and named human
checkpoints](../tasks.md#numbered-execution-tasks). The implementer builds, the reviewer checks the actual diff and
results, and execution stops for the named human action. A reported installation
or code-review pass does not satisfy a runtime gate. Verify the returned evidence
before continuing within the authorised scope.

Choose focused checks before each chunk. Reuse evidence only when its source and
environment still apply; rerun affected checks after changes and the required
end-to-end path at task acceptance gates. Add broader checks only for a concrete remaining
risk. After each build/review cycle, explain what was built, what was observed,
what remains unverified and the next named action using the
[team report](archive/prototype-task-record.md#verification-and-team-explanation).

### C05: Contracts and local execution

- Freeze the node, job, attempt, event, approval, HTTPS, Redis, and proof
  contracts.
- Pin K3s, Redis 7.2.x, base-image, worker-image, runtime, and model evidence.
- Start one single-node K3s cluster on the authorised Ubuntu host confirmed at
  the human checkpoint — the **Ubuntu worker** in the first configuration.
- Deploy Redis behind ClusterIP and the Docker-built worker behind a Kubernetes
  Service.
- Complete one real model response from a Ready worker Pod.
- Persist the job and attempt in coordinator SQLite and show it in the smallest
  local browser UI.

Exit evidence:

- model, image, K3s, Redis, and dependency source/licence/revision recorded;
- Pod, Service, runtime, and prompt are reproducible;
- no mocked inference in the claimed path.

### C06: Distributed execution

- Connect worker API and executor Pods through Redis Streams.
- Add bounded retention, acknowledgement, pending-work recovery, cancellation,
  heartbeats, and leases.
- Authenticate the Mac coordinator to the worker Service over HTTPS.
- Route one real prompt through the Service and Redis to an executor Pod.
- Stream events back and show the request, model, Pod, queue, and routing reason.
- Complete the smallest guided preflight that selects the curated manifest,
  verifies dependencies, and runs the real self-test.
- Stop the cluster and prove the Mac's canonical SQLite history remains usable.

Exit evidence:

- reproducible Mac-to-Service-to-Redis-to-Pod-to-Mac path;
- bounded request and streamed response captured;
- Redis or cluster loss does not lose canonical history.

### C09: Signature workflows

- Complete the fixed Documents path from scan to page-linked extraction,
  grounded drafting, and validated Word artifact.
- Complete the fixed Code path from bounded repository context to patch.
- Run code validation as a restricted short-lived Kubernetes Job Pod.
- Preserve hashes, uncertainty, command output, exit status, and cleanup state.
- Use the same Service, Redis, event, and approval contracts for both paths.

Exit evidence:

- one openable cited Word artifact;
- one applicable patch with observed sandbox evidence;
- no direct canonical write from a worker or Job Pod.

### C11: Concurrency, approvals and offline evidence

- Run Documents and Code attempts concurrently through separate Redis consumers
  and Pods.
- Enforce approval before canonical writes and make retries idempotent.
- Apply and verify default-deny Pod egress plus required cluster/LAN allowances.
- Produce Proof Cards from SQLite, Redis, Kubernetes, model, validation,
  integrity, approval, and network observations.
- Record sequential and concurrent timing honestly.

Exit evidence:

- both real artifacts complete concurrently;
- denial writes nothing and retry creates no duplicate final write;
- the real run records no observed public outbound flow in the named window.

### C13: Recovery and candidate acceptance

- Enforce or physically isolate public egress while preserving the trusted LAN.
- Run the real signature workflow.
- Capture trustworthy network, device, model, tool, integrity, and approval
  evidence.
- Exercise cancellation or one worker interruption.
- Exercise executor-Pod loss, Redis restart, and cluster loss.
- Complete third-party notices for selected components.
- Replace projected numbers with measured results.
- Rehearse and record a backup demonstration.

Exit evidence:

- reproducible offline run;
- per-job Proof Card;
- benchmark table and limitations;
- no unfinished feature presented as working.

When a task passes, proceed to the next eligible, authorised task after
clearing its human prerequisites. Only after C09 passes may the team add the
bounded image-understanding and calculation-with-steps stretch; only after C11
passes may it add a second executor replica. Additional scope needs requester
approval. Do not add another
framework, cluster, broker, runtime, or product surface.

## 3. Alpha acceptance

- [ ] The authoritative SIH26117 wording and IP/submission terms are retained.
- [ ] One installation creates a local workspace without a permanent role
      choice.
- [ ] Guided setup selects, installs or imports, verifies, and self-tests one
      real main engine.
- [ ] A real local chat completes.
- [ ] The pinned Docker worker image runs in a Ready Kubernetes-managed Pod.
- [ ] A Kubernetes Service exposes only the authenticated worker API to the
      trusted LAN; Redis remains cluster-internal.
- [ ] Redis dispatches one bounded attempt to an executor and reports queue,
      pending, acknowledgement, heartbeat, and cancellation state.
- [ ] One real prompt runs through the Kubernetes Service and streams back.
- [ ] The UI or logs show original request, device, model, route, and status.
- [ ] Stopping Redis or the cluster leaves canonical SQLite history intact.
- [ ] One bounded agent workflow produces a validated output.
- [ ] Consequential final write requires a recorded approval.
- [ ] Runtime endpoints and public-egress evidence are documented honestly.
- [ ] Repository instructions reproduce the claimed path.

## 4. Finals acceptance

- [ ] Chat, Documents, Code, and Control Center use one harness.
- [ ] The same installation works standalone and can use trusted workers.
- [ ] At least two task types route automatically.
- [ ] Documents and Code jobs run concurrently on different eligible nodes.
- [ ] OCR preserves source hash, page mapping, and uncertainty.
- [ ] Local retrieval returns page or section citations.
- [ ] The approval note opens as a valid Word artifact.
- [ ] Code execution uses a bounded network-disabled workspace.
- [ ] The patch, validation command, output, and exit status are returned.
- [ ] The coordinator performs no duplicate final write after retry.
- [ ] Pairing and revocation reject an invalidated worker.
- [ ] No external inference occurs during the offline evidence window.
- [ ] Installed models expose source, licence, revision, and integrity state.
- [ ] The Control Center distinguishes trusted LAN traffic from public egress.

## 5. Measurement plan

Initial targets are hypotheses:

| ID | Measure | Initial target |
|---|---|---:|
| M-01 | External inference calls in offline demo | 0 |
| M-02 | Corrupted file transfers accepted | 0 |
| M-03 | Real paired workers | At least 1 alpha, 2 where available for finals |
| M-04 | Concurrent independent workflow types | At least 2 for finals |
| M-05 | Routing accuracy on curated examples | At least 90% |
| M-06 | Worker-loss detection | Under 5 seconds |
| M-07 | Duplicate final writes after retry | 0 |
| M-08 | Distributed makespan improvement over sequential baseline | Positive and reported honestly |
| M-09 | Ready worker Pods behind the Service | At least 1 |
| M-10 | Canonical records lost after Redis restart | 0 |
| M-11 | Redis pending attempt reclaimed after executor loss | 1 fixed failure fixture succeeds |

Measurement rules:

- use the same task set for standalone and distributed comparison;
- record time to first output and end-to-end completion separately;
- report cold and warm behaviour separately;
- record queue time, RAM, VRAM, and temperature where reliable;
- score code, OCR, retrieval, and document quality separately;
- do not publish a universal AI accuracy number;
- do not claim energy, thermal, or cost improvement without comparable evidence;
- report a slower distributed result if that is what occurred.

## 5.1 OD-03 runtime comparison

OD-03 asks whether a direct engine provides enough benefit to justify another
adapter. The recorded macOS comparison uses **Ollama's bundled `llama-server`**,
not a separately installed upstream llama.cpp release. It measures one fixed
prompt and does not isolate wrapper overhead or rank runtimes generally.

**Method** — [`scripts/od03_runtime_comparison.py`](../scripts/od03_runtime_comparison.py),
standard library only, no benchmark framework. It never starts a service: if the
target server is not already listening it exits with instructions.

Requested settings for the macOS comparison:

| Setting | Value |
|---|---|
| Model file | the same GGUF — the Ollama blob `sha256:81fb60c7…` is a real GGUF, so `llama-server -m <blob path>` loads identical weights with no second download |
| Request shape | a **chat** request on both sides — Ollama `/api/chat`, llama-server `/v1/chat/completions` — so the model's own chat template is applied to both. A raw completion against a templated chat is not a comparison. |
| Prompt | one fixed user message, compiled into the script |
| Context | `num_ctx` / `-c` 4096 — the value held constant for **this comparison**; the coordinator now runs 8192, measured separately in [§5.2](#52-context-window-sizing--macos-coordinator-2026-09-04) |
| Output limit | `num_predict` / `max_tokens` 128 |
| Sampling | `temperature` 0, `seed` 42; direct-server launch also sets `top_k` 20, `top_p` 0.95, `min_p` 0, `presence_penalty` 1.5 to match the selected model's settings |
| GPU allocation | macOS direct-server launch requests `--n-gpu-layers all`; Ollama chooses placement. Ubuntu's separately recorded partial GPU allocation is not held equal to the Mac. |
| Thinking | off on both — Ollama `think: false`, llama-server `chat_template_kwargs.enable_thinking: false`. Separate reasoning output or a leaked thinking marker flags the run as non-comparable; TTFT includes the first token from either channel. |
| Prompt cache | each runtime's **default**, untouched. Disabling it on one side only would make the warm runs measure different work. |

The exact request body is echoed into the result JSON. Server launch settings
are recorded below because they cannot be inferred from that body alone.

**Failures cannot become evidence.** A malformed line, a streaming error object,
a missing terminal record or a missing metric aborts the run with a non-zero
exit; no partial result reaches a median.
[`scripts/test_od03_parser.py`](../scripts/test_od03_parser.py) exercises those
paths offline, including separate reasoning and absent or invalid generation
timing — no server, no model.

**Cold and warm are separated.** `--unload-first` makes a preparation inference
with `keep_alive: 0`, waits three seconds, then records one cold and three warm
requests with `keep_alive: "10m"`. The preparation request is not in the four
recorded runs. A forced model reload is not a cold operating-system disk cache.
For the direct server, model loading occurs before requests; its first-request
TTFT excludes model load and cannot be compared to Ollama's cold figure.

**Cancellation was not exercised in C02.** The recorded requests demonstrate
streaming with configured context and output limits; they do not demonstrate
user cancellation, runtime work stopping after a disconnect, or a persisted
cancelled attempt. The script's transport timeout is not cancellation evidence.
Application cancellation is unimplemented; C06 / AF-005–AF-007 owns its
implementation and the device cancel exercise in [tasks.md](../tasks.md#numbered-execution-tasks).

**Provenance:** the earlier coordinator Ollama measurement is retained from
the C02 execution record. The Ubuntu inventory, checksums, inference JSON and
follow-up memory output, plus the Mac direct-engine startup log and inference
JSON, were returned by the requester on 2026-09-03. Closeout reviewed those
outputs without repeating inference or querying either live service.

### Measured — Ollama on the macOS coordinator, 2026-09-03

`ollama` 0.32.14, `qwen3.5:4b-q4_K_M`, four runs through `/api/chat`.

| Phase | Time to first token | Generation | Model load | Prompt eval |
|---|---:|---:|---:|---:|
| Cold — `cold_after_forced_unload`, **includes model load** | **2.504 s** | 37.8 tok/s | 2.300 s | 0.199 s |
| Warm (median of 3) | **0.225 s** | 37.9 tok/s | 0.175 s | 0.048 s |

All four runs returned 89 tokens / 598 characters, `done_reason: stop`, and
**one** response SHA-256 (`c400b210dc824a26…`) — so the output was byte-identical,
established by hash rather than inferred from counts. Thinking was suppressed on
every run. The historical report called its RSS samples 3.83 → 3.90 GB; the old
collector actually selected the largest name-matched process and divided KiB
by 1024. Those samples are not aggregate or peak RAM and are excluded from
memory comparisons. VRAM is not separately reported on Apple unified memory.

Generation speed is effectively identical cold and warm, so the whole 2.279 s
time-to-first-token penalty sits before generation: **93.2 % is model load
(2.124 s) and 6.6 % is prompt evaluation (0.151 s)**, an ~11.1× difference.

An earlier run of this measurement used the untemplated `/api/generate` endpoint
and recorded ~29.3 tok/s. It is superseded, not averaged in: it did not hold the
chat template constant, so it is not comparable to a `llama-server` chat request.

Also observed on this device: the server listens on `127.0.0.1:11434` only
(`lsof`/`netstat`), not on a wildcard address.

### Measured — Ollama on the Ubuntu worker, 2026-09-03

Ollama **0.33.2**, Ubuntu 24.04.4 LTS / Linux `7.0.0-30-generic`, x86_64,
Python **3.12.3**, RTX 2050 4096 MiB. JSON timestamp
`2026-09-03T09:39:24Z`; model and settings match the catalogue entry.

| Recorded request | TTFT (s) | Generation (tok/s) | Load (s) | Prompt eval (s) | Generation duration (s) | Total (s) |
|---|---:|---:|---:|---:|---:|---:|
| Cold after forced unload, includes load | 16.0149 | 10.16 | 14.6906 | 1.3155 | 8.7597 | 24.7737 |
| Warm 1 | 0.5012 | 10.28 | 0.0029 | 0.3151 | 8.6534 | 9.1532 |
| Warm 2 | 0.3267 | 10.14 | 0.0025 | 0.3168 | 8.7742 | 9.1000 |
| Warm 3 | 0.3369 | 9.84 | 0.0022 | 0.3266 | 9.0451 | 9.3808 |
| Warm median | **0.3369** | **10.14** | — | — | — | — |

All four returned 89 tokens / 605 characters, no reported thinking output,
nonempty visible output and `done_reason: stop`. All share SHA-256
`6264a0c46c55fc537bba65a00f2bbace642b6b98fe3938c7e3e0c3024858aab9`.
The raw response text was not supplied for quality scoring. This hash differs
from the Mac output; determinism is observed within each run set only.

The follow-up `/api/ps` reported the catalogue manifest digest, context 4096,
model allocation **3,727,561,846 bytes** and GPU allocation
**2,217,780,180 bytes**. These are runtime allocation fields, not process RSS
or an offloaded-layer count. The accompanying process snapshot was:

| Process | PID / parent PID | RSS from `ps` (KiB) | RSS (MiB) |
|---|---|---:|---:|
| Ollama daemon | 2052 / 1 | 56,004 | 54.7 |
| Model runner (`llama-server`) | 17155 / 2052 | 2,209,224 | 2157.4 |

The benchmark's older `rss_mb: 69.7` measured only a daemon candidate and is
**invalid as runner or total RAM**. Its NVIDIA sample reported the runner at
2948 MiB, taken at a different time from `/api/ps`; do not equate these memory
categories or add them. The repaired collector emits `processes` with PID,
parent PID, name, `rss_mib` and PID-matched `vram_mib`. It lists all matching
runtime candidates, does not attribute them to an endpoint or sum shared
memory, and leaves unavailable metrics null. It replaces the misleading
top-level `rss_mb` and raw-string `vram_mb` fields for future runs.

### Measured — bundled engine on the macOS coordinator, 2026-09-03

macOS **26.6.2**, arm64, Python **3.14.6**. The installed binary is
`/Applications/Ollama.app/Contents/Resources/llama-server`, from Ollama
**0.32.14**. Its version output reports **0.1.0-dev**, build **1**, commit
**7e4c0a968**, AppleClang 21.0.0.21000099 / Darwin arm64; binary SHA-256 is
`05b7f7f8a4047f3012ce094b6e78a39a9c737a0b221524a148021c210447b85d`.
This fingerprints the installed MIT-licensed bundle, not an independently
verified upstream release. No runtime download, build or local modification
was needed; the model's Apache-2.0 provenance remains in the catalogue.

JSON timestamp `2026-09-03T09:57:13Z`:

| Recorded request | TTFT (s) | Generation (tok/s) | Prompt (ms) | Generation (ms) | Cached prompt tokens |
|---|---:|---:|---:|---:|---:|
| First after server start, **excludes load** | 0.1824 | 36.67 | 173.503 | 2399.867 | 0 |
| Warm 1 | 0.0988 | 36.50 | 58.744 | 2411.145 | 24 |
| Warm 2 | 0.0502 | 36.61 | 48.646 | 2403.832 | 24 |
| Warm 3 | 0.0495 | 36.43 | 48.131 | 2415.372 | 24 |
| Warm median | **0.0502** | **36.50** | — | — | — |

Each response has 89 completion tokens, 28 prompt tokens, 598 visible
characters, zero reported reasoning and no thinking markers. All four share
SHA-256 `c400b210dc824a2699b26f8a815e7e3d65bdd8a4de91d163421a1da7f9d5c5ba`.
The earlier Mac Ollama record retained that prefix and matching counts; full
cross-runtime identity is not independently established by the prefix alone.
Legacy process samples were 3213.5 and 3368.2 MiB, not aggregate or peak RAM.

The startup log showed readiness at elapsed **1.301843 s**, but the first
request arrived at **44.377747 s** after a manual terminal switch. There is no
controlled startup-to-first-answer result; neither adding readiness to request
TTFT nor including the operator's delay would establish one. The log also
records Ollama-format qwen35 compatibility fixes, disabled mmap for transformed
tensors, token metadata overrides and unused tensors. Successful requests
demonstrate this bounded path, not general model correctness.

Warm direct-engine TTFT was lower than the earlier Mac Ollama median by
174.8 ms, while generation stayed roughly 36–38 tok/s. Warm direct requests
cached 24 of 28 prompt tokens, so this is repeated-prompt latency, not latency
for new prompts. Different runtime implementations, versions across devices
and a small sequential sample limit broader conclusions.

### Reproduce the recorded path at an authorised human checkpoint

These are retained reproduction instructions, **not a request to rerun C02**.
The requester stopped the temporary Mac server with Ctrl+C. The deferred
comparisons require a future approved measurement if they become necessary.

**Ubuntu worker — bash, `~/SIH/AegisForge`**, with existing loopback Ollama and
the catalogue model already hash-checked:

```bash
cd ~/SIH/AegisForge &&
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
python3 -B scripts/od03_runtime_comparison.py \
  --target ollama --model qwen3.5:4b-q4_K_M --unload-first
```

**macOS coordinator — zsh, `/Users/adityatadge/Documents/GitHub/AegisForge`.**
For that device's Ollama baseline:

```zsh
cd /Users/adityatadge/Documents/GitHub/AegisForge &&
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
python3 -B scripts/od03_runtime_comparison.py \
  --target ollama --model qwen3.5:4b-q4_K_M --unload-first
```

To reproduce the direct-engine run, first check
`lsof -nP -iTCP:8080 -sTCP:LISTEN`; proceed only
if the command succeeds with no listener or exits 1 with no output. Any
listener or other error requires inspection. Do not terminate another process.
In one terminal, release Ollama's model, then launch the installed bundle:

```zsh
curl -q --noproxy '*' --fail --silent --show-error --max-time 30 \
  http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.5:4b-q4_K_M","keep_alive":0,"stream":false}' &&
/Applications/Ollama.app/Contents/Resources/llama-server \
  --model "$HOME/.ollama/models/blobs/sha256-81fb60c7daa80fc1123380b98970b320ae233409f0f71a72ed7b9b0d62f40490" \
  --host 127.0.0.1 --port 8080 \
  --cors-origins localhost --no-cors-credentials \
  --ctx-size 4096 --parallel 1 --n-gpu-layers all \
  --temp 0 --seed 42 --top-k 20 --top-p 0.95 --min-p 0 \
  --presence-penalty 1.5 --reasoning off \
  --sse-ping-interval -1 --perf --offline --no-ui
```

Wait for the listening message. In a second terminal:

```zsh
cd /Users/adityatadge/Documents/GitHub/AegisForge &&
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
python3 -B scripts/od03_runtime_comparison.py --target llama-server
```

Return startup/version output and the full JSON, including errors. Four
successful recorded requests should have nonempty visible output, suppressed
thinking and valid timings. Stop the temporary server with Ctrl+C afterward;
Ollama loads its model again on the next authorised request. These flags are
for this measured bundle, not unverified Ubuntu or upstream builds.

### Finding that changes the bounded settings

`qwen3.5:4b-q4_K_M` is a **thinking model**. With thinking left on it spent the
whole output budget in its reasoning channel and returned an **empty** visible
answer — at `num_predict` 128 *and* at 512, both stopping on `length`. With
`think: false` the same prompt completed in **89 tokens** and stopped naturally.

A bounded output limit is therefore not sufficient on its own: `think: false`
is required, or a C03 job would report success while returning nothing. This is
recorded in the [bounded execution settings](model-catalog.md#bounded-execution-settings-for-the-first-path).

### Deferred by requester at C02 closeout, 2026-09-03

| Run | Device | Evidence still missing |
|---|---|---|
| Direct-engine comparison | Ubuntu worker | Direct-launch compatibility, controlled allocation and timing; its bundled runner exists, but was not tested independently. Port 8080 was occupied in inventory. |
| Comparable cold-start figure | macOS coordinator / Ubuntu worker | Controlled server-start-to-first-answer timing, including model loading, without a manual gap |

**Ollama remains selected.** These explicit deferrals do not block C02
acceptance and do not become successful measurements. A separate upstream
llama.cpp release, Windows, output quality, application persistence, container
GPU access, trusted-LAN pairing and zero-egress operation are not established
by the native runtime checks above. C03 begins only after closeout acceptance
and its own authorisation.

## 5.2 Context window sizing — macOS coordinator, 2026-09-04

Request-local settings only; no service or install was changed. Same installed
model, synthetic near-boundary input with a fact planted at the start.

| Setting | Prompt tokens | Cold TTFT | Warm TTFT | Resident bytes | Early fact retrieved |
|---|---:|---:|---:|---:|---|
| `num_ctx` 4096 | 919 | 3.796 s | 0.196 s | 3,144,910,109 | yes |
| `num_ctx` 8192 | 919 | 3.409 s | 0.198 s | 3,375,617,800 | yes |
| `num_ctx` 8192, larger input | 3052 | 4.543 s | 0.203 s | 3,375,617,800 | yes |

**8192 adopted for the macOS coordinator.** It costs about **220 MiB** more
resident memory, warm time-to-first-token is unchanged, and a fact at the start
of a 3052-token prompt was still answerable. The Ubuntu worker keeps 4096 until
it is measured at its own device checkpoint; the Mac repair was not held for it.

### Context selection observed end to end

A seven-turn synthetic conversation on the coordinator drove the selector past
its budget. Estimated input rose 35 → 1690 → 3376 → 5063 → 5132 of a
5168-token budget, then omission began: 4 messages omitted at turn 6, 6 at
turn 7, each with a visible notice. Saved history stayed at 16 messages
throughout — nothing was trimmed from storage.

When the turn carrying a planted fact had been omitted, the model answered
**"I no longer have it"** rather than inventing the value. That is the intended
behaviour: omission is visible and its consequence is honest.

**Estimate versus measurement.** The pre-flight estimate is characters ÷ 3.0
and was conservative for this fixture: at turn 6 it predicted 5053 tokens where
the runtime reported **2832**. This is not a bound for other inputs or scripts.
Runtime-reported prompt and output counts are recorded separately as measured
values; the enforcement check below covers underestimates.

## 5.3 C03 review repairs — macOS coordinator, 2026-09-04

Observed using the installed `qwen3.5:4b-q4_K_M` GGUF, Ollama **0.32.14**, and
disposable SQLite state. Reproduce from the repository with:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ./.venv/bin/python -m backend.coordinator.check_runtime_context
```

The script makes three explicit local-model requests with `num_ctx: 8192`,
`num_predict: 2048`, `think: false`, `truncate: false`, `shift: false` and the
existing request-local `keep_alive: "10m"`. It installs nothing and does not
read or write the user's chat database.

| Synthetic case | Observed result | Coordinator elapsed |
|---|---|---:|
| Early label before 5,000 CJK padding characters | 5,034 prompt tokens, 5 output tokens; correct label retained, normal completion | 9.618 s |
| 12,000 CJK characters accepted by the selection estimate | Runtime rejected input; no output or assistant message; visible shorten/new-chat error | 0.250 s |
| Counting after near-window CJK padding | 8,042 prompt + 150 output = 8,192; `length`, classified **context**; partial reply saved and job marked incomplete/failed | 6.191 s |

A direct rejection probe reported **12,012 actual prompt tokens**, exceeding
8,192. This demonstrates why the character heuristic is not enforcement.
The loaded runner reported context 8,192, resident allocation **3,375,617,800
bytes**, and model digest
`2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
These are bounded functional checks, not new cold-start, quality or memory-pressure benchmarks.

Offline regressions cover draft response/write ordering and newer typing,
failed sends, atomic submit/delete exclusion, HTTP 409 for unfinished states,
Unicode download headers and combining marks, and output/context limit notices.
Browser checks on an isolated server observed draft isolation and reload
recovery, disabled busy deletion, Cancel focused in the native confirmation,
cancel preserving history, and confirmed deletion remaining absent after reload
with the other chat intact. Both Marathi Markdown and text downloads returned
HTTP 200 with the correct filename and no unsent draft content.

This evidence applies to the macOS coordinator. It does not accept C03 on behalf
of the requester, qualify Ubuntu, or advance C04. See the
[repair handoff](archive/c03-repair-handoff.md) for exact verification and Git paths.

## 6. Demonstration

### Preparation

1. Show the separate public distribution surface and release checksum only if
   they exist.
2. Show the pinned Docker image, Ready Pods, Kubernetes Services, Redis licence,
   installed model, and self-test state.
3. Confirm Redis has no LAN-exposed Service and the worker API requires the
   paired credential.
4. Disconnect or block public Internet while preserving the trusted LAN.
5. Start the evidence window.

### Standalone

1. Open the application in the local workspace.
2. Show Chat, Documents, Code, and Control Center.
3. Run the selected baseline task on this device.
4. Show the model, device, job events, and measured resource use.

### Trusted compute

1. Open Control Center and show paired devices and capabilities.
2. Start a scanned-report workflow.
3. Start a coding task while the document workflow runs.
4. Show the execution choices and automatic routing reasons.
5. Show streamed progress in the correct surfaces.
6. Open the generated cited document.
7. Inspect the returned code patch and validation.
8. Approve or deny the controlled final-write step.

### Sovereignty and resilience

1. Show the enforcing layer and network observation interval.
2. Show trusted LAN connections separately from public egress.
3. Open the job Proof Cards.
4. Disconnect one non-critical worker.
5. Show a safe requeue or recoverable failure without duplicate final output.

## 7. Sovereign Proof Card

Each demonstrated job records:

- workflow, job, step, and attempt IDs;
- original-request hash or approved reference;
- device identity, model manifest, and routing reason;
- tool and validation events;
- input and artifact hashes;
- approvals and final-write state;
- enforcement and observation method;
- public-egress and trusted-LAN observations;
- start/end times and evidence limitations.

It proves only the recorded job and observation window.

## 8. Implementation areas

The six implementation areas are:

1. Frozen contracts, coordinator SQLite, routing, and integration
2. Docker worker, model runtime, Redis consumer, and SSE
3. K3s, Pods, Services, NetworkPolicies, and sandbox Jobs
4. Local browser UI, Control Center, and product acceptance
5. Documents/OCR/retrieval and Code/patch validation
6. Fixtures, contract checks, failure drills, proof, and demo

Anyone may implement any area. Follow the numbered task sequence, use the
shared contracts, review the combined changes, and stop at named human
checkpoints. A person is named for a human action or device access, not exclusive
code ownership. Do not create empty components merely to give someone a folder.

## 9. Major risks

| Risk | Response |
|---|---|
| Product becomes only a networking demo | Complete one real agentic artifact workflow |
| P0 scope expands again | Treat the PRD outcome table as the release boundary |
| Infrastructure displaces workflow work | Use one single-node K3s host; no Helm, operator, service mesh, HA, or multi-node cluster |
| Redis becomes a second database | Keep canonical state in SQLite; use expiring Redis coordination state only |
| Agent count creates incompatible implementations | Use reviewed shared contracts, integrate accepted tasks and verify named human checkpoints |
| Worker Service exposes confidential traffic | Authenticated HTTPS only; Redis stays ClusterIP; verify NetworkPolicy and host firewall behaviour |
| Kubernetes Job is mistaken for a complete sandbox | Require observed non-root, seccomp, capability, path, resource, deadline, and egress checks |
| Setup forces unnecessary downloads | Resolve dependencies only for enabled capabilities |
| Main model is too weak | Benchmark the actual tasks before polishing UI |
| Cross-platform runtime differs | Prove one runtime path, add one fallback only for a measured blocker |
| Pairing becomes state migration | Keep pairing additive; defer coordinator transfer |
| Dashboard displays claims instead of evidence | Bind every status to an identified source and interval |
| Wi-Fi or worker fails in demo | Prefer wired links where available and record a backup run |
| Cold model loading erases concurrency benefit | Report cold/warm separately and preload only when disclosed |
| Confidential content leaks into logs | Metadata-only defaults and synthetic demo inputs |
| Open-source reuse creates licence risk | Record source, pin, licence, network behaviour, and local changes |
| Installer work consumes the prototype | Package only after the real harness path works |

## 10. Research gates

Research only questions that materially affect feasibility:

- official SIH26117 wording, evaluation expectations, and IP terms;
- one runtime across macOS, Windows, and Linux;
- main and specialist model correctness on the chosen demo inputs;
- RAM, VRAM, storage, cold-load time, and sustained thermals;
- pairing credential storage and encrypted LAN transport;
- platform sandbox behaviour;
- pinned K3s, Kubernetes workload, Docker image, and Redis 7.2.x compatibility
  and licences;
- Service exposure, Redis isolation, NetworkPolicy enforcement, and Pod
  security on the Ubuntu worker;
- connected and air-gapped model installation;
- trustworthy public-egress enforcement and observation;
- dependency and model licences.

The user or requester independently verifies the final result before the project
claims completion.

## 11. Problem-statement coverage

The SIH26117 transcription is retained in [README.md](README.md). Current scope
comes from the [PRD](prd.md#release-bands), sequencing from
[P01–P26](../tasks.md#numbered-execution-tasks), and evidence from the
[source audit](#beta-source-audit) and [manual baseline](#p01-manual-20260918).
Archived AF/C IDs are not active task owners.

**Implemented** describes source/prototype capability. **Runtime-qualified**
requires observed representative behaviour on the named build/profile.
**Release-accepted** requires the integrated package and requester release gate.
None implies the next; historical component checks remain valid only for their
recorded scope. No row below is release-accepted yet.

### Expected Solution

| Requirement | Current implementation | Runtime qualification | Release acceptance / task owner |
|---|---|---|---|
| Local workstation deployment | Desktop shell, local adapter and Mac bundle exist; Windows/Linux portability incomplete | Mac Chat/Stop/persistence reported; clean-device installer/runtime profiles unqualified | Pending P02/P03/P13/P14 on Windows, macOS and Linux |
| Automatic model selection across two task types | Per-workflow model selection exists; Auto and qualified routing remain gaps | Two distinct models/task types and actual scheduling not qualified | Pending P04/P05/P10/P14 |
| Scan plus SOP to cited Word approval note | OCR, retrieval and document writers exist | Supplied Mac run failed useful grounded output; full two-source fixture not demonstrated | Pending P04/P06/P14; refusal, source reuse and fabricated approval claims must be resolved |
| Code run and verified in a sandbox | Bounded proposals, Apply/Undo and remote validation Job paths exist | Local screenshot says not sandbox tested; current real isolation and integrated validation remain unqualified | Pending P06/P07/P11/P14 |
| Image/scanned document understanding | Vision/OCR path exists, including typed transcription/unreadable/refusal handling | Broad OCR quality unqualified; synthetic scan attempt is not a passing benchmark | Pending P04/P06/P14 for advertised inputs |
| Logs/monitor showing no external calls | Network policies and Proof Card schema/UI exist | Live per-job collector not proven; unavailable network fields are not zero egress | Pending P12/P14 with named observer, interface, interval and allowed LAN traffic |

### Additional description coverage and later scope

| Requirement | Current implementation / limit | Qualification and active owner |
|---|---|---|
| Drawings, photographs, P&IDs and handwriting | Image/OCR path is a prototype base, not qualified industrial interpretation or symbol detection | P04/P06 only for explicitly supported fixtures; specialised coverage P17/P25 |
| Spreadsheet work and Excel output | XLSX reading/writing exists; cached formula values are not a calculation engine | Existing advertised artifact paths P06; new calculation/tool capability requires explicit scope and evidence under P25 |
| PowerPoint output | No qualified presentation-generation workflow established | Conditional capability work P25; do not advertise as working |
| Calculations with steps | No general verified calculation engine established by document generation | P06 must not fabricate results; additional executable calculation capability P25 |
| Multi-step work | Bounded document/Code workflows and repair paths exist | P06/P11 qualify real end-to-end behaviour; no claim of unrestricted autonomous planning |
| Multiple models, addable later | Inventory and per-workflow selection exist; complete catalogue lifecycle missing | P04/P05 minimum Beta set; P17 broader models and calibrated ranking |
| Grounding in manuals/SOPs/correspondence | Selected-source extraction, FTS5 retrieval and citation checks exist | P06 qualifies grounded output; P16 hybrid retrieval/personal context; P21 governed shared corpus |
| Multilingual industrial interaction | No broad language quality qualification established | P17/P25 named language fixtures, supported models and acceptance evidence |

## 12. Mentor implementation-direction coverage

These directions describe the **retained managed backend**, not dependencies
ordinary desktop users must administer. Preserve the implemented backend while
qualifying portable peers. Current operations are in [worker operations](worker-operations.md).
Implementation, runtime qualification and release acceptance remain separate.

| Direction | Implemented / prototyped | Runtime qualification | Release acceptance / task owner |
|---|---|---|---|
| Kubernetes and Docker | Pinned Dockerfile, OCI image/build history and K3s manifests exist | Historical build evidence is retained; current deployed candidate and isolation require fresh evidence | Pending P02/P07/P13/P14; organisation administration P21 |
| Create Pods | API/executor Deployments and bounded validation Job builder exist | Current readiness, resource/egress enforcement, termination and cleanup unqualified | Pending P07/P11/P12/P14 |
| Service API | Versioned authenticated worker API and Service manifests exist | Current requester-to-worker integrated run unqualified; source or a Ready Pod alone is insufficient | Pending P08/P09/P11/P14 |
| Redis | Streams, receipts, leases, cancellation/replay and executor paths exist | Component/mock and historical results do not prove current restart, retention or failure recovery | Pending P08/P11/P12/P14; fleet improvements P15 |


<a id="runtime-ownership-20261004"></a>
## 2026-10-04 — Runtime ownership and external-update usability finding

**User-reported:** after an external Ollama update, Refinix showed “The selected model is unavailable
for new work. Open Settings.” The updated runtime version, current selected model/digest, live status
response and packaged application were not observed in this documentation task.

**Source-inspected:**

- [profiles.for_observation](../backend/contracts/profiles.py) matches model ID, digest, runtime name,
  exact runtime version and target profile. An unmatched updated engine yields no matching profile.
- [Coordinator._model_capability_blocker](../backend/coordinator/server.py) distinguishes no qualified
  workflow profile for the observed Ollama version from a missing or disabled model.
- [renderReadyLine](../frontend/app/app.js) uses the reported generic line when the runtime is reachable
  and the model is installed but unavailable for new work. Several blockers can share this line;
  version mismatch is a source-supported explanation, not a confirmed live diagnosis.

**Product decision:** runtime/model/workflow qualification remains engineering/release work.
Customers receive one managed app/engine setup, with explicit model provisioning and automatic local
installation checks. An external engine update must not change Refinix's engine. A pinned app-managed
llama.cpp build remains the preferred candidate, pending parity, packaging and recovery qualification;
no runtime migration or admission change was made here. Unsupported engine combinations need their
specific reason and an approved graphical recovery action, not instructions to edit profiles.

**Orchestration decision:** keep the existing harness. LangGraph is an unadopted evaluation option for
an evidenced workflow gap; no comparative Refinix integration/performance/maintenance result was
established in this review.
Framework orchestration and inference-engine ownership are separate decisions. See
[PROJECT.md](PROJECT.md#70-orchestration-choice-and-alternatives) for the options and reconsideration criteria.

**Verification boundary:** source inspection and documentation review only. No application tests,
model calls, runtime probes, downloads, installs, migrations, framework adoption or Git writes.

<a id="hardware-presets-20261004"></a>
## 2026-10-04 — Published evidence for hardware/capability presets

**User direction:** prepare category recommendations and runtime/context/cache/resource presets from
existing research; collect hardware facts and match the reviewed records. Reuse existing tools and
code. Device brands are labels, and owning every target laptop is not a research prerequisite.
[PROJECT.md §4.3.1](PROJECT.md#431-reviewed-hardware-and-capability-presets) and
[model-catalog.md §4.1](model-catalog.md#reviewed-presets) define the current contract.

The following public primary records were inspected on 2026-10-04. These are externally reported
results or artifact metadata, not fresh Refinix measurements:

| Source | Reported observation | Appropriate use / limitation |
|---|---|---|
| [Benchmark author's Apple dataset](https://huggingface.co/datasets/enescingoz/humaneval-apple-silicon) | M1, 16 GB, macOS 26.3.1: Qwen3.5 4B Q4_K_M generation 14.05/13.49 tok/s at 128/256 output tokens; Gemma 3 4B Q4_K_M 21.34/20.69 tok/s. Rows dated 2026-04-07 | Candidate comparisons. Short prompts, full GPU offload and flash attention; no pinned engine commit identified on the card. Does not prove 8 GB, long context or OCR; its memory column is insufficient for total peak-memory qualification |
| [Same benchmark record](https://huggingface.co/datasets/enescingoz/humaneval-apple-silicon) | M2 Max, 32 GB: Qwen3.5 4B Q4_K_M generation 48.35/48.07 tok/s at 128/256 tokens, 2026-04-07 | Evidence for this configuration only; not a forecast for base M2/M1 or Windows GPUs |
| [Quantizer's Qwen3.5 files](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/main) | Q4_K_M weights 2.74 GB; F16 multimodal projector 672 MB | Download/storage seed, not peak RAM. Different bytes from the historical 3,389,971,840-byte Ollama blob; provenance/hashes and parity must be established before substitution |
| [Google's Gemma 3 QAT files](https://huggingface.co/google/gemma-3-4b-it-qat-q4_0-gguf/tree/main) | Q4_0 weights 3.16 GB; F16 projector 851 MB; gated distribution | Alternative candidate with licence/access review needed. This QAT Q4_0 artifact is not the benchmark's Q4_K_M artifact |

The [upstream CUDA benchmark discussion](https://github.com/ggml-org/llama.cpp/discussions/15013)
provides additional GPU observations. No matching RTX 2050/Qwen3.5 4B result was established in this
review; do not invent that minimum or transfer another GPU's measured speed. Use exact comparable
rows where available; label conservative estimates and their missing inputs otherwise.

**Starting points, not accepted defaults:** retain Qwen3.5 4B as the existing reuse baseline. Compare
Gemma against the actual Chat/Code/document fixtures before selecting it. The historical Mac path
records context 8192 and Chat output 2048; Ubuntu context 4096 remains separate evidence in
[the first-model record](model-catalog.md#bounded-execution-settings-for-the-first-path).
These are not new-engine or all-device qualification. Specify and justify cache types, actual peak
resources, available-memory/storage floors and engine build before promoting a complete preset.
Do not synthesize missing KV values or minimum macOS versions from these short benchmarks.

**Reuse finding:** existing upstream runtime, Hub download/cache and platform-metric libraries cover
substantial commodity functionality; the catalogue's [reuse inventory](model-catalog.md#42-reuse-before-new-infrastructure)
records integration and offline-policy gaps. No single inspected package supplies all Refinix
workflow qualification, native packaging, sandbox enforcement and update/state recovery.

The already-considered `llmfit` has
[documented target-hardware profiles and JSON plans](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md),
including context caps and storage estimates. This can support internal preset preparation without
the physical computer. Outputs include estimates and limitations; they do not prove workflow quality
or actual peak resource use. No tool was installed, run or adopted as a shipped dependency here.

**Plan review:** the implementation-owner proposal needs correction for preset matching/evidence,
reuse choices, compatible-data rollback, sandbox resource enforcement and sampled-observer claims.
See the [consolidated review](beta-execution-handoff.md#review-agent-assessment-20261004).
The owner must review these doc changes and reconcile the proposal before joint PASS or implementation.

**Verification boundary:** documentation and source/public-record inspection only; no application
tests, benchmarks, model weights, installers, live runtime calls or Git writes. Published research
does not accept Refinix packages, supported OS ranges, security controls or the updater.
