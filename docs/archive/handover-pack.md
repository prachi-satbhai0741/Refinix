# Handover pack

> Historical prototype record/template. Retained for reproduction and dated evidence.
> Current scope and order are in [tasks.md](../../tasks.md#numbered-execution-tasks);
> refresh source/device facts and obtain applicable authorisation before using old steps.

One input handover instead of a question at every chunk.

The requester supplies the inputs and the authorisation scope below **once**.
Agents then implement, review and fix inside that scope, and return only for an
input nothing in the repository can supply, **missing authorisation**, or a
required device action or acceptance check.

This document **does not authorise anything by existing**. Authorisation is the
sentence the requester writes in Part 2.

> **What this changes and what it does not.** Supplying an input in advance
> removes the *question*, never the *gate*. A fixture supplied today still has
> to pass its acceptance check when its chunk runs; a stated constraint still
> needs the device action it describes. Expect fewer redundant questions and
> clearer checkpoints — not a promised number of stops. Some chunks need
> several device actions or repair cycles, and that cannot be known in advance.
> The rule this implements is in the
> [operating contract](../../tasks.md#operating-contract).

---

## Where the files go

**Not in this repository.** Put them in `private/handover/` at the repository
root, which is already git-ignored (`/private/` in `.gitignore`, verified with
`git check-ignore`), or on shared storage and give agents the path.

Never commit, paste into chat, or place in a tracked file: credentials, tokens,
API keys, private or confidential documents, real customer or plant data, or
personal identifiers.

The fixture rule is
[security.md §11](../security.md#11-repository-content): **use synthetic or
explicitly approved non-sensitive fixtures.** A document does not have to be
publicly redistributable — it has to be synthetic, or non-sensitive and
explicitly approved. Separately, C07 requires **source hashes and provenance**
for whatever is supplied, so send those with the file and keep the file itself
out of Git.

`private/` and `scans/` being ignored is a safety net, not a guarantee: a
forced `git add -f` bypasses ignore rules. Treat the location as a convenience
and the "never commit" rule above as the actual control.

Suggested layout:

```text
private/handover/
├── documents/     scan + SOP + the expected-result note
├── code/          the fixture repository, or a note choosing the synthetic option
├── competition/   official SIH26117 statement, rules, deadline, judging criteria
└── constraints.md output destinations, device windows, install/network limits
```

---

## Part 0 — Already settled. Do not re-answer.

Every row below is recorded with evidence. Re-supplying them wastes the sitting.

| Already decided | Value | Recorded in |
|---|---|---|
| Six device inventories | Collected for all six machines | [devicespecifications.md](../devicespecifications.md) |
| First configuration | macOS coordinator + Ubuntu worker; other machines off the critical path unless a measured need creates a device setup checkpoint | [devicespecifications.md](../devicespecifications.md#first-configuration--the-only-two-devices-on-the-critical-path) |
| Runtime (OD-03) | Ollama; `llama-server` is a comparison only, not a second adapter | [model-catalog.md](../model-catalog.md#od-03--ollama-is-the-first-runtime) |
| Model set (OD-05) | One model — `qwen3.5:4b-q4_K_M`, Apache-2.0, integrity verified | [model-catalog.md](../model-catalog.md#31-od-05--the-first-selected-model-set) |
| Pairing policy (OD-06) | Fingerprint-pinned TLS + single-use code; recorded, unimplemented | [security.md](../security.md#41-od-06--the-prototype-pairing-decision) |
| Infrastructure pins (OD-08) | K3s `v1.36.4+k3s1`, `redis:7.2.16`, `python:3.13-slim-bookworm` | [architecture.md](../architecture.md#81-od-08--resolved-infrastructure-pins) |
| Worker ports | `8443`, NodePort `30443` | [`backend/contracts/v1.py`](../../backend/contracts/v1.py) |
| UI direction | Local HTML/CSS/JS; `frontend/design/` is the visual reference; no React conversion | [frontend/README.md](../../frontend/README.md) |
| Job/event/approval schema | Reviewed contract draft; **not frozen** — integration pending C05 | [contracts README](../../backend/contracts/README.md) |

**Also not for the sitting** — these are recorded as later decisions and
answering them now would be guesswork that creates rework: installer
technology, specialist model selection, semantic-retrieval defaults, and
anything depending on an extraction path C07 has not designed yet.
See [open decisions](../prd.md#11-open-decisions).

---

## Part 1 — C03 prerequisites already supplied

Settled on 2026-09-04: Ubuntu port 8080 is Jenkins and remains untouched;
C02 was accepted; C03 through C13 were authorised sequentially. Do not ask
these questions again. The table is retained as the prerequisite record.

| # | Item | Who | Done when |
|---|---|---|---|
| 1 | **Identify the Ubuntu `*:8080` listener.** Run `sudo ss -ltnp 'sport = :8080'` and return the complete output — or the exact error — plus what that program is for. **Do not stop an unidentified service.** | Ubuntu worker operator | The output and the program's purpose are recorded |
| 2 | **Accept the C02 closeout**, or state the specific remaining objection. Deferred benchmarks stay labelled unmeasured either way. | Requester | Acceptance is recorded in `tasks.md` |
| 3 | **Authorise execution** — see the wording below. | Requester | The scope sentence is written and recorded |

### Part 2 — The authorisation sentence

Write it explicitly. A template:

> I authorise **C03**. The scope covers implementation, review fixes, and
> proportionate offline checks using existing dependencies and isolated test
> data. Stop for an input I alone can supply, for work outside this
> authorisation, or for a required device action or acceptance check.

To cover a range instead, name it — *"I authorise C03 through C05"* — and note
that progression still happens only after each chunk's acceptance gate clears.
Authorising C03 alone does not authorise C04.

**Do not delete the "work outside this authorisation" clause when copying
this.** Missing authorisation is a real checkpoint: repository evidence can
answer a technical question, but it can never grant permission to install
software, change networking, or take another consequential action.

---

## Part 3 — Needed before the build and workflow chunks (C04–C10)

Collect in the sitting; none of it is required to start C03. **Each subsection
states the earliest chunk that stalls without it** — the two earliest are
provisioning and device availability, which bite well before the workflows.

Best effort is fine for the later ones: they are gathered against chunks that
are not designed yet, so expect one or two follow-up requests when we get
there. That is the model working, not failing.

### 3.1 Provisioning constraints — earliest needed: **C04**

C04 builds the worker image and C05 provisions the cluster, so installation
limits are the first thing that stalls after C03.

| Needed | Who |
|---|---|
| Whether connected setup time is available, and when | Both device operators |
| Any download size or data-cap limits | Both device operators |
| Any restriction on installing software, or on `sudo` | Both device operators |

Agents supply the exact packages, artifacts, pinned versions and rollback steps
once they are known. This row asks only what is *allowed*, not what to install.

### 3.2 Device operating windows — earliest needed: **C05**

| Needed | Who |
|---|---|
| When the coordinator and worker can be available **at the same time** | Both device operators |

Cluster deployment (C05), pairing and the disconnect/cancel exercise (C06), the
failure drills (C12) and the three rehearsals (C13) all need both machines at
once. Existing hardware details need no repetition.

### 3.3 Documents pack — earliest needed: **C07**

| Needed | Notes |
|---|---|
| A **permitted** scanned inspection report | Synthetic or explicitly approved non-sensitive; provide provenance and SHA-256. |
| The relevant SOP or manual | Synthetic or explicitly approved non-sensitive; provide provenance and SHA-256. |
| **What a correct approval note should say** | The required sections, the facts that must appear, and the page numbers each should cite. This is the acceptance criterion — without it, "the output looks fine" is the only available check. |
| Which application opens the `.docx` | So the artifact check is against a real reader. |

### 3.4 Code fixture — earliest needed: **C07**; exercised in **C09**

Choose one:

- [ ] **Agents prepare it** *(recommended)* — we write one small repository with
      a single deterministic Python bug and its validation command, then you
      review that concrete fixture. Cheaper and faster than inventing one blind.
- [ ] **You supply it** — a small permitted repository, the exact change
      requested, and the single validation command that must be allowed to run.

### 3.5 Output destinations — earliest needed: **C10**

| Needed | Who |
|---|---|
| The folder on the coordinator where generated artifacts should be written | macOS coordinator operator |
| Where the backup demonstration recording is saved | macOS coordinator operator |

Naming a folder now does not pre-approve future writes; approval stays per-action.

---

## Part 4 — Needed before offline evidence and rehearsal (C11–C13)

| Needed | Earliest | Who | Notes |
|---|---|---|---|
| Which LAN may be used, and who can authorise temporary network controls | C11 | Network owner | Controls are applied by the device operators, not by agents |
| A separate device and operator to observe the offline window | C11 | One teammate | Agents design the observation method. A second laptop on the same Wi-Fi does not by itself guarantee visibility. |
| Official SIH26117 documents | C13, but the sooner the better | One teammate | Exact wording, submission deadline, required deliverables, judging criteria, submission/IP terms. Send sources or links, not a summary — this closes [OD-01](../prd.md#11-open-decisions) and may change scope, so early is safer. |
| Distribution and website direction | C13 | Requester, with the design track | Product name (final or provisional), repository visibility, ownership/licensing direction, and what the public site is for — showcase, demo request, or downloadable release. Approved contact details and copy. Relates to [OD-02](../prd.md#11-open-decisions). |

---

## What still requires the built result

No advance answer replaces these. They are how the product is shown to work.

| Chunk | Human action on the built result |
|---|---|
| C03 | Use real Chat, restart the application, confirm the history survived |
| C04–C05 | Build the worker image and return its digest; deploy the reviewed manifests; verify the running integration |
| C06 | Pair the two devices with real credentials and fingerprint; exercise cancel and disconnect |
| C07–C09 | Review agent-prepared synthetic fixtures and required setup on the Mac/Ubuntu configuration; run Documents/OCR, open the generated Word output, and inspect the Ubuntu-validated patch |
| C10 | Exercise approve, deny and expiry against real outputs |
| C11–C12 | Apply the reviewed network controls, observe the run, run the failure drills, record measurements |
| C13 | Three clean-start rehearsals, the backup recording, and candidate acceptance |

## C03 continuation — 2026-09-04

The requester withdrew the mandatory third-device requirement. The critical
path is the Mac coordinator and Ubuntu worker; OCR returns to C08 Documents.
The Windows qualification script is retained as **deferred**, with no C07
action or required execution role. Windows machines may still build any module.
C01/C02 remain accepted, and all C03 repairs stand. The earlier C03 run recorded
29 checks, a real Ollama/browser response, clean stop/restart, stable node
identity and retained history; this correction does not rerun or replace it.

The requester will accept the repaired Mac app after running it. Only C04
build-input preparation is authorised before that acceptance: see
[the prepared image inputs](../../backend/worker-image/README.md). Worker/API
implementation and image building follow acceptance; no worker image, OCR,
pairing or cluster result is claimed from these inputs.

**Internal demonstration: 8–9 September 2026.** The dated sequence and explicit
slip risks are in [tasks.md](prototype-task-record.md#sequence-toward-the-internal-demonstration).
Evidence gates remain mandatory; a shorter verified demonstration must be
labelled incomplete if the full candidate does not fit.

### VERIFY — RUN THESE YOURSELF

macOS coordinator, arm64, zsh. Stop the existing coordinator with Ctrl+C in its
terminal, then run:

```sh
cd /Users/adityatadge/Documents/GitHub/AegisForge
PYTHONPATH=. ./.venv/bin/python -m backend.coordinator
```

Open `http://127.0.0.1:8770`, refresh the page, and send:

> Write a detailed description of Paris in six numbered sections: history,
> geography, architecture, museums, food, and daily life. Write about 100 words
> in each section and end with the exact sentence: End of description.

Confirm the reply reaches its final sentence and the attempt shows `stop` plus
an observed output count and a reply limit of `2048`. If it reaches the cap,
expect **failed**, reason `length`, and an **Incomplete reply** notice beside
the retained text; ask to continue. Restart with the same command and confirm
the response and stopping reason remain. Return the observed result or error. This is
the requester acceptance gate in AGENTS.md/tasks.md; C04 follows acceptance.
No install or host configuration changes are involved. Ctrl+C stops the app;
its existing SQLite history remains outside the repository. The deferred
Windows qualification packet has not run and is not needed for this acceptance.

The reply repair raises only C03 Chat's output allowance from 512 to 2048;
context stays 4096 and no model is installed. Startup adds one nullable metrics
column to the existing database. Earlier stopping reasons stay **not recorded**
rather than being invented. The additive column can remain if the previous
coordinator source is reinstated; do not delete the history database.

**Reply-repair verification, 2026-09-04:** 33 coordinator/contract checks passed,
including stop/length/missing/unexpected reasons, partial-reply continuation,
the version-1 history upgrade and expected browser disconnects. JavaScript
syntax passed. A separate macOS instance on loopback port 18770 with temporary
history returned a real 664-token reply in 22,735 ms, ending in `stop`; its
metadata and text survived restart with the same node ID. The browser displayed
the reply limit of 2048 and the retained **Incomplete reply** notice for a
separate, explicitly synthetic `length` fixture. The test instance was stopped;
the normal port-8770 app and its history were not modified. These checks prove
the repaired completion path, not factual answer quality or C03 acceptance.

### GIT / GITHUB — RUN THESE YOURSELF

Repository `/Users/adityatadge/Documents/GitHub/AegisForge`; observed branch
`aditya` tracking `origin/aditya`, with existing modified/untracked files.
Review the combined C03 files, two-device correction and C04 build inputs before
staging; other pre-existing documentation and AGENTS.md changes remain separate.

```sh
cd /Users/adityatadge/Documents/GitHub/AegisForge
git status -sb
git add backend/coordinator/__init__.py backend/coordinator/__main__.py backend/coordinator/db.py backend/coordinator/runtime.py backend/coordinator/server.py backend/coordinator/test_coordinator.py backend/coordinator/README.md
git add frontend/app/index.html frontend/app/control.html frontend/app/app.js frontend/app/app.css frontend/app/overrides.css
git add backend/worker-image/Dockerfile backend/worker-image/Dockerfile.dockerignore backend/worker-image/requirements.lock backend/worker-image/provenance.json backend/worker-image/README.md
git add scripts/qualify-ocr-worker.ps1 tasks.md docs/devicespecifications.md docs/model-catalog.md docs/handover-pack.md docs/c03-context-ui-build-brief.md agent-memory/userprompts.md agent-memory/agentchangelog.md
git diff --cached --check
git diff --cached --stat
git commit -m "feat: add reviewed coordinator and prepare two-device worker build"
```

No Git or GitHub writes were run by the agent.
