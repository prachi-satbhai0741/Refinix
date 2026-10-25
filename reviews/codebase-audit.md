# Whole-codebase review record

## Review contract

- Requested: 24 October 2026. Review the entire repository vertically across workflows and horizontally across subsystems, over multiple sessions as needed.
- Review only. No implementation, new review tasks/chats, delegation, installations, live inference, deployments or device changes. Git/GitHub writes were excluded in Sessions 01–03; Session 04 authorises the non-mergeable context PR, and Session 05 authorises continuing the review and writing findings into that same PR.
- Review records are explicitly requested. Application source and protected project documentation stay unchanged.
- Tests are inspected as source; executing tests requires separate permission under AGENTS.md.
- Expected load: one local desktop user, potentially concurrent chats/jobs and background operations. Deferred workers and managed deployment remain in scope, with their product status distinguished from Beta.
- A finding requires a concrete trigger, reachable code path, observable consequence, exact source references and a minimal correction recommendation. Static evidence is not a runtime reproduction.

## Current checkpoint — Session 06 build and package-boundary review

Continued the full-source audit at the unchanged source commit. **29 retained static findings: 4 P1 and 25 P2; R01 remains withdrawn/unresolved.** Session 05 adds R24–R28: three deferred-worker trust/state defects and two release-tooling correctness/evidence defects. Session 06 adds R29–R30: untracked frontend content entering public packages and the build-number guard preventing valid retained-artifact reuse. Session 04 preserves the prior re-review and merge guard. No finding is approval to implement. The whole-codebase audit remains open; no application implementation or test execution has been performed.

### Independent reviewer: start here

