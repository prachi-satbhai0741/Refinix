# Refinix — in-app update and app consolidation handoff

Prepared 7 October 2026. Repository: `/Users/adityatadge/Documents/GitHub/AegisForge`.

**Plan first.** Inspect current source and return one evidence-backed execution plan for independent review. The requested updater implementation and app deletion belong in that plan; do not execute them during this planning turn. This handoff supersedes older instructions about creating permanent review app copies or requiring a particular agent model.

## User's latest request — verbatim

```text
Yes, make it such that earlier we used to rebuild the application or in short update the application. Right now, you coding agent just create another refinex. Instead of that make it such that the application updates itself right and I can see the option of update so that I don't have to run the command or anything I can just click on my primary refinix app update it closes updates and then reopens
You know, just how claude code and codex have that update option. Accordingly, I want an update icon in my Refinix app. It could be either on the top left, top right, any place which is suitable according to the UI UX design.


Also delete all the refinix app which are unnecessary and apply this plan. Then we will shift to the qualifying packages and all that and the repository unwanted code cleanup.



Accordingly, I think Claude knows what the plan is. I want you to create a handoff and then Claude reasons through what the remaining tasks are, what my additions are and accordingly create a plan for you to review.


Make sure my words are in the handoff. I'll copy your handoff and then paste it to Claude. And also after you giving me the handoff, I'll continue with you in the next chat.
```

## Current checkpoint — continue, do not restart

- Branch `aditya`, HEAD `c5ce035`, with substantial uncommitted implementation and two untracked additions: `.github/dependabot.yml` and `desktop/test_dependency_pins.py`. Refresh status and preserve every existing change. No Git/GitHub writes are authorized by this handoff.
- A–G implementation, the six-finding repair batch, and the final attachment/routing repairs are already present. The latest build is `desktop/out/local-review-20261007g`, version 0.1.0 internal, macOS arm64. Its ZIP SHA-256 is `3e095616d4a30cdc27402416d388c5cd3fe3f4419bc630ee3b842b377b76acc8` (36,029,987 bytes). Its 77-file shared application snapshot matched current application source at the last completed verification: `751f07172b79adc3b8ac990e55821f5580c026d051ad8015951b151ca084e95f`.
- The completed continuation ran 316 affected offline tests: 315 passed, 1 skipped. Packaged scratch checks verified the notes.txt answer, Word creation with the supplied contents, unreadable-PDF refusal before generation, Setup reopening while Ready, native Code folder connection, and the correct reviewable Code diff without modifying its file. Normal quit stopped the owned engine. Relaunch preserved chats, the document, connected project and rejected proposal. The final quit left no matching app/runtime processes at that checkpoint.
- Real `~/.aegisforge/coordinator.sqlite3` is already schema 15. Its database/WAL/SHM bytes were unchanged throughout the continuation. Do not open an incompatible old binary on that store or downgrade it. Refresh process/data state before any replacement or cleanup.
- Existing unpacked bundles are `desktop/out/local-review-20261006/unpacked/Refinix.app`, `desktop/out/local-review-20261007e/unpacked/Refinix.app`, and `desktop/out/local-review-20261007g/unpacked/Refinix.app`. Spotlight indexed all three. `/Applications/Refinix.app` and `~/Applications/Refinix.app` were absent when checked. Determine the intended primary installation from current facts; do not delete the working baseline before its replacement is verified.
- One cosmetic lifecycle event row displays `attempt start -> undefined` after document creation; the stored job/attempt state is completed. Include its small correction in the next coherent implementation if appropriate.
- Detailed completed evidence: `agent-memory/agentchangelog.md`, AC-20261007-003. Earlier broader suite/fallback results are historical evidence with their recorded provenance, not newly run checks.

## Reuse the existing updater

Read `AGENTS.md`, `docs/PROJECT.md`, active `tasks.md`, and the focused `docs/releases.md` / `docs/security.md` authorities. Trace these current paths before proposing new code:

- `backend/coordinator/updates.py`: existing python-tuf metadata verification, compatible offers, staged downloads, cancellation and verified offline bundle import. Its source explicitly says in-app installation is not implemented.
- `backend/coordinator/recovery.py`: existing workspace-lock-protected, journalled data snapshot/restore and crash recovery. Reuse this rather than inventing another backup system. Data recovery is not proof that binary replacement/relaunch already works.
- `backend/coordinator/server.py`: existing update API and coordinator ownership boundaries.
- `desktop/build.py`, `desktop/packaging_plan.py`, `desktop/lifecycle.py`, `desktop/shell.py`: existing package identity, native bridge, startup/shutdown and platform mechanisms.
- `frontend/app/app.js`, `control.html`, `index.html`, `code.html`, existing styles and tests: Settings already has Updates controls for checking/downloading/importing, but no Install and restart action.
- The current internal package has no update trust root/feed, so its unavailable-updater message is honest. A new icon alone cannot make updating work. Identify the missing trusted package-production/configuration and native installation path.

## Required outcomes for the plan

