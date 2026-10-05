# Releases, installation and application updates

Status: standalone Beta scope revised 2026-10-03; distributed architecture retained for post-Beta work.
Beta publication, platform qualification and updater acceptance remain unaccepted.
[PROJECT.md](PROJECT.md) owns scope; [security.md](security.md)
owns security boundaries. No build, signing, hosting or release action is authorised
merely by this document.

## 1. Release readiness

Release when the supported product passes acceptance, not on a calendar deadline.
Beta 0.1 qualifies standalone install/use/in-app-update/recovery on each of Windows, macOS and Linux,
using the bounded profiles in [PROJECT.md](PROJECT.md#25-platform-support-and-beta-scope). Distributed
execution and broader upgrade/peer matrices follow after Beta; they are not first-download gates.
The in-app updater is a current Beta target, not a claim of implementation or acceptance.
A downloadable source archive or a working development checkout is not an end-user installer.
Publish the tested OS version/edition,
architecture, GPU/CPU backend and capability matrix; do not promise every existing
computer, driver or Linux distribution is compatible. Publish supported minimum OS versions/ranges
separately from exact observed builds. Linux initially targets Ubuntu. Bind the shipped
[hardware/capability presets](model-catalog.md#reviewed-presets) to the package's engine/model manifests.

Use public model/runtime benchmarks to prepare candidate hardware tiers without owning every laptop.
Record external measurements and estimates separately from Refinix qualification. Obtain remaining
platform-specific package, sandbox and update observations on representative available devices,
appropriate CI environments or volunteer machines; ownership by the user is not a prerequisite.
An inference benchmark cannot establish native installer, credential-store, update or recovery safety.

Retain the current UI and harness. Package qualified application dependencies and
provide graphical model selection/import. Normal end users should not configure
Python, Kubernetes, certificates or package managers in a terminal. Explain required
OS approvals and unsupported prerequisites. Sandbox installation must be qualified
early; local inference does not establish safe local code execution. Beta must work without a peer,
private server or managed Kubernetes/Redis backend. Retain existing distributed code for later work.

The release team verifies the shipped app, core dependencies and representative workflows. Provide
a pinned, integrity-verified managed engine and support existing local Ollama reuse under the
[open-model runtime policy](PROJECT.md#13-runtime-and-resource-policy). Model origin selects the
backend without mandatory duplicate weights or a technical chooser. Customers do not create
qualification profiles; broad compatible model listing/downloads do not require team measurements.
Package/update/tool-security acceptance remains separate from model recommendations and admission.
Selected weights are explicitly provisioned/imported assets; no automatic download of every model.

Current source boundary: [.github/workflows/ci.yml](../.github/workflows/ci.yml)
checks main pull requests and pushes on a Linux runner. It does not implement the
multi-platform build/sign/publish/update pipeline below. Existing macOS packaging
is a prototype path, not evidence of signed public installers for all platforms.

### Release maturity

| Milestone | Required distribution scope |
|---|---|
| Beta 0.1 / SIH Reviewer Preview | Qualified standalone workflows on all three OS families, authenticated immutable packages, accepted in-app updates/offline import and tested manual recovery; no unfinished updater |
| Beta 0.2 / 0.3 | Deferred mesh and incremental product improvements; each changed/new profile repeats affected install/workflow/security/update checks |
| Finals candidate | A rehearsed version with a frozen, evidence-backed claim set; broader capabilities only when accepted |
| Production-qualified release | Full advertised OS/backend, upgrade/recovery, interoperability and managed-deployment matrices, as applicable |

Use a clearly labelled **Beta/preview channel** initially. Add a stable channel
only when its production gates pass; never label the reviewer preview stable.
Display versions such as Beta 0.1 consistently, with one authoritative package
version and explicit pre-release status. The prototype's existing `0.1.0` value
is not itself a published Beta. Current scope and sequencing are in
[PROJECT.md](PROJECT.md#28-release-phases) and [tasks](../tasks.md).
Historical release bands and P-task identifiers are not active publication gates.

<a id="beta-01-publication"></a>
### Beta 0.1 publication acceptance

Enable Download Refinix Beta only after the standalone Phase 5 gates in `tasks.md` pass and the user
accepts the evidence. This scope change grants no profile or updater acceptance. Before enabling the button:

1. Select and publish an exact OS/edition/architecture/backend/capability matrix,
   minimum measured resources, model/download sizes, prerequisites and limitations.
   Include at least one qualified desktop profile for each of Windows, macOS and
   Linux. Each supports useful standalone Chat/Documents/Code and the offered updater.
   Qualify Code sandbox validation on at least one eligible local profile; disclose validation limits
   on other profiles. No required Beta workflow or installation depends on a peer or managed sandbox.
2. Build an immutable package for each selected OS profile from the designated commit/version. Verify final
   shipped source/resources, dependency and model manifests, notices, integrity,
   publisher authentication and platform signing/notarisation where required.
   An ad-hoc prototype signature is insufficient public distribution evidence.
3. A nondeveloper completes website → download → install → hardware detection →
   model choice/download or supported offline import → self-test → real work.
   Exercise later Settings → Models management and all applicable local install/workflow/security
   cases from the
   [Beta acceptance matrix](evaluation.md#beta-acceptance) on the shipped bytes. Historical mesh cases
   remain post-Beta acceptance, not an override of the current standalone release scope.
4. Test first launch/relaunch, denied OS permissions, missing runtime/model,
   insufficient disk, cancellation, unsupported capabilities and uninstall/data
   preservation. Package/runtime provisioning is complete before offline tests.
   Shared source-level checks may be reused only when the tested code and inputs
   are identical; they do not replace platform-specific installer, credential,
   state-preservation or recovery observations.
5. Qualify the in-app update workflow and every case in
   [updater acceptance](#update-acceptance) using two labelled builds on each published profile.
   Also document and rehearse authenticated **manual full-package replacement** using
   two labelled test builds on **each published OS/architecture/backend profile**: stop/drain work, snapshot affected
   state, replace the app, reopen offline and verify chats, model references,
   credentials and artifacts. Prove recovery after a failed replacement without
   opening an incompatible newer schema or losing newer user work. An in-app updater is required
   for the current Beta scope; manual replacement alone requires a separate user-approved scope
   change. A schema migration is not compulsory; if one ships, its failure/recovery checks are
   mandatory. The complete future matrix is deferred,
   not basic data safety. Users can remain on a working offline version.
6. Release notes explain Beta limitations, supported models and execution targets,
   recovery/removal instructions and a support route that requires no automatic
   telemetry. Provide a local synthetic try-it workflow and expected outputs.
7. The user accepts the evidence and authorises publication. Upload verified
   assets before publishing the website link; verify the link actually downloads
   the matching package without an account. Record version, hash, profile and
   review date with the evidence. A source archive does not satisfy this gate.

The website/PPT can describe sovereign local AI, trusted heterogeneous compute,
model/device routing, sandboxing, recovery and organisation deployment. Every
functional claim uses Working now / Beta-experimental / Planned labels under
[current scope](PROJECT.md#25-platform-support-and-beta-scope); no unsupported Download option is
enabled. Describe mesh execution as post-Beta direction unless a separately named prototype has
observed evidence; do not present it as part of the standalone Beta package.

## 2. From source change to published version

    Member branch -> dev -> main
                               |
                          existing CI
                               |
                 designated new application version
                               |
              build each supported platform package
                               |
              package, upgrade and compatibility checks
                               |
                     sign and verify artifacts
                               |
                  publish versioned release assets
                               |
                    publish update metadata last (when qualified)
                               |
              website download / qualified in-app Check for updates

- Preserve [CONTRIBUTING.md](../CONTRIBUTING.md)'s branch flow. A change reaching
  main triggers CI; it does not itself update user installations.
- Designating a release means recording a new application version in a reviewed
  source change on main. Pin its source commit and release tag; one version names
  one immutable set of artifacts. Never silently replace bytes under an existing
  released version. A corrected build receives a new version.
- Use one authoritative application-version value for the UI, packages, tag and
  update metadata. Document major/minor/patch semantics and separate protocol,
  database-schema and model-artifact versions; matching app versions alone is not
  a compatibility check.
- Extend CI with builds/checks for each supported OS/architecture. Publish the
  chosen release channel only after all required artifacts and gates for that
  version pass. A failed build leaves the previous accepted version advertised.
- Sign only trusted release inputs in restricted build jobs, then verify the final
  distributed bytes. Signing keys must not reach untrusted pull-request jobs,
  source archives, binaries or logs. Preserve package manifests and notices.
- Initial distribution candidate: GitHub Releases with a small public update feed
  and website links to the same verified assets. Confirm hosting limits against
  actual package sizes; larger bundles may require a suitable artifact host.
  Users must not need GitHub credentials to install a public release. Internal
  deployments may mirror approved assets without contacting public hosts.
- Publish assets before updating the release feed, so the app never advertises a
  missing installer. Release notes describe behaviour, compatibility, migration,
  additional capability requirements and known limitations.
- Start with the Beta/preview channel described above. Development artifacts
  never appear as accepted Beta updates; stable and staged rollout policies follow
  their qualification. Publish update metadata only when that updater path exists.

GitHub supports tagged releases containing notes and binary assets; an Actions
artifact used during a build is not automatically an end-user release.
[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

### Internal test artifacts

Internal test packages are built by the same native driver
([desktop/build.py](../desktop/build.py)) and manually dispatched package workflow from one
reviewed source snapshot, for macOS, Windows and Ubuntu. They exist to produce test evidence on
real devices before any Beta release; they are not releases.

- **Unsigned and labelled.** Version `<app version>-internal.<n>` with a build-set id, channel
  `internal`, signing `unsigned`. They carry no publisher signature or notarisation, so testers
  follow the OS's documented unsigned-app step; this is never presented as normal installation.
- **Identity records.** Each package embeds `refinix-build.json`: version, build set, channel,
  source and input digests with their components, lock hashes, engine identity and trust-root
  identity, and never the package's own hash. After packaging, `<artifact>.sha256`,
  `<artifact>.manifest.json` (final name, size, SHA-256, embedded identity and its hash) and
  `<artifact>.TESTING.md` are written beside it. The identity is read back from the finished
  artifact and compared with the requested build. A Windows installer is read back only on a
  disposable runner.
- **Immutable and reused.** One label names one set of bytes. Unchanged inputs reuse a retained
  artifact only after its SHA-256 is read again and matches its record; otherwise it is rebuilt
  with a recorded reason. Old bytes are never relabelled. Separate N, N+1 and engine-change sets
  are kept for updater tests.
- **Separate trust.** Internal update metadata is signed by an internal test trust root whose
  keys are held apart from production roots and signing keys. A package built for the internal
  root does not accept production metadata as internal, and production builds never trust the
  internal root.
- **Test evidence only.** Observations made with these packages attach to the recorded SHA-256
  and support qualification decisions. They do not, by themselves, accept a platform, the
  updater or a release.
- **Never offered as a Beta update.** Internal artifacts are not published as release assets and
  never appear in the Beta update feed; a released Beta installation is never offered an
  internal build.

## 3. User update workflow

**Beta 0.1 qualification target.** Trace and reuse suitable existing update/packaging code before
adding new implementation. Acceptance is required on each advertised OS profile; a merged source
change, a release design or UI controls are insufficient. Do not render nonfunctional
Check/Download/Install controls or claim “up to date” without evidence.

Settings -> Updates shows the installed version, last check and Check for updates.

1. The user explicitly starts a connected check. Fetch only the required release
   metadata; do not send prompts, documents, hardware inventories or analytics.
2. Authenticate metadata and select an update compatible with OS, architecture,
   application/migration requirements and installed capability profile.
3. Show the offered version, release notes, package size, prerequisites and any
   new permissions or model downloads. The user chooses Download update or Later.
4. Download to staging, separate from the running application. Show progress and
   cancellation; support resume where the artifact host/installer permits it.
5. Verify authenticity and integrity before executing anything. Partial or failed
   verification never changes the installed app or advertises Ready to install.
6. Offer Install and restart. Drain work or obtain explicit cancellation of affected
   jobs and reconcile local attempts before replacing processes. When later releases offer peer
   execution, also pause remote admissions and reconcile accepted remote attempts.
7. Back up affected durable state, perform the qualified platform installation and
   versioned migration, then start and check the new application.
8. Confirm the installed version and preserved state. On failure use the tested
   recovery path and explain what happened, without claiming a successful update.

If this release changes the inference engine, the release team qualifies the new exact build and
supported model/workflow combinations before offering it. The app verifies and selects the managed
engine and runs the appropriate local installation checks without asking the customer to manually
requalify models. Unrelated system-engine updates must not change the installed Refinix engine.
Reject a package/qualification mismatch with its actual reason; preserve or recover the last accepted
compatible installation without losing newer work. A new available release does not disable the
current working offline application.

Being online briefly is sufficient only if the necessary transfer completes.
Interrupted downloads leave the installed version usable. Failed/offline checks
show unavailable or last checked, not an unverified Up to date result. Once all
required assets are verified locally, installation must work without public access
for the qualified installer profile.

No silent periodic, startup or network-reconnection checks. Configure
updater libraries and platform facilities accordingly. Application use does not
require accepting an update, renewing a cloud account or contacting the website.
An expired/invalid update offer is rejected without disabling existing offline work.

### Offline update import

Provide Import update for a verified package brought through removable media or an
approved internal host. Apply the same authenticity, compatibility, job-draining,
backup and migration checks. Do not bypass signatures or anti-downgrade checks merely
because a file came from USB. Fully offline update formats must include the required
trust metadata and assets; missing/expired metadata requires a fresh valid bundle,
not disabling validation or forcing public connectivity.

## 4. Update implementation and trust

Use established platform installers/updaters and signature libraries. The initial
strategy is full-package replacement with staged verification and tested recovery;
delta downloads are conditional on bandwidth/size evidence. The app should not
self-modify arbitrary source files or execute scripts from a mutable branch.

Evaluate Sparkle for macOS and qualified signed platform installation paths for
Windows/Linux. Evaluate TUF-compatible metadata handling where appropriate. These
are candidates: do not force a desktop-shell rewrite to obtain an updater, invent
cryptography, or assume a framework's defaults meet offline requirements.
[Sparkle](https://sparkle-project.org/), [TUF specification](https://theupdateframework.github.io/specification/latest/).

Before adopting an updater, record source, exact version, licence, supported OSes,
network behaviour, signing/verification, elevation requirements, crash recovery,
key rotation and recovery from key compromise. Metadata must bind the version,
platform, package location, size/hash and compatibility information to a trusted
publisher. Verify it using a packaged trust root or qualified platform trust path.
HTTPS and SHA-256 alone do not protect against a compromised publisher endpoint
substituting both an installer and its checksum. Reject tampered, incompatible,
replayed or unauthorised downgraded offers using the selected trust mechanism.

Production release qualification includes platform signing/notarisation where
required. The current ad-hoc signed Mac prototype is not equivalent evidence.

## 5. Data, models and compatibility

| Boundary | Required behaviour |
|---|---|
| Application files | Replaceable package; do not store user data inside it |
| App-managed inference engine | Pin executable/build, configuration and compatibility records to the release; external engines cannot silently replace it. Qualified app/dependency updates change it with tested recovery |
| Chats, instructions, memory and corpus | Preserve outside installation directories; no automatic training or export during update |
| Model weights | Separate versioned artifacts; preserve compatible installed weights, avoid redundant downloads |
| New capabilities | Explain optional downloads, permissions, licence and hardware needs before enablement; no runtime fetching |
| Database/config migrations | Record schema version; preflight storage; consistent snapshot and recoverable migration. Do not merge incompatible stores blindly |
| Corpus/index changes | Preserve source data; rebuild derived indexes when embedding/extraction versions change; block stale/incompatible index use until ready |
| Peer/server protocol (post-Beta) | Advertise versions and capabilities; permit qualified mixed-version combinations and reject incompatible jobs before dispatch |
| Worker upgrades (post-Beta) | Drain admissions and reconcile accepted jobs; a dropped connection is not proof that work did not execute |
| Rollback | Restore a compatible binary and data state; never open a newer incompatible schema with an older binary |

A rollback snapshot covers affected schemas/configuration and must be tested. Avoid
silently discarding work created after the snapshot: diagnose before restore and
preserve/export recoverable newer data as appropriate. Recovery is a controlled,
known-good operation, distinct from accepting an arbitrary old update from a server.
Snapshots and downloaded packages have visible retention/storage policies.

<a id="6-acceptance-before-first-publication"></a>
## 6. Update and production release acceptance

The old “before first publication” anchor is retained for incoming links; it no
longer requires the full production matrix before Beta 0.1. Use the Beta gate and per-profile updater
acceptance below first; broader historical-source-version and peer matrices remain later work.

<a id="update-acceptance"></a>
<a id="in-app-update-acceptance--band-b"></a>
### In-app update acceptance — Beta 0.1

Before exposing an updater, use two built versions, N and N+1, on every profile
for which that updater is offered. Record
source commits, package hashes, signing identity/trust result, OS/architecture,
fixture state and actual observations. Required cases:

- Clean install, model setup/import, offline core workflows and first launch.
- Explicit metadata check; no updater traffic before the user requests it.
- Valid full update and verified offline import, followed by an offline restart.
- Managed engine remains the recorded build after an unrelated system-runtime update or search-path
  change; no external engine is selected silently and offline work remains usable.
- A release transition changing the managed engine installs matching qualification records, runs
  local installation checks and completes supported model/workflow work without customer profile edits.
- Wrong/missing managed-engine bytes or corrupted identity/compatibility metadata produce a specific
  integrity/compatibility blocker and graphical recovery. Absence of a team-measured model profile
  alone is not a local admission failure; no spoofed identity or fabricated evidence.
- Existing local Ollama models remain available through their recorded source/runtime identity;
  preserve both stores, manual preferences and automatic routing without forced duplicate downloads.
- Interrupted/cancelled download, offline host, missing asset and insufficient disk.
- Modified package/metadata, wrong platform, incompatible version, stale replay and
  invalid signer; no partial installation or user-data changes on rejection.
- Active local jobs, orderly drain/cancel, restart and attempt reconciliation.
- Chats, selected models, personal instructions, corpus permissions and credentials
  retained; derived indexes either valid or explicitly rebuilding.
- Migration failure/crash and recovery with consistent state; later user work is
  not silently overwritten by rollback.
- After mesh is exposed: active remote jobs, worker drain/reconciliation, supported mixed-version
  peers and explicit refusal of incompatible combinations. These are post-Beta checks.
- Graphical install/update completed by a nontechnical operator; unsupported host
  prerequisites surfaced without terminal debugging.

Passing ordinary unit tests alone does not establish installer or updater acceptance.
Release manifests, evidence and end-user files must agree. The website publishes
only qualified profiles and actually available artifacts with their release channel.

<a id="production-release-acceptance"></a>
<a id="full-production-release-acceptance--band-c"></a>
### Full production release acceptance

Repeat the updater cases across every advertised OS/edition/backend and supported
source-version/schema transition, including mixed-version peers and managed worker
upgrades. Exercise publisher-key rotation/recovery and unsupported upgrade refusal;
preserve recoverable newer work on rollback. Record the supported transition matrix
rather than promising arbitrary old-version rollback. Complete
[production acceptance](evaluation.md#production-acceptance) before stable claims.
This is later production maturity, not an additional Beta 0.1 prerequisite.