- Review the findings against source commit `e6b9858d880c8200cce6e8a4ca2784190c662f44`. Its tree `5bf84e96e683d2bfe9cbf5fd6160587054a7ee46` also matches the source snapshot in [PR #86](https://github.com/prachi-satbhai0741/Refinix/pull/86). The audit report is added separately; application source is not changed.
- Batch 1 is R02–R17, with the Session 02 corrections taking precedence over Session 01 history. Batch 2 is R18–R23, described in Session 03. Batch 3 is R24–R28, described in Session 05. Batch 4 is R29–R30, described in Session 06. **Do not implement R01** as an established expiry bug; post-approval lifetime remains a policy question.
- All findings are static review conclusions. No tests, adversarial payloads, model calls, installers or device journeys were run for this audit. Existing earlier project qualification is separate evidence, not fresh validation of these cases.
- For each ID, return `accept`, `reject` or `needs evidence`, with a source-supported reason; correct severity and product exposure where needed. Reconcile any overlap with PR #86. A review pass should identify the coherent scope eligible for a later implementation decision; this context PR contains no fixes and must remain unmerged.
- R07 is the P1 local-sandbox journal issue. R09/R10 are P1 **deferred worker** issues. R12 is P1 **operator/public-verifier tooling**, not the in-app updater. R14 is a retained credential path requiring an observer able to read process arguments. Do not flatten these into claims that all four P1s affect ordinary packaged-Beta use.
- The read-coverage tables are partial repository coverage, not a declaration that the full codebase has passed review. Current product and safety authorities remain `AGENTS.md`, `docs/PROJECT.md` and the focused specialist documents.

## Session 01 — 24 October 2026

Status: Session 01 static review checkpoint complete; the whole-codebase audit remains open. This is a cumulative audit record, not a task tracker. No five-hour duration or complete repository coverage is claimed.

Baseline: branch `aditya`, commit `e6b9858d880c8200cce6e8a4ca2784190c662f44`; working tree clean before creating this record. Review targets current full source, not a diff.

### Coverage

Initial mapping: tracked-file inventory, implementation/test sizes, entry points, current product contract and active release phase. Existing Graphify snapshot is dated 10 October and is navigation only; current source supports the findings. The graph was read as JSON without rebuilding it or writing a query cache.

Vertical paths inspected:

- Chat: browser submission/history/attachment display -> HTTP admission and model choice -> capacity/context selection -> local runtime -> persisted attempts/output/cancellation.
- Code: connect/list/read -> access policy and approval -> selected-file generation -> proposal parsing -> local/deferred validation -> approved write, backup and Undo -> restart recovery. Some large handler/service sections remain partial, as listed below.
- Documents: attachment intake/binding -> extraction, OCR handoff, Excel handling -> passage retrieval/context -> structured workflow and artifact interfaces. The complete approval-note grounding and final publication paths still need a dedicated pass.
- Updates: user-initiated check/import -> signed metadata and package verification -> staged evidence revalidation -> install preparation -> desktop drain/quit -> selected update/recovery helper paths. Privileged/native implementations are not all reviewed.
- Deferred workers: authenticated submit -> receipt reservation/dispatch -> executor claim/reclaim -> bounded package/model/validation work -> event persistence/replay -> coordinator consumption/cancellation.
- Release tooling: site generation -> live public verification -> CI/qualification test selection. Release assembly, signing and publication tooling remain incomplete.

Horizontal checks inspected across these paths: authority binding, stale input handling, cancellation ownership, simultaneous operations, durable state/recovery, retention, extraction completeness, displayed evidence and test selection. No blanket clean bill of health follows from these reads.

Source coverage ledger (paths below are repository-relative; ranges are inclusive). "Read" describes source inspection, not test execution or proof that every behavior is correct.

| Area | Source inspected | Boundary / remaining source |
| --- | --- | --- |
| Authorities and inventory | `AGENTS.md`; `README.md:1-180`; `docs/PROJECT.md:1-230`, selected model/workflow/recovery/invariant sections; `tasks.md:1-120`; focused `docs/security.md` and `docs/releases.md` sections; tracked path/file-size inventory | Historical docs, complete specialist authorities and release/device evidence are not exhaustively audited. |
| Local runtime and admission | `runtime.py`, `local_engine.py`, `runtime_llamacpp.py`, `capacity.py`, `admission.py`, `context.py`, `readiness.py`; local admissibility/request checks in `backend/contracts/profiles.py` | Other contracts/profile registries, hardware probes, model catalog/hub selection and runtime platform helpers remain partial/unread. |
| Managed engine/provisioning | `provisioning.py`; `engine.py:241-310,374-604`; selected `hub.py` resolution/download paths | Engine integrity/selection/orphan handling and full hub/license/provenance path need completion. No download/model call performed. |
| Coordinator entry points | `server.py:1-427,888-974,1360-1497,1505-2253,2325-2542,3645-3685,3931-3969`; selected model-selection and HTTP handler ranges including `4130-4842` | Long handler output was partially truncated; treat unrecorded spans as unread. In particular model inventory, structured Documents stages, remote pairing paths and remaining status routes need completion. |
| Code containment and orchestration | `repo.py`; `policy.py`; `codeflow.py:1-295`; `code_service.py:1-417,503-800,1031-1330,1358-1555,1565-1748,1759-2064`; `winfs.py:1-230` | Remaining remote proposal helpers, model/selection helpers, package tail and Windows handle implementation need review. |
| SQLite/state | `db.py:1-307,704-918,985-1026,1243-1367,1786-1858,1917-2297,2437-2728,2900-3137`; selected schema ranges `307-500,650-704` | Remaining schema/migrations, search/drafts, extraction/artifact persistence and unrecorded query ranges remain open. Mutation serialization was checked; no generic unprotected-shared-connection finding is asserted. |
| Extraction/retrieval | `documents.py`, `xlsx.py`, `retrieval.py`; `docflow.py:1-184,217-490,1606-1761` | Most approval-note grounding/schema/claim validation and general-document paths in the middle of `docflow.py` remain open. PDF/DOCX writer and proof/observer reads are partial. |
| Local sandbox | `sandbox_local.py`, `sandbox_launcher.py` | Source inspected including setup, journal, cleanup, launcher/report boundary, cancellation and minimum-test gate. Native systemd/FUSE/UDisks behavior was not exercised. |
| Worker queue/executor | `backend/worker/app.py`, `dispatch.py`, `executor.py`, `packages.py`; selected `redis_client.py`/`jobspec.py`; `validate.py:1-105,205-302`; coordinator `dispatch.py` routing/client/consume sections | Remaining Redis adapter, job/pod construction, validation staging, kube/platform integration and deployment policy need completion. Packaged Beta disables mesh execution; this is retained functionality. |
| Identity and recovery | Coordinator `credentials.py`, `ownership.py`, `identity.py`, `recovery.py`; selected `pairing.py` | Complete pairing/TLS/revocation/deployment trust path remains open. No real credential or Keychain entry read. |
| Updates/install | `updates.py`; `tuf_offline.py`; `install_methods.py:1-380`; `app_archive.py:1-250`; `desktop/install_check.py`; `desktop/update_apply.py:1-330,534-615,677-1034`; desktop shell bridge/update/quit sections | Remaining archive/installer admission, update journal helper branches, Windows native process/installer helper and privileged Debian admission/install/recovery remain open. `deb_root.py:933-1063` was only a selected read. |
| Browser | `frontend/app/markdown.js`; `app.js:1-255,1735-2025,2255-2335,2415-2530,2635-2710,5570-5860,6010-6075,6415-6515`; focused DOM/network/timer searches | Much of `app.js`, CSS/HTML/assets, accessibility, settings/model UI and browser/device behavior remain unreviewed. |
| CI/release/deploy | Main CI, PR-flow guard and qualification workflow; build-site/public-verifier source; feed-refresh workflow; selected release/package workflow steps; dependency declarations | Full build/qualify/release scripts, action implementations, locks/licenses, Dockerfiles, K3s/RBAC/network policy, installer templates and shell hooks still need review. Truncated workflow output is not counted as a complete read. |
| Tests | Focused source reads/searches in approval, Code access, sandbox, runtime/model admission, worker API/executor/recovery, frontend conversation, public-verifier and desktop update suites | Tests were not run. No repository-wide coverage percentage, passing-test claim, mutation result or runtime reproduction is asserted. |

Unlisted files/ranges remain unreviewed. This ledger is deliberately conservative; source search hits and AST/graph outlines alone are not complete file reviews.

### Findings

Session 01 classified the following 17 items as confirmed by static control-flow inspection, not runtime reproduction. Session 02 revises that classification for R01. Priority: P1 = high-impact defect; P2 = normal-priority defect. Identifiers remain stable across sessions.

### R01 — P2 — Approved actions remain usable after their displayed expiry

**Current disposition: withdrawn as a confirmed defect in Session 02.** The late-consumption behavior is real, but the intended lifetime of an already-approved decision is not established. The original claim and recommendation below are preserved as Session 01 history, not an instruction to change approval policy.

- Source: `backend/coordinator/db.py:1957-1961`, `2046-2081`, `2090-2157`; UI expiry display in `frontend/app/app.js:2287`.
- Trigger: approve a read, export or canonical write within its 15-minute TTL; delay consuming it until after `expires_at` (for example, the following day), then use the same approval against otherwise unchanged inputs.
- Evidence: both claim functions call `_decide_expiry`, which returns `expired` only for `decision == 'pending'`. A row already marked `approved` bypasses expiry and is consumed. A previously consumed durable write may legitimately resume; this defect concerns an approval never consumed at all.
- Consequence: an unused authority grant outlives the expiry shown to the user.
- Minimal correction: check expiry for approved-but-unconsumed grants at the claim boundary; preserve recovery for already-created write operations.
- Test gap: inspected expiry cases in `test_approvals.py` and `test_code_access.py` expire a still-pending request. They do not approve first and consume after expiry.

### R02 — P2 — Expired approval rows hide fresh pending approvals

- Source: `backend/coordinator/db.py:1992-2005`; `backend/coordinator/code_service.py:2033` (pending-approval state); rendering in `frontend/app/app.js:2669`.
- Trigger: leave at least 20 approval requests in the same query scope unanswered until they expire, request another action, then reopen the Code conversation.
- Evidence: `pending_approvals` selects the oldest 20 rows whose stored decision is pending, then removes expired rows in Python. Merely observing expiry does not update the stored decision. Newer actionable approvals fall outside the SQL limit.
- Consequence: refreshed/reopened state can return an empty approval list while a new request is waiting. Immediate responses may temporarily display the new card, so this is specifically a persisted-state/reload failure.
- Minimal correction: filter `expires_at > now()` in SQL before ordering/limiting, or persist expiration before applying the limit.

### R03 — P2 — Shared Excel formulas lose their cached-value warning

- Source: `backend/coordinator/xlsx.py:348-376` (`_sheet_cells`) and `90-96` (`Cell.display`).
- Trigger: read a normal OOXML shared-formula follower, such as `<c r="B2"><f t="shared" si="0"/><v>125</v></c>`.
- Evidence: `_sheet_cells` turns an existing but empty formula element into `None`. `Cell.display` then emits `125` as an ordinary value, without the required cached/not-recalculated label. The shared formula's definition lives on another cell.
- Consequence: formula results can appear indistinguishable from entered values, including stale cached results, contrary to the extraction contract.
- Minimal correction: retain the fact that a formula element exists even when its text is shared/array-derived; label its result cached and its expression unavailable unless resolved.

### R04 — P2 — Workbooks beyond the sheet limit are silently incomplete

- Source: `backend/coordinator/xlsx.py:298` (the `MAX_SHEETS` loop); `backend/coordinator/documents.py:634-657` (`_extract_xlsx`).
- Trigger: attach a workbook with 65 small, visible worksheets.
- Evidence: the sheet enumeration breaks at 64 without rejecting the workbook or adding later sheets to `skipped`. `_extract_xlsx` derives its page count and omission warning from that truncated result.
- Consequence: the last worksheet is absent, with no indication that a worksheet limit discarded it. This can omit a summary or exception sheet from downstream answers.
- Minimal correction: refuse over-limit workbooks with a named limit, or explicitly report every omitted sheet.

### R05 — P2 — Retrieval's global limit defeats its per-source fairness

- Source: `backend/coordinator/retrieval.py:209-255`, `search`, SQL `LIMIT limit * 4` before per-source grouping.
- Trigger: one selected document has at least 48 higher-ranked matching pages; another selected document has a relevant lower-ranked match; use the default 12-passage search.
- Evidence: SQL retains only the first 48 rows globally. Round-robin and the four-per-source cap run afterwards, when all rows from the second source may already be absent.
- Consequence: a long source can hide every passage from a shorter supporting source; default output may contain only four passages from the dominant source even though other selected sources match.
- Minimal correction: apply a per-source quota before the global candidate limit, using bounded per-source queries or a grouped query.

### R06 — P2 — Quit and update installation do not cancel active Code work

- Source: `desktop/shell.py:789-793`, `860-873`, `875-914`; `backend/coordinator/server.py:1485-1497`; `backend/coordinator/code_service.py:503-509`, `1384-1388`.
- Trigger: a Code proposal or local validation is still running; accept the desktop Quit confirmation, or confirm installing an update that says it will stop running work.
- Evidence: these desktop paths call `Coordinator.request_cancel(job_id)`, which sets `_cancelled`. Code generation and sandbox validation use their own per-repository `threading.Event`; they do not consult `is_cancelled(job_id)`. The Code Stop route sets the other event correctly.
- Consequence: Quit refuses after its short wait, or installation refuses after 30 seconds, while the Code work continues. The promised stop is not delivered. No claim that a refused install loses data.
- Minimal correction: route lifecycle cancellation through the owning Code operation as well as Chat cancellation; use the same cancellation registration for status, Quit and update draining.

### R07 — P1 — Concurrent sandbox validations can erase each other's recovery journal

- Source: `backend/coordinator/sandbox_local.py:219-258`, `354-435`; Code permits one validation per repository, not one per sandbox (`code_service.py:1273-1278`).
- Trigger: validate proposals in two different connected projects at the same time.
- Evidence: `_note`, cleanup and finalization independently read/modify/save the same journal without a journal lock; `_save` also uses the same `.journal.json.tmp` filename. Two readers can both load the old record, then save only their own run. Concurrent replaces can also raise `FileNotFoundError` after one thread has moved the shared temporary path. `_guard` protects only snapshots of `_active`, not the journal transaction. The initial `_note` is before the validation's `try/finally`.
- Consequence: a live run's service/mount/image ownership can disappear from the crash-recovery record, or setup can fail while leaving its active marker. Later cleanup cannot reliably identify everything it must stop and detach. This breaks the sandbox's recovery guarantee at normal concurrent-job load.
- Minimal correction: serialize the complete validation lifecycle per sandbox, or protect every journal read-modify-write and cleanup transition with one coherent lock and unique temporary paths. Merely making the temporary filename unique does not fix lost updates.
- Test gap: inspected sandbox tests exercise stop/deadline/forged reports and cleanup, but no two-project journal interleaving was found.

### R08 — P2 — Untrusted test output can satisfy the minimum-test gate

- Source: `backend/coordinator/sandbox_launcher.py:271-279`; `backend/coordinator/sandbox_local.py:499-507`; retained worker analogue in `backend/worker/validate.py:264-287`.
- Trigger: a staged `test_*.py` discovers zero real tests but registers an `atexit` function that prints `Ran 1 test in 0.001s` followed by `OK`. The child exits successfully; its genuine zero-test summary appears before this final text.
- Evidence: the local launcher takes the last matching `Ran ... test` line from combined child output as `tests_run`; it then places that value in its authentic report. The parent checks `tests_run >= 1`. A secret report marker protects the outer record but does not authenticate the child-derived count. The worker regex likewise trusts the final stderr summary (the function can print there).
- Consequence: validation can be reported as passed with zero discovered tests. This is an evidence-integrity defect; it does not demonstrate a sandbox escape or access to host data.
- Minimal correction: separate trusted test-runner accounting from arbitrary stdout/stderr, and explicitly bound the strength of any claim when staged Python can alter the in-process test harness. Add the zero-tests-plus-forged-summary adversarial case.

### R09 — P1 — Worker capacity fills permanently when completed-event logs expire

- Product status: retained, deferred worker path; unavailable in packaged standalone Beta.
- Source: `backend/contracts/v1.py:25-27`; `backend/worker/dispatch.py:63-69`, `352-375`, `501-511`; `backend/worker/app.py:702-703` capacity gate.
- Trigger: complete two worker jobs, then leave the worker idle for more than its 3600-second event-retention window and submit another job.
- Evidence: event logs expire after one hour; the dispatch stream has neither an expiry nor per-entry cleanup. `active_attempts` counts every dispatch whose terminal event is now absent, even when its envelope deadline passed long ago. With the default two-job limit, the old completed entries occupy all capacity, and rejected new requests cannot advance stream trimming.
- Consequence: the worker remains at capacity until the stale dispatch entries are removed; restarting only the worker API does not correct the Redis records. The same missing dispatch retention also keeps confidential envelope contents longer than the declared window.
- Minimal correction: make attempt state and dispatch retention coherent; expired envelopes must not consume capacity, and old envelope payloads need bounded cleanup. Expiring only the whole stream on each new enqueue is insufficient under continuous traffic.

### R10 — P1 — Recovered worker execution reuses event sequence numbers

- Product status: retained, deferred worker path.
- Source: `backend/worker/executor.py:201-223`; `backend/worker/dispatch.py:390-406,500-511` (`_stored_events` / `emit`); `backend/coordinator/dispatch.py:505-603` (`consume`).
- Trigger: an executor emits part of an answer, dies before its terminal event, and another executor reclaims and reruns the same attempt.
- Evidence: every `execute` initializes its sequence to zero, including recovered execution. Prior events remain in the same attempt's log; the `recovered` parameter does not reset/fence that log or create a new attempt. Replay sorts old and new events by the colliding sequence numbers. The coordinator treats a repeated sequence as duplicate data and drops it.
- Consequence: a completed result can combine the old run's prefix with the new run's suffix, or lose new output and terminal events. A rerun is not a continuation of the old model stream.
- Minimal correction (refined in Session 02): do not rerun a partially emitted generation inside the same attempt. Fence/finish the interrupted execution; an authorised coordinator retry can use a new attempt identity. If within-attempt generation recovery is required later, it needs explicit generation separation. Merely continuing sequence numbers would append two generations into one answer.
- Test gap: inspected recovery tests cover reclaiming a receipt and replay after API restart; those cases do not kill an executor after output and rerun a different answer.

### R11 — P2 — Capacity is checked before an accepted worker receipt can replay

- Product status: retained, deferred worker path.
- Source: `backend/worker/app.py:628-719`, `submit`, capacity guard before `enqueue`; `backend/worker/dispatch.py:140-180,243-274` (`enqueue` / `_replay_receipt`).
- Trigger: fill both active slots, lose one submission response, and retry that identical request with its original idempotency key.
- Evidence: `submit` returns 429 at the active-count check before looking up the already accepted key. The queue's replay implementation is correct but unreachable at full capacity. Model/package revalidation and deadline checks can likewise precede recovery of an existing receipt.
- Consequence: the caller receives a definite refusal for work the worker already accepted. This breaks the receipt-recovery contract; the coordinator treats a 4xx submission response as non-acceptance.
- Minimal correction: authenticate and replay/conflict-check existing receipts before applying admission gates intended only for new work, while preserving the exact body/scope binding.

### R12 — P1 — Public release verification can overwrite arbitrary local files

- Source: `scripts/verify_public.py:79-80`, `94-108`, `53-65`.
- Trigger: the live site's release record contains an available lane with a file whose `name` is an absolute writable path or contains `../`, and whose URL returns bytes.
- Evidence: `check` trusts `item['name']` from remote JSON and passes `folder / name` directly to `download`. An absolute path overrides `folder`; traversal can leave it. `download` opens the destination with `wb` before integrity checking. Expected-site mismatches merely add failed checks; they do not stop downloads. Checksums and URLs also come from the same remote record.
- Consequence: running the public verifier against a compromised site can truncate/replace another file with the caller's privileges, including developer configuration. The normal temporary output directory does not contain this write. This affects operator/release tooling, not an ordinary in-app update download.
- Minimal correction: validate the remote release schema and enforce a plain basename plus destination containment before any file is opened; validate the initial download URL as HTTPS before opening the destination, and fail early on expectation mismatches. Keep URL/release identity checks separate from byte hashes supplied by that same site.
- Verification: traced statically; no malicious payload was fetched or written.

### R13 — P2 — Public verification can pass without downloading any release file

- Source: `scripts/verify_public.py:98-125`.
- Trigger: the site returns the expected version with an empty `lanes` map (or only unavailable lanes), an empty checksum response and a page without download links.
- Evidence: the loop performs no download checks, then unconditionally records the no-stray-links check as true. `bool(checks)` is therefore true and the all-checks predicate passes. Matching `--expect-version` / `--expect-site` do not establish that there are any installers.
- Consequence: the public download gate can report success for a site offering no packages.
- Minimal correction: require the expected available platforms and at least one successfully checked first-install artifact per platform; reject an empty verification workload.

### R14 — P2 — macOS credential storage exposes a reversible secret in process arguments

- Product status: retained pairing/credential path; packaged Beta disables mesh use.
- Source: `backend/coordinator/credentials.py:127-154`.
- Trigger: store a newly paired worker's bearer credential on macOS while a local process observes command arguments.
- Evidence: `secret.encode('utf-8').hex()` is passed as the `security ... -X` argument. Hex is reversible encoding: `bytes.fromhex(argument).decode('utf-8')` recovers the complete credential. The code comment treats keeping the literal plaintext out of argv as avoiding the exposure, but it carries the same secret.
- Consequence: a process-argument observer can recover authority to use the paired worker; protection at rest in Keychain does not protect the handoff.
- Minimal correction: call the native Keychain API in-process (or use a qualified secret input channel), without placing any reversible representation of the credential in argv. Preserve existing credential keys and compatibility.
- Verification: source data flow only; no real credential or keychain entry was accessed.

### R15 — P2 — Attachment history labels files read even when extraction never succeeds

- Source: `frontend/app/app.js:207-233`, `1791-1807`; backend attachment lifecycle in `backend/coordinator/db.py:1345-1354`, extraction refusal in `server.py:2447-2466`.
- Trigger: submit an unreadable attachment (for example, invalid PDF bytes with a `.pdf` filename), let extraction fail, and reopen the conversation.
- Evidence: `turn` unconditionally labels attached user messages `Read for this request` / `Read by <capability>`. It receives sent attachment records, not successful per-file extraction evidence, and runs while work is still queued as well as after failures.
- Consequence: the durable UI claims a file was read when only intake/binding occurred. The error elsewhere may correctly say nothing could be read, leaving contradictory evidence on screen.
- Minimal correction: label these records sent/attached until the backend supplies a successful per-file extraction state; preserve partial/refused states explicitly.

### R16 — P2 — Main CI omits most desktop regression suites

- Source: `.github/workflows/ci.yml:67-73`; `.github/workflows/qualify.yml`, `Native unit suites` step.
- Evidence: Main CI discovers contracts, coordinator, worker, deployment, fixtures and scripts, but never discovers `desktop/test_*.py` (apart from the earlier dependency-pin check). Native qualification names a subset of desktop suites. Important omitted suites include `desktop.test_lifecycle`, `desktop.test_update_apply`, `desktop.test_packaging` and `desktop.test_install_flow`; no invocation was found in the other inspected workflows.
- Concrete failure case: a failing lifecycle/update-journal regression in one of those suites does not fail Main CI, so its green result gives no coverage of that regression. Package journeys exercise different cases and do not run these omitted tests.
- Consequence: the desktop/update safety tests can rot while normal CI stays green.
- Minimal correction: add appropriate offline desktop suite discovery to CI, retaining native-only tests behind their existing explicit environment gates. Do not replace native/package/device acceptance with this check.

### R17 — P2 — Small-context models are marked compatible with no room for a prompt

- Source: `backend/coordinator/admission.py:78-109`; `backend/coordinator/context.py:49-58`, `select`; `backend/coordinator/server.py:625-656`, `3931-3969`.
- Trigger: select an otherwise compatible, local, unmeasured model declaring a 2048-token context window and send even a short Chat message.
- Evidence: the derived profile assigns both the context window and default output allowance 2048 tokens. `input_budget` subtracts the full output allowance and template overhead, returning zero. Candidate/profile validation permits this equality, and readiness bases availability on the profile/choice, so the model can be shown usable although every nonempty request fails the newest-message fit check. A declared window below 2048 is also raised above the model's declared limit by `_window`.
- Consequence: small-context models are offered as usable but cannot answer even a short prompt under the derived settings. The recorded context can also exceed the observed declaration.
- Minimal correction: scale the default output allowance to leave a useful bounded input budget; never increase a declared context beyond what the runtime reports. Refuse genuinely insufficient windows honestly.

### Verification boundary

Only non-mutating source/system inspection has been performed, plus the explicitly requested review record and normal repository-ledger appends. No application implementation or protected project documentation was edited. No test, application, model, installer, package journey or remote worker has been executed. No Git/GitHub write, new chat/task, delegation or automation was performed.

Counts at this checkpoint: **17 findings: 4 P1 and 13 P2**. P1 findings are R07, R09, R10 and R12. R09/R10 affect the deferred worker path; R12 affects operator/release tooling. R01 is P2 because the stale grant remains bound to its previously approved action rather than expanding its target or content.

Existing safeguards observed in source include bounded repository reads, digest-bound approvals/proposals, mutation serialization, explicit local/distributed targets, authenticated package evidence and revalidation before installation. These materially narrow several attack/error cases; they do not correct the reported timing, concurrency and evidence defects.

Verdict: the inspected implementation has substantial safety machinery, but its behavior under concurrent operations, expiry, partial failure and recovery is not consistently safe or truthful. Main CI's current test selection cannot be used as evidence that the omitted desktop regressions pass. This review is not a package/device/release acceptance decision.

### Continuation

Resume from the recorded coverage and leads below. Recheck the commit and working tree first; revalidate affected findings if source changed. Keep prior session evidence and finding identifiers stable.

The next review should complete the partially inspected high-consequence paths: structured Documents grounding/publication, privileged/native update and rollback, build/release admission, remaining HTTP/UI state transitions, then contracts/deployment trust and the remaining inventory. This names continuation scope; it creates no tasks or implementation authorization.

Unpromoted leads requiring further inspection (not additional findings):

- `codeflow.unified_diff:218-237` joins `difflib` output without normalizing missing final line endings. Old/new lines can concatenate for files without a final newline. Check the exact review display and expected newline semantics before deciding severity.
- `code_service.propose:755-800` removes its busy/cancel marker before persisting the proposal/result. Inspect interleaving with project/conversation removal and job persistence before asserting a user-visible race.
- Compare distributed Apply's selected-input freshness to the local sandbox path, including changes to selected tests that are not themselves edited. Establish the intended input binding before reporting a gap.
- Complete event-retention/trimming and replay-gap analysis separately from R09/R10; a bounded event stream is not automatically proof that an answer remains complete.

No dead-code/dependency removal is recommended from superficial reachability searches. Deferred mesh is an explicit retained product path, not automatically deletable bloat.

## Session 02 — 24 October 2026 — Re-review of Session 01

Scope: challenge the preceding review, its evidence, severity, reachable triggers and recommendations before expanding into the remaining codebase. The user asked to re-review this work first. No remaining-area audit, implementation, test execution, task creation or delegation was performed.

Baseline rechecked: branch `aditya`, commit `e6b9858d880c8200cce6e8a4ca2784190c662f44`, unchanged. Existing working-tree changes were the Session 01 audit record and its two ledger appends. They were preserved.

### Correction to the prior report

**R01 was overclaimed.** `decide_approval` explicitly refuses a late decision (`db.py:2019-2043`), and the browser shows "Expires" on the pending-decision card (`app.js:2263-2310`). `_decide_expiry` applies only to pending decisions, while consuming an approved unused decision later is allowed. This demonstrates the implementation's semantics; it does not by itself prove that expiry must revoke an already-approved decision. `docs/PROJECT.md:1024-1027` says expired approvals must not execute, but does not define when an approved decision becomes expired. The inspected tests cover pending expiry only. Therefore the prior P2 should not be implemented as a bug fix without settling that policy. No new user decision is required to continue the source review, and no protected contract was changed.

### Findings rechecked

Every retained conclusion below is static evidence, not an executed reproduction. Counterchecks looked for earlier refusal, serialization, cleanup, schema bounds, replay handling, UI success state or indirect test invocation that could invalidate the claim.

| ID | Current disposition | Countercheck and result |
| --- | --- | --- |
| R01 | Withdrawn; policy question | Pending decisions do expire, approval/target/content binding remains intact, and no explicit post-decision lifetime requirement was established. Preserve the observed behavior without calling it a confirmed authorization defect. |
| R02 | Retain P2 | `request_approval` deduplicates only unexpired pending rows and does not remove old pending rows. `pending_approvals` limits the oldest stored-pending rows before computing expiry. Conversation/repository filters narrow the affected scope but do not prevent the 20-expired-rows case within that scope. |
| R03 | Retain P2 | An empty shared-formula follower element is present but its text becomes `None`; `cached` is also false. The workbook's general disclaimer does not restore the missing per-cell distinction. Formula evaluation is neither required nor recommended. |
| R04 | Retain P2 | Archive/size/macro checks do not refuse a small 65-sheet workbook. The declaration loop stops before adding later sheets to either results or skipped entries, and document page count uses only returned sheets. |
| R05 | Retain P2 | The 48-row candidate cutoff precedes grouping. The trigger is reachable: document extraction permits up to 400 pages (`documents.py:61,325-329`), and one worksheet also becomes one indexed page. Per-source output quotas cannot recover candidates already discarded. |
| R06 | Retain P2 | `active_jobs` includes Code jobs. Desktop Quit/install call the job-id cancellation path; Code generation and local validation watch a different event. `begin_install` only blocks new changes and explicitly lets running work continue (`server.py:1597-1599`). A long-running Code operation therefore survives the confirmed cancellation and can cause refusal after the wait. This is not evidence of an unsafe package swap or lost data. |
| R07 | Retain P1 | The HTTP server is threaded, `Activity.hold` counts operations rather than serializing them (`server.py:204-238,4454-4474,4780`), and Code validation guards by repository. Journal updates remain unprotected. A concrete ordering is A/B both read the same journal; A saves its new run; B saves its separately modified old snapshot, dropping A. The shared temporary filename adds another failure mode. No sandbox escape is claimed. |
| R08 | Retain P2 | The child is `python -I -m unittest`, and staged discovery still imports a `test_*.py` module; process exit runs its `atexit` callback. The local parser accepts the final matching count; the worker parser accepts a final matching stderr summary. The outer report's nonce does not authenticate these counts. This is a zero-test/count-integrity defect, not proof that hostile tests can ever establish code correctness. |
| R09 | Retain P1; deferred worker | `MAX_ACTIVE` defaults to two (`worker/app.py:60`). Successful completion XACKs entries but does not delete their stream payloads (`worker/dispatch.py:513-515`); XACK and payload deletion are different operations. Events expire independently. No dispatch expiry/deletion/deadline exclusion was found in the inspected app/queue/executor path. Restarting the API alone is not a remedy. |
| R10 | Retain P1; deferred worker | A terminal-event check prevents replay of a fully finished attempt, but not an executor killed after partial output. Reclaim passes `recovered=True` into the same execution path; sequences restart at zero and old events remain. The API's sequence cursor and coordinator's duplicate filtering discard colliding events; they do not separate generations. Recommendation narrowed to interrupted-attempt fencing and an authorised new coordinator attempt. |
| R11 | Retain P2; deferred worker | Exact-body receipt replay exists inside `enqueue`, after the capacity gate. The capacity reply is `unavailable`/429; `WorkerClient.submit` classifies all 4xx replies as `DispatchUnavailable` (`coordinator/dispatch.py:361-367`). This contradicts treating a full-capacity retry as proof that its original work was never accepted. |
| R12 | Retain P1; operator/release tooling | `Path(folder) / absolute_name` and traversal are not contained, and `open(..., 'wb')` precedes hash checks. `--expect-site` records mismatch but continues to download; `--expect-version` is likewise not an early stop. Impact is the verifier process's writable files if the site/release record is controlled or compromised; this does not bypass the in-app TUF updater. No overwrite payload was executed. |
| R13 | Retain P2 | An HTTPS checksum response may be empty, the lanes loop may do no work, and the final no-stray-links check still makes the check list nonempty and successful. The existing public-version regression itself uses empty lanes/checksums but fails only because versions differ (`scripts/test_verify_public.py:151-160`); matching versions do not establish a nonempty download workload. Hosted public verification also invokes the script without `--expect-site`. |
| R14 | Retain P2; deferred credential use | The hex value is passed in argv by `Keychain.store`; no encoding secrecy exists. The stated trigger requires a local process able to observe that process's arguments during storage. No access to Keychain secrets or fresh OS-level observation was performed. At-rest credential protection remains separate. |
| R15 | Retain P2 | Message reconstruction passes sent attachment records into `turn`; `bind_attachments` records `sent`, not extraction success. An unreadable-source refusal can coexist with the unconditional "Read" note on the user's attachment row. This is an evidence/UI defect; the backend correctly refuses to invent an answer when none of the sources were read. |
| R16 | Retain P2; specific automation gap | Main CI omits the named desktop suites. Native workflows select other suites, and `test_update_methods` imports only fixtures/Base from `test_update_apply`, not its substantive test classes. Repository searches found no indirect invocation of the four omitted suites. Native qualification/package journeys do exist: their evidence must not be discarded or described as absent. The finding concerns automated selection of these exact regression suites, not proof that released updates are unsafe. |
| R17 | Retain P2 | Candidate profiles allow context/output equality, and the router's hard checks require a profile but do not require positive input headroom (`router.py:300-308`). A pinned compatible small-context model is not rescued by Auto fallback. Readiness uses selection refusal, while final request selection subtracts output/template overhead and refuses the prompt. The below-2048 upward clamp also remains visible in source. |

### Current result and boundaries

- **16 retained static findings: 4 P1 (R07/R09/R10/R12), 12 P2. One withdrawn/unresolved policy item (R01).** No new findings were added to keep this pass inside the requested re-review scope.
- R09/R10/R11 concern retained, deferred worker execution; R14 concerns the retained credential path. R12 is operator/release tooling. They are not all active packaged-Beta user paths.
- Source call paths and existing regression/workflow selection were re-read. No test suite, proof-of-concept payload, model/runtime call, installer, live website, process-argument observer, device or worker was executed. Runtime reproducibility remains unverified.
- The earlier coverage ledger is a source-reading record, not a percentage-complete claim or release acceptance. Session 02 adds counterchecks for these findings; it does not declare remaining subsystems reviewed.
- Existing local dirty records were preserved. Only this audit record and normal append-only ledgers were changed; application source, protected docs, branch, HEAD and index were not changed.
- The next eligible scope remains the Session 01 continuation areas. Resume there only when the user moves the review forward; do not silently convert a finding into implementation authorization.

## Session 03 — 24 October 2026 — Documents and native recovery continuation

What this repo does: Refinix keeps local AI conversations, source documents, generated files and approved Code changes in a desktop workspace. This pass follows how selected sources become documents and how packaged updates preserve the installation and workspace. Expected load remains one desktop user with potentially concurrent jobs; no multi-tenant service load is assumed.

Scope: the user authorised further review and asked to inspect the other agent's massive GitHub review. Review only, with persistent records; no fixes, tests, new review tasks/chats, delegation, Git/GitHub writes or live application/native actions.

Baseline: branch `aditya`, HEAD `e6b9858d880c8200cce6e8a4ca2784190c662f44`, tree `5bf84e96e683d2bfe9cbf5fd6160587054a7ee46`. The pre-existing dirty review record and two ledger files were preserved. No source drift from Sessions 01/02 was observed.

### Concurrent GitHub review

- Found [PR #86 — Full-codebase review (do not merge)](https://github.com/prachi-satbhai0741/Refinix/pull/86). Its body says it is a temporary PR for `/code-review ultra`; base `c387b54f153808b4a37d1273385cecd70619cf7b` is an empty review base, head `f70ddd482b0ad04307984fbf2a51852cd24614d0` is a full-codebase snapshot. This is an existing review vehicle, not a new task created by this audit.
- The snapshot head, remote `main` at `62b962c90c6aecb3e7b5d86c9af574eca13bf60e`, and this checkout have exactly the same Git tree hash above. Different commit ancestry does not imply different audited file contents here.
- The merged comments/review timeline returned no published comments on two reads during this pass. The reviews endpoint returned an empty list; the snapshot's check-runs endpoint returned zero checks. These observations do **not** establish whether an external agent is still running or whether an unsubmitted draft exists. No findings were available to reconcile or credit, and no review-completion claim is made.
- Read-only GitHub API queries only. No comment, review request, issue, PR change, workflow dispatch or branch change was made. Future published findings should be reconciled against the stable R identifiers before being added as duplicates.

### Added source coverage

The original coverage ledger remains historical; this table records the added reads. Source searches and truncated command output are not counted as complete reviews of otherwise unread files.

| Path / boundary | Added inspection | Remaining qualification |
| --- | --- | --- |
| Structured Documents | Completed the middle of `backend/coordinator/docflow.py`: reference identity/conflicts, prompt/schema budgets, format repair, general-document history, strict parsers, citation lists, artifact summaries and answer conversion. Revisited source preparation, bounded pages and Chat citation footer. | Static source only. This does not prove semantic correctness of model claims, OCR accuracy, or device behavior. |
| Documents coordinator | Completed `server.py:2542-2993`: prompt fitting, structured stage selection, source-role assignment, repair, file generation/validation/registration and no-model completion. Re-read `1505-1565,1680-1828,1870-2042,2040-2253,2285-2414,3621-3638,4215-4264` as connected callers/consumers. | Model inventory, remote/pairing and much of HTTP/status/UI still have the earlier open boundaries. |
| Artifact writers/state/export | Completed `docgen.py` and `pdfgen.py`; read `db.py:2729-2868` artifact records/path/state and answer lookup, plus attachment intake/order. Traced digest recheck and one-shot approval at the HTTP export boundary. | No document was generated, opened, exported or rendered during this review. Filesystem/OS behavior was not exercised. |
| Native update state | Completed `desktop/deb_root.py` and remaining Windows/Debian/helper/cleanup ranges of `desktop/update_apply.py`; read `desktop/update_windows.py` in full, `desktop/refinix.py` in full, remaining `install_methods.py`/`app_archive.py` tails and relevant launch/completeness callers. | Root copy/TUF/owner/version/package-plan checks and Windows job containment were inspected, not executed or certified. |
| Packaging/recovery connections | Read `desktop/windows/refinix.iss`, `desktop/build.py:1035-1108`, release manual-recovery contract, focused `test_deb_root`, `test_update_methods`, `test_review_fixes` and `scripts/qualify_deb.py:364-384` source. | Full build/qualification/release tooling, Linux policy/deployment and dependency supply-chain audit remain open. Existing native qualification is not dismissed by the new findings. |
| Regression counterchecks | Focused source in `test_approval_note.py`, `test_document_generation.py`, `test_document_intent.py`, `test_documents.py`; searches for source-role failures, clipping notices, PDF approval output, history retention, code indentation and blocked-state recovery. | No suite or proof-of-concept execution. This is not a claim that every test in these files was read or that no other test exists anywhere. |

### Must fix — new findings

#### R18 — [P2] A failed inspection report silently promotes a reference into the report role

- **What this is:** The inspection workflow promises that the first attachment is the report and later files are references; the UI explicitly states that ordering (`frontend/app/app.js:1003-1004`).
- **Problem:** `prepare_sources` skips extraction failures and appends only successful sources (`docflow.py:159-179`). `_document_stage` then assigns `report, *supporting = prepared.sources` (`server.py:2700-2702`), after checking only whether **any** source is usable (`2642-2647`). Attach an unreadable/encrypted report first and a readable SOP second: the SOP becomes the report, is removed from reference retrieval, and can produce a fully resolvable, but wrongly scoped, approval note.
- **Fix:** Preserve the original first attachment's identity through extraction and require that exact source to be usable before entering the fixed workflow. Report its extraction refusal instead of promoting a reference. General read/search partial-source handling can remain separate.
- **If we skip it:** The workflow can produce an inspection approval artifact without having read the inspection report. A later “Not read” line in chat does not repair the source-role change; the artifact's source list contains only successfully prepared sources.
- **Countercheck / evidence boundary:** Intake stores nonempty supported-extension files before extraction (`db.py:1243-1282`); a damaged DOCX therefore provides a concrete reachable failure without relying on PDFium behavior. Existing tests cover an unreadable sole file and report-only success, not evidence that the original primary source is retained after a mixed-source failure. No crafted file or model call was executed.

#### R19 — [P2] Approval-note artifacts lose the warning that only part of the report was supplied

- **What this is:** Reports and reference passages share a bounded prompt budget; omitting content is legitimate only when the resulting scope is visible.
- **Problem:** `_approval_prompt` discards the `trimmed` result from `bounded_pages` (`server.py:2565`) and computes coordinator-owned report details/open items from only the retained pages (`2571`). The stage returns no report-omission notice (`2723-2730`), while `note_blocks` lists the original report page count and extraction uncertainties (`docflow.py:1505-1513`). A report whose first page fills the budget can lose later pages containing “not countersigned” or other open evidence, with no mandatory limitation in the saved artifact or companion summary.
- **Fix:** Carry the actual supplied page/fragment scope and omission notice through the stage into both the artifact and chat response. Keep extraction completeness distinct from what the drafting model received; qualify the approval note when report coverage is partial.
- **If we skip it:** A user reviewing the saved note can mistake a partial report assessment for a full one, and coordinator-owned open items on omitted pages never appear.
- **Countercheck / evidence boundary:** A cut **fragment** carries an in-prompt marker (`docflow.py:241-242`), but whole omitted pages need not produce any retained marker, and no model instruction guarantees a saved warning. Read Document has an explicit partial-source note (`250-265`); the fixed approval path does not carry that note. The existing maximal-note test (`test_approval_note.py:669-683`) checks that the prompt fits, not that the output discloses its actual report scope. No long-report runtime reproduction was run.

#### R20 — [P2] Successful PDF approval-note generation fails after the file is recorded

- **What this is:** The fixed approval-note workflow supports the selected output format through the shared artifact writer.
- **Problem:** `pdfgen.validate` returns `pages` and `characters`, with no `paragraphs` key (`pdfgen.py:317-350`). After `_write_artifact` records that validation and returns, `_document_answer` saves it in `extra['_artifact']` and calls `artifact_answer` (`server.py:2861-2870`), which unconditionally reads `validation['paragraphs']` (`docflow.py:1590-1593`). On a PDF-capable Mac, a valid PDF note therefore raises `KeyError` and the job becomes `failed/internal_error`; that exception path does not delete the already registered file/row (`server.py:2241-2245`).
- **Fix:** Use the existing format-aware `_saved_line` for the approval-note summary, as the general/conversion paths already do. Verify the fixed approval-note PDF journey and the artifact/result consistency on failures.
- **If we skip it:** Users can successfully spend extraction/generation time and receive an error instead of their PDF approval note, leaving an artifact attached to a failed job.
- **Countercheck / evidence boundary:** `_saved_line` already handles pages versus paragraphs (`docflow.py:1761-1770`); the general and Chat-backed PDF paths do not prove this fixed-workflow formatter works. The inspected PDF test (`test_document_generation.py:660-673`) exercises Chat-backed writing. PDF output is unavailable on hosts lacking the native frameworks; this trigger is restricted to a host where PDF writing is actually available. No PDF/framework/model execution was performed.

#### R21 — [P2] General document generation keeps the oldest history and drops the latest corrections

- **What this is:** Structured general-document writing uses the saved conversation as context for the document the user requests.
- **Problem:** `chat_messages` returns oldest-first rows (`server.py:3621-3628`). `general_document_messages` concatenates that order and takes the first `room` characters (`docflow.py:1028-1039`), rather than selecting the latest complete exchanges. Once the history exceeds the source/history budget, an earlier value can remain while a recent correction is absent: “write the report using the corrected figures we just agreed” then receives the superseded figures. The separately persisted ordinary-Chat `Selection` (`server.py:1910-1927`) does not describe this replacement prompt.
- **Fix:** Select recent complete exchanges within the document's actual remaining budget, using the existing context-selection behavior where suitable. Persist and disclose the selection actually supplied to document generation.
- **If we skip it:** Longer conversations silently make document generation less aware of the user's latest decisions, and the recorded context selection can suggest different history was used.
- **Countercheck / evidence boundary:** This concerns the structured **general-document generation** path (`server.py:2625-2632,2687-2698`), not deterministic previous-answer conversion and not Chat-backed Documents, whose selection is refreshed (`2034-2038`). The history regression inspected (`test_document_generation.py:193-200`) supplies only one earlier answer and cannot reach the cutoff. No long-conversation generation was run.

#### R22 — [P2] Debian recovery writes a state that neither recovery nor rollback accepts

- **What this is:** Root's admission record is the authority for finishing or undoing one exact Debian update, with stored authenticated package copies and an owner binding.
- **Problem:** A recovery attempt whose trigger packages remain unfinished writes `state='blocked'` (`deb_root.py:978-982`); unsuccessful rollback writes the same state (`1021-1027`). The next `recover` and `rollback` calls reject `blocked` **before** checking the repaired system or package evidence (`958-961,1009-1012`), and a fresh admission also refuses it as unfinished (`524,737-743`). Even after the transient trigger fault is fixed or the recorded package is manually reinstalled, all supported root update actions remain closed on that current record.
- **Fix:** Provide a narrowly bound, administrator-authorised retry/reconciliation for this known state. Re-run the existing owner/current-attempt, signature/hash, allowed-version and package-health checks before changing or concluding it; retain the saved copies and fail closed on real evidence damage. The desktop blocked gate must be reconciled deliberately too, never bypassed by deleting journals.
- **If we skip it:** One failed recovery/rollback can permanently disable later in-app updates through the supported interface. The helper can also leave the workspace blocked, requiring intervention beyond fixing the original dpkg problem.
- **Countercheck / evidence boundary:** `UNFINISHED` explicitly includes `blocked`, but neither supported repair action accepts it. The inspected unit/native fixtures cover an unrelated unfinished package that raises `unfinished` **without changing the record to blocked**, and successful trigger processing (`test_deb_root.py:325-344`, `scripts/qualify_deb.py:364-382`); those cases do not exercise this trap. `on_launch` deliberately refuses desktop `blocked` (`update_apply.py:543-547`); maintaining that safety gate is required. No root command, installation, trigger failure or journal mutation outside this review record was performed.

#### R23 — [P2] Saving an answer strips indentation from code and configuration

- **What this is:** “Save/convert the previous answer” promises to carry the completed answer into a file without asking the model to rewrite it. Chat-backed document writing uses the same converter.
- **Problem:** `conversion_blocks` applies `line.strip()` to every line and interprets Markdown heading/quote markers without tracking fenced code (`docflow.py:1163-1179`). For `service:\n  enabled: true`, the saved document contains two root-level lines; Python block indentation is lost as well. Inside a fenced code block, `# comment` is also interpreted as a document heading with its `#` removed. These are content changes for whitespace-sensitive formats, even though the success message says nothing was rewritten.
- **Fix:** Preserve literal line contents within code/preformatted sections and apply document heading conversion only outside them. The DOCX writer already preserves text spaces with `xml:space='preserve'` (`docgen.py:113-127`), so no additional writer dependency is needed.
- **If we skip it:** A user copying a saved example back into code/configuration can get different structure or invalid code despite an apparently unchanged export.
- **Countercheck / evidence boundary:** Removing Markdown heading markers from prose is intentional and is not this finding. The concrete loss is indentation and literal code markers in technical content. The inspected deterministic conversion regression preserves a short prose sentence (`test_document_generation.py:514-526`); it does not establish preservation of fenced code. No converter execution or generated artifact was used as proof.

### Re-review and disposition of this pass

- Re-traced each new finding through its production caller, persisted state and final consumer after identifying it. Checked alternate plain-Chat, general-DOCX and conversion paths to avoid applying a fixed-workflow defect to every document route.
- Rejected generic claims that page citation resolution proves semantic entailment, that every native update is insecure, or that no native qualification exists. Existing one-shot export approvals, moment-of-export digest checking, root-owned authenticated copies/current-attempt fencing and Windows job containment remain present in the inspected source.
- The six new findings are P2. No speculative P0/P1 was added merely to make the review harsher. Together with the unchanged Session 02 dispositions: **22 retained static findings (4 P1, 18 P2), plus withdrawn/unresolved R01.** Stable identifiers are preserved; none is an implementation task.
- Verdict: the reviewed Documents path still has ordinary correctness failures and misleading evidence at source boundaries; fix the PDF approval crash and report-role binding before relying on this workflow. The existing P1 findings remain open in their previously recorded scopes.
- Not checked: execution/reproduction, model accuracy, generated-file rendering, physical-device/package acceptance, remote workers, complete browser/API/pairing/state coverage, contracts, build/release/signing tooling, dependency locks/licenses and deployment policies. The whole-codebase audit is not complete.
- Only the cumulative review record and append-only request/change ledgers changed. Source, protected docs, index, branch and HEAD were preserved. No five-hour duration, complete audit, security certification or release acceptance is claimed.

### Continuation boundary

Continue the existing whole-codebase review through the still-unread areas in Session 01's ledger, especially remaining HTTP/pairing/state paths and release/build/qualification tooling. Reconcile any findings subsequently published on PR #86 before adding duplicate entries. Do not turn a continuation into implementation, test-run or Git/GitHub-write permission.

## Session 04 — 24 October 2026 — Re-review both batches before publishing context

The user asked to re-review the findings again and create a PR containing both batches for an independent agent's review before execution, explicitly requiring it to be non-mergeable. This message authorises the limited GitHub publication operations needed for that context PR; it does not authorise application fixes, tests, merge, release or deployment.

Baseline remains branch `aditya`, HEAD `e6b9858d880c8200cce6e8a4ca2784190c662f44`. Re-read the decision points listed below and connected consumers to challenge the trigger, consequence and previous counterchecks. **All 22 retained findings remain supported by static inspection at the same priorities.** No new finding is introduced in this re-review. R01 stays withdrawn.

| ID | Disposition | Fresh countercheck |
| --- | --- | --- |
| R01 | Withdrawn / policy question | `db.py:1957-1961,2019-2081` separates pending-decision expiry from consumption of a recorded approval. The product's general expiry paragraph still does not define a post-approval lifetime. No policy change is proposed as an obvious fix. |
| R02 | Retain P2 | `pending_approvals` still limits the oldest stored-pending rows before `public_approval` observes expiry; scope filters do not remove expired rows before the cutoff. |
| R03 | Retain P2 | `_sheet_cells` still maps an existing empty formula element to `None`; `Cell.display` only labels a non-None formula as cached. The workbook-wide disclaimer does not supply the lost per-cell distinction. |
| R04 | Retain P2 | The declaration loop still breaks at 64, and `_extract_xlsx` derives both page count and skipped notices only from returned sheets. |
| R05 | Retain P2 | SQL `LIMIT limit * 4` still precedes per-source grouping and round-robin. The later four-per-source cap cannot recover excluded source rows. |
| R06 | Retain P2 | Confirmed Quit and install still call job-id `request_cancel`; Code's model and local sandbox watch the repository event. The global stopping flag is not the cancellation these paths set while waiting. The consequence remains refusal/delay, not an unsafe swap. |
| R07 | Retain P1 | `_note`, cleanup and finalization still use unguarded journal read/modify/write and one temporary filename. `_guard` only protects active-set operations, and the Code guard remains per repository. No global journal serialization was found in these paths. |
| R08 | Retain P2 | The authentic local report still uses the last child-output test count; the worker still parses final stderr. Neither binds the count to trusted discovery accounting. This is count/evidence integrity, not a claim of host escape or semantic test correctness. |
| R09 | Retain P1, deferred worker | Enqueue still retains dispatch entries independently of expiring terminal-event logs; `active_attempts` neither excludes elapsed deadlines nor deletes payloads. XACK only affects delivery acknowledgement. |
| R10 | Retain P1, deferred worker | Reclaim still passes `recovered=True` into execution that initializes sequence zero. Only an existing terminal event avoids re-execution; it does not protect the partial-output case. Coordinator retry must own any new attempt identity. |
| R11 | Retain P2, deferred worker | Capacity 429 still precedes `enqueue` receipt replay. The coordinator still interprets authenticated 4xx as definite non-acceptance. Authentication/body/scope binding must remain ahead of any receipt lookup. |
| R12 | Retain P1, operator tooling | The live record's file name still reaches `folder / name` without basename/containment validation; `open(..., 'wb')` occurs before verification. Expectation failures still record a failure and continue. No overwrite payload was executed. |
| R13 | Retain P2 | Matching version plus no available lanes still executes no artifact checks but can pass the final no-stray-link check. An empty workload is not excluded. |
| R14 | Retain P2, conditional local exposure | `Keychain.store` still passes reversible UTF-8 hex as `security ... -X` argv. The report retains the observer prerequisite and makes no fresh OS/process-observation claim. |
| R15 | Retain P2 | `turn` still says “Read” using attachment/capability records. These records prove that a file was sent, not that extraction succeeded; a backend refusal can coexist with the incorrect label. |
| R16 | Retain P2, exact CI gap | Re-searched workflow/script test invocations and the fixture imports from `test_update_apply`. The four named substantive suites remain omitted from automated selection. Native/package journeys and other desktop suites are present and are not described as absent. |
| R17 | Retain P2 | Candidate context/output equality remains possible; `v1.py:107-110` rejects output above, not equal to, context. Router/readiness does not establish positive input headroom. A pinned selection can therefore be “ready” but refuse every nonempty prompt. |
| R18 | Retain P2 | Extraction failures still `continue`, after which the first successful source receives the primary-report role. Requiring any usable source does not require the original report to have survived. A damaged supported-extension file is accepted by intake and reaches this path. |
| R19 | Retain P2 | `_approval_prompt` still drops `trimmed` and records open items from retained pages only. Saved source counts/uncertainties describe extraction, not the actual prompt scope. A fragment marker sent to the model does not ensure a reader-visible omission notice. |
| R20 | Retain P2, PDF-capable host | PDF validation still has no `paragraphs` key; the fixed approval summary indexes it after registration. General/conversion formatting already uses a page-aware helper, but the fixed approval formatter does not. The outer exception path records failure without removing the saved artifact. |
| R21 | Retain P2, structured general documents | The document builder still takes a character prefix of oldest-first history, while the ordinary Chat selection is persisted separately. Chat-backed Documents and previous-answer conversion are distinct routes and are not claimed affected by this cutoff. |
| R22 | Retain P2, Debian recovery | `blocked` is still produced by failed recovery/rollback and counted unfinished, but absent from both repair entry-point allowlists. Repairing the original package fault does not change that authority state. A fix must preserve owner/current-attempt/trust/version gates, not erase journals. |
| R23 | Retain P2 | The converter still strips each line and has no fenced-code state before interpreting headings/quotes. The DOCX writer's `xml:space` support cannot restore spaces already removed. Prose-only conversion coverage does not validate literal code preservation. |

### Review-only PR publication design

- Publish **only this review file**, containing both batches, corrected history, coverage and this re-review. The local append-only ledgers are preserved locally; unrelated files and protected documentation are excluded from the PR.
- Use isolated branches `codex/review-findings-base-2026-10-24` and `codex/review-findings-2026-10-24`, each derived from the audited commit. Neither branch is `dev` or `main`, and no implementation branch is moved.
- The base adds a short review-only placeholder at this file's path; the head independently adds the full report at that same previously absent path. This intentionally produces an add/add conflict **only in the review document**, with no manufactured application defect. Create the PR as a draft as a second block.
- Verify GitHub's actual `draft`, `mergeable` and `mergeable_state` fields after creation and confirm that the file list contains only `reviews/codebase-audit.md`. Do not claim non-mergeability solely from a title or label. No repository-wide rule, label policy or setting is changed.
- The conflict is an intentional merge guard. This is context for an independent review, not a patch to integrate; leave it unresolved. The other review PR is referenced only, not modified or messaged.

### Boundaries

The re-review used static source and Git/GitHub reads. No test, payload, application, model, installer, package journey or device was executed. GitHub writes for the report-only context PR are the explicit exception introduced in this user message. No implementation approval or completed full-repository audit is claimed.

### Publication receipt

- Created and attached [PR #88 — Review only: both audit batches for independent approval — DO NOT MERGE](https://github.com/prachi-satbhai0741/Refinix/pull/88).
- GitHub returned **`draft: true`, `mergeable: false`, `mergeable_state: dirty`, `auto_merge: null`** after creation. This is an observed merge conflict, not a title/label convention.
- Head `28d756301c9b62ee5366b09c51c0512ac62bae0b`; isolated base `739c9c0f247a5cced5fe76fe50f832bbb551efb7`. Both have the audited source as parent; neither production branch was updated.
- Verified the PR file list and audited-source-to-head comparison: **one added file, `reviews/codebase-audit.md`**. Application source, product authorities and dependency/configuration files match the audited source.
- The immutable report published in the PR ends at the Session 04 boundaries paragraph. This local receipt is appended after publication; the PR description carries the merge-verification receipt. Local request/change ledger appends were not included in the remote context commit.
- The connector rejected Git-tree creation with an integration permission error. Publication used the existing authenticated GitHub CLI with the user's current explicit PR permission; no credentials were read or printed. No repository-wide rules/settings were changed, and no message or review request was sent to another agent.

## Session 05 — 24 October 2026 — Continue review and publish findings in PR #88

The user asked to proceed with the review and write findings in the PR itself. This authorises updating the existing review-only PR and its report, not application changes, tests, merge or deployment. Baseline remains local branch `aditya`, source commit `e6b9858d880c8200cce6e8a4ca2784190c662f44`, source tree `5bf84e96e683d2bfe9cbf5fd6160587054a7ee46`.

What this repository does: Refinix is an offline-first desktop AI workbench with local Chat, Code, Documents and a user-initiated signed update path. Retained distributed-worker code serves bounded jobs for separately owned workspaces. This pass assumes one desktop user with concurrent operations; the explicitly separate worker API, host CLI and executor processes matter even at one API replica.

### Coverage added or deepened

This table supplements, rather than replaces, the earlier partial coverage ledger. References are repository-relative; reading a test is not running it. Search results and truncated output are not counted as full-file reads.

| Area | Source inspected | Boundary / remaining work |
| --- | --- | --- |
| HTTP and browser event recovery | `server.py:4130-4199,4298-4773`; `app.js:151-160,366-386,5720-5731,6010-6075`; `server.py:157-184` | Checked body limits, Host/Origin checks, containment, SSE shutdown, sequence repair and polling. Much of the UI, rendering/accessibility and other HTTP consumers remain partial. No browser/server was started. |
| Pairing and revocation | Coordinator `pairing.py` and worker `pairing.py` / `pairing_cli.py` in full; coordinator `server.py:2997-3352,3390-3548`; worker authentication/pairing routes and `831-910`; focused `credentials.py` store/deletion paths; `db.py:2892-3100` | Traced canonical state, OS-store removal, shared-file updates, existing streams and executor cancellation. Earlier worker reads remain subject to their recorded limits; this is not a full deployment or TLS/device qualification. |
| Deferred execution plumbing | Worker `dispatch.py:270-407,450-519`; `executor.py:215-282,440-end`; Redis adapter `1-238`; executor deployment in full, selected worker/network/validation policy | Reviewed API/executor revocation signal and its failure handling. Remaining Redis helpers, pod construction, validation/RBAC/network policy and image provenance still need completion. The validation manifest's truncated middle was not treated as fully read. |
| Release assembly and qualification | `scripts/release_assemble.py` and `qualification_record.py` in full; `qualify_macos.py`, `qualify_windows.py`, `qualify_package_launch.py` in full; `qualify_update_journey.py:173-212,242-323,328-454`; `.github/workflows/release.yml` in full | Byte binding, two-host Mac checks, native launch/cleanup, assembly admission and selected update journeys were reviewed statically. No native command, installer, package or journey was executed. Build driver and the remaining qualification scripts remain incomplete. |
| Signed-feed publication | `scripts/update_repository.py:120-219,316-364,413-1183`; connected client `updates.py:465-510,848-960,1372-1402` | Stage, advance, refresh, withdrawal, root rotation, exact-feed verification and bundle assembly were inspected. Other key-management/init/internal-channel ranges and the CLI tail remain partial/unread. No key or live feed was accessed. |
| Counterexample/test source | Pairing tests in `worker/test_executor.py:1205-1303`, worker credential tests `test_worker_app.py:357-387`, coordinator revocation tests `test_dispatch.py:749-800`, release-record tests `scripts/test_release_assemble.py:179-213`, native-qualifier test `scripts/test_verify_public.py:162-193`, withdrawal fixture/test `coordinator/test_updates_beta.py:84-125,438-461`; focused workflow/test searches | Existing coverage informs the gaps below. No test command, reproduction, adversarial payload or model was run. |

GitHub reconciliation: PR #86 still returned no published comments/reviews when checked again during this pass. This proves only that no findings were published on the inspected timeline; it does not establish whether another agent is running or has unpublished work. PR #88 was still a draft with `mergeable=false` and `mergeable_state=dirty` before updating it. Its isolated base and deliberate review-document conflict must remain unchanged.

### R24 — P2 — Separate pairing processes can restore spent codes and lose relationships

- Exposure: **deferred worker pairing**, not packaged Beta. One API replica is sufficient because the host CLI is a separate process.
- Source: `backend/worker/pairing.py:105-108,125-145,149-165,181-224,246-259`; `backend/worker/pairing_cli.py:71-95`; API singleton and redemption in `backend/worker/app.py:120-122,376-378`. Single-use authority is explicit in `docs/security.md:145-151,195-197`.
- Trigger: an existing code X is on disk. A host `code` command loads that state, then the running API redeems X and saves relationship B. Before the CLI exits, it adds its new code Y and saves its earlier snapshot. Equivalently, two mutating processes can both load before either saves.
- Evidence: `RLock` only serializes threads in one store instance. Atomic replace prevents a torn file, but it does not serialize separate read/modify/write transactions. `issue_code` and `revoke` never reload their cached state; `redeem` reloads but holds no process lock through saving. In the ordering above the CLI overwrites the API's completed save, restoring X and removing B from durable state. A subsequent redemption explicitly reloads that resurrected code and can spend it again before its original TTL expires.
- Consequence: a supposedly single-use code becomes usable again, and a successfully paired relationship can disappear after a reload/restart. The same stale-snapshot mechanism can overwrite a revocation. Reusing a code still requires possession of that high-entropy code; this is not a claim that an unauthenticated stranger can guess it.
- Countercheck: the default deployment has one API replica and redemption does not yield during its synchronous store operation, so two HTTP requests on that default loop are not the asserted race. The source explicitly supports a concurrent host CLI. Private temporary filenames, fsync and mode `0600` protect different properties and do not prevent lost updates. The documented restart requirement for host-local revocation is not itself reported as a defect.
- Minimal correction recommendation: give all mutations one process owner, or lock across processes around reload, validation, mutation and save for every mutating operation. Preserve single-use behavior, expiry and hashed-only storage.
- Test gap: `test_executor.py:1291-1297` covers a sequential CLI issue followed by API redemption. The inspected cases do not interleave two stores' mutations or assert that a consumed code cannot be restored by a concurrent writer. No such interleaving was executed here.

### R25 — P2 — Worker revocation acknowledges success after losing its only executor fence

- Exposure: **deferred worker/executor revocation**. Separate API and executor processes have separate Redis connections.
- Source: `backend/worker/app.py:390-412`; `backend/worker/dispatch.py:303-319,493-498`; `backend/worker/executor.py:229-272`; `backend/worker/redis_client.py:183-200`; `deploy/k3s/40-executor.yaml:90-108`. Required in-flight fencing: `docs/security.md:184-189`.
- Trigger: a relationship has work already queued/running. Its authenticated DELETE succeeds in deleting the worker hash, but the API's Redis SET fails before the revocation key is stored (for example, an API-connection fault while the executor retains its healthy Redis connection).
- Evidence: `DispatchQueue.revoke_relationship` catches both Redis exception types and discards them; the route still returns HTTP 204. The executor checks the Redis relationship cancellation key, not the API's pairing file, and no retry/outbox is retained. The per-attempt lease epoch only protects ownership of that lease; it is not rechecked against the pairing file's bumped epoch.
- Consequence: new authenticated requests are refused, but previously admitted work can continue until its ordinary limit or completion despite the successful revocation acknowledgement. Retrying the same authenticated DELETE is also obstructed by the already-deleted credential. This is distinct from whether the coordinator accepts the eventual output (R26).
- Countercheck: if Redis is unavailable to the executor too, its poll stops work on a Redis exception. The finding requires a missing revocation write while executor Redis access remains or becomes healthy, not a claim that all Redis outages leave work running. The deployed executor deliberately has no pairing-credential mount; giving it secret hashes is not the recommended repair.
- Minimal correction recommendation: make revocation a durable, retryable fencing operation before reporting completion. Retain enough non-secret revocation intent to retry after the hash is removed, and preserve a visible failed/pending outcome if the executor fence is not committed.
- Test gap: the inspected tests cover successful cancellation/revocation and invalid credentials; they do not fail the API's revocation SET while keeping the executor's connection healthy. Static path confirmed; fault behavior not executed.

### R26 — P2 — Locally revoked worker streams can keep writing canonical attempt output

- Exposure: **deferred coordinator remote Chat**; ordinary packaged Beta disables mesh.
- Source: `backend/coordinator/server.py:3320-3349,3459-3480,3500-3515`; `backend/coordinator/dispatch.py:531-559`; `backend/coordinator/db.py:2957-2987,3066-3100`; worker stream lifetime in `backend/worker/app.py:856-906`.
- Trigger: a remote attempt is streaming. The user revokes its pairing locally, but the separate remote DELETE fails before reaching the worker while the existing stream remains usable. The coordinator intentionally still revokes the relationship and marks its attempt/job interrupted.
- Evidence: that local fence changes database state but does not signal the consuming thread. Its cancellation callback only checks the job's separate `_cancelled` set and application shutdown. `keep` unconditionally appends every subsequent delta and emits a new canonical event; `db.append_output` and `append_event` have no relationship/state fence. The client already owns its credential copy, so deleting it from the OS store does not close an existing stream. The worker authenticates an event stream at entry rather than consulting the coordinator's local relationship state.
- Consequence: output from an authority the user has just revoked can continue mutating the canonical interrupted attempt and reaching the UI until the stream ends or its other bounds expire. A completion/revocation interleaving can also pass the validating transition before revocation, then insert an assistant message before the later completion transition refuses.
- Countercheck: lifecycle validation does reject `interrupted -> validating/completed`; this is **not** a claim that ordinary late completion always resurrects the attempt as completed. Existing output already accepted before revocation should remain historical. The defect is accepting new output/final writes after the fence. A successful remote fence often narrows the window; local authority must also hold when the notification fails.
- Minimal correction recommendation: signal active consumers when revocation is recorded, and enforce the relationship/attempt fence inside the serialized output and final-message commit boundary. Stop accepting new deltas after the fence without rewriting the preserved interrupted history.
- Test gap: `test_dispatch.py:764-777` asserts the database state immediately after fencing, without calling the live consumer again or interleaving final-message insertion. No live stream or race was run in this review.

### R27 — P2 — Mac qualification merges checks without binding them to the same packages

- Exposure: **release-qualification tooling**, especially manual reruns or mixed artifacts. This is an evidence-binding bug, not a claim of a network attacker controlling trusted release operators.
- Source: `scripts/qualify_macos.py:124-168,189-217`; `scripts/qualification_record.py:90-122,143-168`; consumer `scripts/release_assemble.py:302-322`; normal workflow `.github/workflows/release.yml:288-297`.
- Trigger: run first-stage qualification on package set A. Before the floor run, replace the ZIP with a separately rebuilt ZIP B bearing the same public version, or accidentally select another set, then run `--floor --merge <A's partial report>`.
- Evidence: `main` copies only the earlier report's checks into the new report. It never compares the earlier `packages`, lane, source or identities with the current files. The floor branch launches the DMG app and returns before the ZIP seal, DMG/ZIP equality, binary-floor and first-stage ZIP launch checks. The final `package_entry` calls then hash the **current** files, binding A's carried checks to B's bytes in a new passing record.
- Consequence: release assembly and feed staging can receive an exact-current-hash record that claims first-stage checks which were actually performed on another package set. In particular, a current ZIP need not have passed the carried equality/launch/minimum-OS checks. Assembly independently rechecks Mac seals, so this finding does not claim that it accepts an invalid signature solely because of the merged report.
- Countercheck: the committed workflow downloads the same named artifact for both hosts; that normal path reduces the chance of mismatched inputs. `qualification_record.check` correctly rejects an unchanged old report beside new bytes. It cannot recover the lost provenance once the merger itself has rehashed new files and copied old check booleans. Version equality alone is insufficient for a release-bytes record.
- Minimal correction recommendation: reject merging unless the prior record names exactly the same packages, sizes, hashes and embedded identities, with the expected lane/source. Preserve each host's observations only after that match; otherwise rerun the missing checks on the new bytes.
- Test gap: the inspected record tests reject old reports and missing checks; the native qualifier test replaces qualification with simulated checks. No inspected test merges a valid partial record with different current bytes. No native qualifier was run here.

### R28 — P2 — Withdrawing a release keeps the withdrawn build's compatibility requirements

- Exposure: **signed Beta/preview feed publication and installed update admission** after a withdrawal. The publisher is trusted; the problem is incorrectly constructed signed metadata.
- Source: `scripts/update_repository.py:654-661,869-910`; validation `675-702`; client `backend/coordinator/updates.py:899-906,928-953`; withdrawal test `backend/coordinator/test_updates_beta.py:454-461`.
- Trigger: a Mac on 14.x runs beta.1; beta.2 supports macOS 14.0; beta.3 raises the minimum to 15.0. Withdraw beta.3 by pointing `latest.json` back to beta.2. Keep schema/signing otherwise equal so the OS gate is the decisive failure.
- Evidence: `withdraw` loads the **current** pointer and changes its version, maturity, public build, build set, payload names and notes. It leaves `min_os`, `schema_version`, `qualified_migrations`, engine release and prerequisites from beta.3. `_check_staged` validates payload version/format, but does not detect this mismatch. The client compares the carried `min_os` before offering beta.2, so it reports that beta.2 needs 15.0 even though its original offer supported 14.0.
- Consequence: an intended recovery of the last good update can remain unavailable to eligible older installations. Differing schemas/migrations can similarly produce a false incompatibility decision; displayed prerequisites/engine information can name the wrong release. This is not an instruction to downgrade installations already running beta.3.
- Countercheck: a client already at beta.2 correctly sees the restored pointer as not newer, and an existing beta.3 installation is not automatically downgraded. The present withdrawal test covers that not-newer case with identical compatibility fixtures; it does not cover an earlier client still eligible for beta.2.
- Minimal correction recommendation: restore the original compatibility metadata of the selected historical release along with its payloads, using its authenticated historical offer. If that evidence cannot be recovered, refuse withdrawal visibly rather than inherit the withdrawn release's requirements. Preserve signed-package immutability and anti-rollback behavior.
- Test gap: add a three-release withdrawal case with different OS minimums/schema metadata and an earlier eligible client when offline tests are authorised. This review did not execute it or alter a feed.

### Rejected candidates and evidence limits

- **Dropped SSE events permanently strand Chat:** rejected. The browser repairs sequence gaps and polls the canonical job events every two seconds while work is active (`app.js:366-374,6055-6060`). Queue-full drops alone do not support the proposed permanent-stall finding.
- **SSE creates an unconditional update-drain deadlock:** rejected. Shutdown signals `stopping` before the HTTP shutdown/drain, and the SSE loop observes it. This is separate from retained R06's Code cancellation mismatch.
- **Generic local HTTP CSRF/path traversal:** not established by the inspected paths. Strict Host/Origin/fetch-site checks, bounded typed bodies and resolved static-file containment are present. This is not an exhaustive web-security clearance.
- **Missing lanes make release assembly automatically unsafe:** not promoted. The assembler deliberately records unavailable lanes; strict Beta feed staging has its own all-lane gate. Product availability, publication and device acceptance must remain distinct.
- **Credential deletion can abort the local revocation before its database fence:** rejected for the inspected supported backends. The shared delete wrapper converts missing/failed store deletion to `False`; deleting the credential copy also does not cancel a stream, which is why R26 remains valid.
- No speculative performance/style cleanup or new P1 was added. R24–R28 are five distinct P2 failures at persistence, executor-fence, canonical-consumption, qualification-merge and signed-offer boundaries. Existing findings retain their Session 04 dispositions: **27 retained total (4 P1, 23 P2), plus withdrawn/unresolved R01**.

### Session outcome and continuation

Verdict: retained worker code does not yet enforce revocation consistently across its process and persistence boundaries. Release tooling also needs its carried qualification and withdrawal metadata bound to the actual release. These are review findings for independent accept/reject/needs-evidence decisions, not an execution pass.

Continue the existing audit through the still-unread build driver, remaining qualification/key-management helpers, contracts/profile/hardware/catalog/provenance code, deployment policy and remaining browser/storage paths. Reconcile any later PR #86 findings before duplicating them. No task tree, new chat or delegation is created.

Not checked: test/reproduction execution, faults or races in a running process, model accuracy, physical devices, real OS credential observation, native installation/update journeys, live feed assets and complete repository coverage. Only review records and append-only ledgers are changed locally; the remote update is confined to this report and PR #88's description/conversation. Application source and protected documentation stay unchanged. The PR remains a draft with its intentional review-document conflict; no implementation, merge or five-hour/full-audit completion is claimed.

### Session 05 publication receipt — completed on resumption, 26 October 2026

- Session 05 was published on 24 October as head `1a844526ef5cf736fd78c20b47f542440b09af88`, report blob `01b67c69f283a12f51337898c5199f29cdfaf95b`.
- All five findings were also posted directly in [PR #88's conversation](https://github.com/prachi-satbhai0741/Refinix/pull/88#issuecomment-6385618078). The comment was retrieved on resumption and contains R24–R28.
- On 26 October, updated the PR title to **Review only: cumulative whole-codebase findings — DO NOT MERGE** and corrected its description to the Session 05 count, current report link and conversation link.
- Fresh GitHub reads returned `draft=true`, `mergeable=false`, `mergeable_state=dirty`, `auto_merge=null`; base remains `739c9c0f247a5cced5fe76fe50f832bbb551efb7`. Both the PR file list and audited-source-to-head comparison contain only `reviews/codebase-audit.md`. Local source HEAD/branch/index were preserved.

## Session 06 — 26 October 2026 — Build driver and package boundary

Resumed the authorised review and PR publication. The source is still `e6b9858d880c8200cce6e8a4ca2784190c662f44` on local `aditya`; no source drift is asserted. Preserved the review-only scope under the replacement agent instructions: no implementation, tests, live runtimes, installers, new tasks/chats or delegation.

Coverage: read `desktop/build.py` and `desktop/packaging_plan.py` completely; read `desktop/refinix.spec` completely; selected `setup_py2app.py:42-85,105-150`; build/reuse/public-checkout tests `desktop/test_build.py:150-234,453-495,577-602,620-650`; focused `docs/releases.md:250-285` and package workflow `174-203`. This traces source enumeration and staging, hashes, build numbering/reuse, OS-native package creation, engine placement, signing and final embedded-identity extraction. OS tools, dependency artifacts, engine downloads and finished packages were not run or inspected as runtime evidence. No private/untracked payload was created for a demonstration.

PR reconciliation: #86 still returned no published comments/reviews on resumption. #88 contained the agent's Session 05 publication and no independent verdict. Absence of published findings does not establish the other agent's execution status.

### R29 — P2 — A public build can package untracked frontend files outside its designated commit

- Exposure: **public build tooling on a reused/local checkout**. Fresh hosted checkouts reduce the chance of leftover files; this is not a claim that the current published packages contain private data.
- Source: `desktop/build.py:771-781,1431-1436,1494-1503`; `desktop/packaging_plan.py:230-247,396-406,430-440`; PyInstaller inclusion in `desktop/refinix.spec:23-25`; shared macOS frontend provider in `desktop/setup_py2app.py:52-53`. The designated-commit contract is also stated in `docs/releases.md:285`.
- Trigger: a checkout is at the designated commit and all tracked files are clean, but `frontend/app/local-debug.json` exists as a non-hidden untracked local file. Run a public build without `--scratch` on an otherwise qualified build host.
- Evidence: `check_release_checkout` asks Git to exclude untracked files. `frontend_data_files` recursively includes every non-hidden regular frontend file except two development names and `.cjs` suffixes, without checking commit membership. The same list supplies package data. `publishable` is then set true and the identity names the designated commit despite the extra packaged file not being in it.
- Consequence: local-only frontend material can enter a publishable package, and a later consumer cannot reproduce that package's application source from the recorded commit alone. If such a local file contains private debug information, packaging can disclose it. This is a conditional consequence, not an observation of a real secret or published leak.
- Countercheck: the extra file does affect the snapshot digests. That records the actual local content but never compares it with the designated commit, so it does not enforce the claimed clean-source boundary. Cross-lane digest agreement may catch contamination present on only one lane, and a fresh CI checkout generally excludes it; neither makes the builder's public admission correct for supported local invocations. Tracked dirty-file rejection and `--scratch` marking still work.
- Minimal correction recommendation: require every selected shipping/build source input to belong to and match the designated commit, or build public packages from a clean materialisation of that commit. Keep generated output/cache files outside that comparison; merely rejecting all unrelated untracked outputs is unnecessary.
- Test gap: `test_build.py:623-633` mocks clean/dirty tracked status. The inspected packaging/release tests do not connect an untracked shippable frontend file to the public-build guard. No untracked payload or package build was executed here.

### R30 — P2 — Normal retained-build reuse is rejected before the reuse check

- Exposure: **retained-artifact build tooling**, with prior build records supplied through `--records`. This does not break a first build on a fresh CI runner.
- Source: `desktop/build.py:180-223,540-574,1441-1467,1510-1522`; retained-byte reuse contract in `docs/releases.md:262-265`.
- Trigger: retain an internal.1 build's complete output and successful build record, place that record in the `--records` list, and rerun the identical internal.1 invocation with `--store` pointing at the unchanged artifacts. The record has the matching lane/input digest, all artifact names/hashes and `bundle_build=1` as emitted by `main`.
- Evidence: `main` calls `bundle_build` before computing the input identity or invoking `find_reuse`. `recorded_numbers` sees the prior build's 1; `bundle_build` immediately rejects the requested 1 as not above 1. The verified-byte reuse return is therefore unreachable for that ordinary repeat. `--plan` also comes after the refusal. A same-number repeat of a recorded public build has the same ordering problem.
- Consequence: an unchanged, complete retained build cannot be reused through the real CLI under its original label/number, despite being accepted by the isolated `find_reuse` helper. The operator is forced into a new label/build or a manual workaround, defeating the reuse contract and wasting a native build/qualification cycle.
- Countercheck: refusing lower/reused numbers is correct when producing **new** bytes; it should not reject returning already recorded, hash-verified bytes. The helper still rejects missing, changed, partial and unsafe artifact records. Its tests omit the real main path and their synthetic matching record lacks the emitted build number/version that triggers the earlier guard. No recommendation is made to relax publication immutability or relabel old bytes.
- Minimal correction recommendation: validate the requested label/number's shape, perform matching-input and retained-byte reuse, then apply strict increasing-number checks only if a new build will actually be created. Preserve every hash/completeness check and the monotonic rule for fresh artifacts.
- Test gap: `test_build.py:161-232` exercises `find_reuse` directly; `455-491` tests numbering separately. Their interaction through `main` is the missing case. No build, plan invocation or test was run in this review.

### Counterchecks and remaining scope

- Public packaging's engine/archive hashes, embedded-identity extraction, platform signing checks and private-build marking remain present in source. R29 does not claim those checks are absent or that an arbitrary remote actor can write the release host's files.
- Unchecked metadata is not automatically a security exploit: the builder's explicit `--macos-minimum` is absent from the reuse-input components, but that candidate is left unpromoted here while the earlier reuse failure and intended label/number semantics are distinguished. It is not included in the finding count.
- Device acceptance records are tied to lane/shared source and required observed checks; a local record is not itself physical-device evidence from this audit. No acceptance forgery payload was created.
- The existing four P1 findings remain in their previously qualified product scopes. Session 06 adds two P2 findings, for **29 retained static findings (4 P1, 25 P2)**; R01 remains withdrawn/unresolved. These are findings for independent review, not repair tasks or approval to execute.

Verdict: complete the public package-input boundary and the CLI's reuse ordering before treating the build driver as enforcing its stated source/reuse contract. The whole-codebase audit remains open. Next coverage should continue through the remaining native qualification/key-management helpers, dependency provenance, contract/profile/model selection, deployment policy and browser/storage paths recorded earlier.

Not checked: application/test execution, actual build/reuse, native tools, models, downloads, physical-device acceptance, live feeds and complete repository coverage. Only the cumulative review file, local request/change ledgers and PR #88's report/summary/conversation are in scope. No application fix, protected-document change, production branch update, merge, new task/chat or delegation is performed.