1. **One primary Refinix application.** Establish one stable installation location/identity and update that installation. Package building and temporary staging remain necessary; stop accumulating permanent unpacked review copies that appear as extra installed apps. Explain the one-time graphical bootstrap needed to install an updater-enabled build, since 7g cannot yet install an update itself. The user should not need terminal commands for bootstrap or subsequent updates.
2. **A visible, accessible update control.** Recommend a compact top-right control beside the existing header actions unless inspection shows a better placement. Preserve the current UI. Use a clear accessible label, keyboard operation and understandable states: checking, unavailable/offline, update available, downloading, ready to install, installing/restarting and failure. Keep Settings -> Updates as the detailed view. No fake enabled controls and no silent startup/periodic network checks.
3. **Click -> verified update -> close -> replace -> reopen.** Reuse authenticated metadata and staged package verification. Show version/notes/size, allow Later/cancel, handle active work through orderly drain or explicit cancellation, snapshot affected durable state, stop only owned processes, replace the correct installed application, reopen it, and verify the new version and preserved state. Report failure honestly and recover safely. Never run mutable-branch scripts or self-modify arbitrary source files as an updater.
4. **A usable development/review update path as well as the release path.** Explain how an agent-built, versioned package reaches the primary app through a graphical verified local/offline import or a configured trusted development channel. A source edit, push or new ZIP is not itself an installed update. Keep development trust separate from production; do not disable authentication to make private builds update. Do not require a public host for the local proof or invent missing signing credentials.
5. **Safe removal of duplicate apps.** Inventory exact bundle paths and active processes; verify recoverable ZIP/build records, a closed-app state snapshot and the working primary replacement before removing obsolete unpacked bundles. Prefer recoverable removal. Preserve source, all user data, credentials, model weights/Ollama stores and required rollback material. Never remove a running app's files. Name exactly which copies will go and which app remains. Include verification of the resulting Spotlight/launch behavior.
6. **Prove the update journey.** Use two labelled versions N and N+1 in isolated test data. They are controlled update fixtures, not permanent duplicate installations. Cover valid connected/offline updates, restart/persistence, modified or incompatible packages, interruption/cancellation, insufficient disk, active work, failed installation/migration and recovery without overwriting newer work. Reuse unchanged passing evidence; do not claim macOS proof establishes Windows/Linux acceptance.
7. **Then qualify packages and clean unwanted repository code.** Retain full Beta 0.1 requirements: Windows/macOS/Linux package/device checks, signing/notarisation as required, updater/recovery and user acceptance before publication. Keep offline WebView2 bundling, .deb primary/AppImage secondary and Dependabot in the remaining work. Signing identities, public hosting and actual device availability are human facts, not assumptions. Plan broad unwanted-code cleanup after package qualification as requested; delete only proven dead/superseded code after checking callers, compatibility, data and intended future use. Preserve deferred mesh/Kubernetes/Redis code.

## Decisions and constraints already settled

- Reuse the existing app, UI, harness, runtime adapters, models, storage and validators. Broad compatible local model choice and task-appropriate primary/secondary routing apply to any model, not just Qwen/PaddleOCR. Existing Ollama models stay in Ollama; model origin selects the runtime. Manual pins/running attempts remain fixed. Preserve approvals, sandbox/data boundaries and D1/D9 behavior.
- D1 accepts the correct whole, single-line Chat self-test forms `unsafe; smaller number: 2.4` and `unsafe; 2.4`; wrong/contradictory/prose/multiline replies fail. D9 treats a genuinely output-limit-incomplete result as current, task-specific Auto evidence, not a universal ban or a classification of crashes, unavailable runtimes or formatting-only failures. Preserve the v4 fingerprint semantics and successful-retest recovery.
- The date is flexible; full Beta gates remain. Unsigned local test builds are permitted; an unsigned public Preview was not approved. Do not confuse internal updater authentication with accepted public platform signing.
- One owner reasons, implements and integrates directly. No subagents, nested delegation, per-file task trees, repeated broad audits or unnecessary test/build reruns. A particular agent-model switch is no longer required; conserve tokens through compact context and coherent work.
- This turn is planning only: no application/source edits, app deletion/installation, live tests, downloads, migrations, host changes, Git/GitHub writes or publication. Protected-document changes require separately named user approval. List genuine human prerequisites once, with recommendations and trade-offs; continue independent planning.

## Return for independent review

Produce one coherent execution plan with: current facts versus missing behavior; existing code to reuse and exact affected paths; primary-app/bootstrap and repeatable-update mechanics; icon placement/states; precise duplicate-cleanup/recovery boundary; focused verification and acceptance criteria; remaining package/device/signing/hosting dependencies; and the proposed execution permission scope.

The user will paste your plan into the next review chat. The reviewer should return PASS with required additions, or NEEDS FIX with concrete points. Do not automatically execute because this handoff was pasted, and do not treat a planning PASS as release acceptance.

## Next review chat checkpoint

Read this handoff and AC-20261007-003, then review the implementation owner's returned plan against current source and the user's verbatim request. Preserve the dirty tree. Do not restart the completed repair batch, message another chat, or implement/delete/install before the next user execution checkpoint.
