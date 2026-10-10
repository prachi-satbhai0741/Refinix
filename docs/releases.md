# Releases, installation and application updates

Status: standalone Beta scope revised 2026-10-03; unsigned public Beta policy added 2026-10-10 on the
user's direction (Refinix Beta 0.1 is published, unsigned on macOS and Windows, before the user's device
walkthrough). Device acceptance and updater acceptance on people's computers remain unaccepted.
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
| Tester preview `0.1.0-preview.N` | Kept for compatibility (ordering, identity, the `latest-preview.json` pointer and install capability `preview-test`); not used for Beta 0.1 |
| **Refinix Beta 0.1** `0.1.0-beta.N` (maturity `beta`) | A normal GitHub release of immutable packages for all three OS families, built and natively qualified on hosted runners from one designated `main` commit ([Beta 0.1 publication](#beta-01-publication)); unsigned macOS (ad-hoc sealed) and Windows packages allowed, with each OS's warning shown before download; in-app updates with install capability `provisional`; **device testing pending** on every platform until it is observed and recorded |
| Beta accepted (device evidence) | The same channel after the user's device walkthrough: a recorded device-acceptance record per platform ([Beta acceptance](#beta-acceptance-device-evidence)) lets a later build carry install capability `qualified`; fixes ship as new immutable versions |
| Beta 0.2 / 0.3 | Deferred mesh and incremental product improvements; each changed/new profile repeats affected install/workflow/security/update checks |
| Finals candidate | A rehearsed version with a frozen, evidence-backed claim set; broader capabilities only when accepted |
| Production-qualified release | Full advertised OS/backend, upgrade/recovery, interoperability and managed-deployment matrices, as applicable |

Use a clearly labelled **Beta channel** initially, with three maturities: tester previews, the public
Beta and final. A maturity names the release class only; what was tested travels separately (each
platform's device-testing state and each package's bound native qualification record), so no label can
claim an acceptance that was not observed. Add a stable channel only when its production gates pass.
Display versions such as Beta 0.1 consistently, with one authoritative package
version and explicit pre-release status. The prototype's existing `0.1.0` value
is not itself a published Beta. Current scope and sequencing are in
[PROJECT.md](PROJECT.md#28-release-phases) and [tasks](../tasks.md).
Historical release bands and P-task identifiers are not active publication gates.

<a id="tester-preview-publication"></a>
### Tester preview publication

A tester preview exists so real devices can try the actual packages **before** acceptance. It is a
separate class beside the accepted Beta, never a substitute for it.

**Before publishing**, all of these hold:

- final source verified and the offline regression suites passing on the designated `main` commit;
- native builds, and installation smoke checks where a native machine or runner is available;
- identities, dependencies and final hashes verified (`scripts/release_assemble.py`);
- each platform's signing recorded as it is: Developer ID and notarisation for macOS, or unsigned
  with an ad-hoc seal that verifies strictly; Authenticode for Windows, or unsigned. Unsigned packages
  are published with the operating system's warning shown before the download. Ubuntu packages carry
  no platform signature (see [Linux authentication](#beta-channel));
- install and update recovery reviewed; no known problem that risks data or breaks a security
  boundary;
- "pending device testing" labels, limitations and recovery/removal instructions in place.

**Order:**

1. A fixed, immutable version (`0.1.0-preview.N`, with its own public build number B) from a
   reviewed `main` commit.
2. Verify the full set (`release_assemble.py`).
3. Upload to a **draft** GitHub release and verify the uploaded assets' names and sizes.
4. Publish the GitHub prerelease (immutable from then on).
5. Deploy the website links and the preview feed pointer (`latest-preview.json`).
6. Download anonymously **through the website** and check the bytes against `SHA256SUMS`.
7. Send testers a short install checklist that names the SHA-256 to record with observations.

Website download cards show OS/architecture, minimum requirements, version, "Tester preview",
device-testing status and limitations before download. A blocked platform is shown as
**unavailable**, never hidden.

<a id="beta-01-publication"></a>
### Beta 0.1 publication

On the user's direction (2026-10-10), Refinix Beta 0.1 is published **before** the user's device
walkthrough, and macOS and Windows packages are published **unsigned** when their checks pass. Public
availability and device acceptance are separate completion records. Before the release is published
and the website links are enabled, all of these hold, on one designated `main` commit:

1. Offline regression suites pass on that commit, and the commit's native qualification
   ([`qualify.yml`](../.github/workflows/qualify.yml): unit suites on each OS, release-bytes checks,
   packaged update/rollback/interrupted-update journeys with synthetic saved work, the Ubuntu
   sandbox) passed on the same file tree.
2. [`release.yml`](../.github/workflows/release.yml) builds all three lanes from that commit with the
   production Beta trust root, and qualifies every package on its exact bytes: the `.deb` with real
   dpkg/APT and a scratch-data launch, the Windows setup inside the real install job with file list,
   registration, scratch-data launch and uninstall, the Mac DMG and ZIP (strict ad-hoc seal, same app,
   every binary's minimum macOS at or below the declared minimum, scratch-data launch) and the same
   Mac bytes launched again on the oldest free arm64 macOS runner.
3. [`release_assemble.py`](../scripts/release_assemble.py) refuses unless every published file is
   named, byte for byte, by a passing native qualification record, identities agree, no file is a
   private `--scratch` build and every file name is plain.
4. Draft release → uploaded names and sizes checked → published as a **normal** GitHub release
   (not a prerelease). Feed targets staged offline; [`advance-feed.yml`](../deploy/distribution/workflows/advance-feed.yml)
   downloads each asset anonymously, checks its size, SHA-256 and final download host, signs, deploys
   exactly the signed commit and passes only when the live feed and site are exactly that commit's.
5. [`verify-public.yml`](../.github/workflows/verify-public.yml) downloads every file from the live
   website without credentials, matches `SHA256SUMS`, and installs and starts the published bytes on
   each OS's runner.

Hosted runners are not people's computers: Beta 0.1's device testing stays **pending** on every
platform, and its in-app installs are `provisional`, until the walkthrough below records otherwise.

<a id="beta-acceptance-device-evidence"></a>
### Beta acceptance (device evidence)

Recorded after the user's device walkthrough, per platform; it grants `qualified` install capability to
later builds of accepted source and changes the website's device-testing state. The checklist below
remains the acceptance content:

1. Select and publish an exact OS/edition/architecture/backend/capability matrix,
   minimum measured resources, model/download sizes, prerequisites and limitations.
   Include at least one qualified desktop profile for each of Windows, macOS and
   Linux. Each supports useful standalone Chat/Documents/Code and the offered updater.
   Qualify Code sandbox validation on at least one eligible local profile; disclose validation limits
   on other profiles. No required Beta workflow or installation depends on a peer or managed sandbox.
2. Build an immutable package for each selected OS profile from the designated commit/version. Verify final
   shipped source/resources, dependency and model manifests, notices, integrity,
   publisher authentication, and each platform's signing recorded as it is. For the Beta,
   unsigned macOS and Windows packages are allowed (user direction, 2026-10-10); an ad-hoc seal
   is integrity evidence, not Developer ID or notarisation.
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

The website and presentations can describe sovereign local AI, trusted heterogeneous compute,
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

<a id="beta-channel"></a>
### Beta channel: build, sign, assemble, publish

Implemented in source (8 October 2026); not yet exercised against live hosting.

| Step | Where | What |
|---|---|---|
| Version | reviewed `main` commit | `0.1.0-preview.N` / `0.1.0-beta.N` / `0.1.0`, public build number N above every earlier build of that lane — internal builds included, since macOS orders apps by `CFBundleVersion` (internal builds 1–6 already exist, so the first public build is 7 or higher); [release identity](../backend/coordinator/release.py) gives one ordering key and its Debian (`X.Y.Z~R.S`), macOS (`CFBundleVersion` N) and Windows (`X.Y.Z.N`) forms |
| macOS, Windows, Ubuntu | [`release.yml`](../.github/workflows/release.yml), manual, `contents: read`, hosted runners (macOS 15 arm64, Windows Server 2025, Ubuntu 24.04) | refuses unless started from `main` at the designated commit; every public build is a clean checkout of that commit (`--scratch` builds are never publishable); builds with the committed Beta trust root and feed (`desktop/updates/beta-*.json`) and the [pinned Python](../desktop/python_runtime.py) (python.org 3.13 installers, verified, on macOS and Windows; Ubuntu's python3.12); the macOS app is sealed ad hoc (or Developer ID signed and notarised when that is set up); Authenticode signing only in the `beta-sign` environment; every package qualified natively on its exact bytes ([`qualify_deb.py`](../scripts/qualify_deb.py), [`qualify_windows.py`](../scripts/qualify_windows.py), [`qualify_macos.py`](../scripts/qualify_macos.py), [record format](../scripts/qualification_record.py)); the Mac bytes run again on the oldest free arm64 macOS runner; outputs workflow artifacts only |
| Assemble | locally, [`release_assemble.py`](../scripts/release_assemble.py) | the run's commit/event/workflow/conclusion; every lane's identity agrees and is publishable; bytes re-hashed; plain file names; each lane's signing one it allows (unsigned recorded, never hidden); for unsigned Mac files a strict ad-hoc seal check of the app in the ZIP and in the mounted DMG and `hdiutil verify`, for Developer ID the Team ID, stapled ticket and Gatekeeper on a quarantined copy; every published file bound to a passing native qualification record; writes `SHA256SUMS`, `release.json` (with each platform's signing, OS warning, minimum OS and device-testing state), release notes and the exact publication commands; [`build-site.sh`](../scripts/build-site.sh) renders the website's download cards from `release.json`, showing minimum OS, warning and device-testing state before each first-install download |
| Release assets | GitHub release on the source repository | draft → verify uploaded names and sizes → publish (a normal release for the Beta; prerelease for previews); immutable once published |
| Feed | the website repository (`refinix.runs-on.dev/updates/beta/`), Pages deployed by GitHub Actions | targets signed offline on the release Mac (`update_repository.py stage`, which refuses a package without its bound qualification record); then [`advance-feed.yml`](../deploy/distribution/workflows/advance-feed.yml), behind a required reviewer, downloads each new asset anonymously, checks size, SHA-256 and that the download ends on a host installed clients accept, signs snapshot and timestamp, commits, deploys exactly that commit and passes only when the live feed (`update_repository.py expected` → `verify --expect`) and the live site and downloads are exactly that commit's |

**Feed rules.** Consistent snapshots; every file immutable except `timestamp.json`; versions only
increase; a published package target is never changed or dropped; a Beta or final release carries
every lane, a preview may carry only the ready ones. All feed writers and site deploys share one queue
(`beta-feed`); a deploy never replaces a newer tree. Failure before the commit changes nothing;
after it, redeploy the same commit or fix forward with higher versions — **never restore older
metadata**. Withdrawing an offer is a new targets version whose pointer names the previous build.

**Freshness.** Expiry: timestamp 7 days, snapshot 30, targets 180, root 365.
[`refresh-feed.yml`](../deploy/distribution/workflows/refresh-feed.yml) re-signs the timestamp daily
(and the snapshot below 14 days), deploys, reads it back and opens an issue below the alert levels
(timestamp 3 days, snapshot 7, targets 45, root 90). The release manager renews targets offline at
60 days or fewer and the root at 120 or fewer.

**Starting the feed (once).** On the release Mac, the release manager creates the Beta keys and the feed's first root, with the keys in a folder outside every repository:
`python scripts/update_repository.py init --channel beta --keys <release keys folder> --repo <refinix-site checkout>/updates/beta`. That root (`updates/beta/metadata/1.root.json`) is committed twice: to the website repository, where the feed starts, and byte for byte as `desktop/updates/beta-root.json` in the source repository, where every Beta package embeds it as its update trust root (`release.yml` refuses to build without it). Passphrases come from `REFINIX_KEY_PASSPHRASE_<ROLE>` or a prompt, never from a file in a repository.

**Keys.** The offline default in [security.md](security.md#101-the-beta-update-channel-as-implemented)
keeps root and targets keys in two encrypted offline copies. For Beta 0.1, the user approved a
custody exception on 10 October 2026: retain encrypted PEM files in a local archive outside every
repository and back them up in iCloud Drive; store the four role passphrases in Apple Passwords
with iCloud Keychain. This is encrypted cloud-backed custody, not an offline backup. The files and
passphrases use the same Apple account, creating a shared account-security and recovery dependency.
Backup recovery has not yet been checked. Owner-only permissions and Finder hiding do not block
an agent running as the same Mac user; agent access should be limited to the source repository,
with passphrases kept out of agent chats, output, ordinary files and logs.

Root and targets signing remains a manual release-manager operation; those private keys and
passphrases never enter GitHub. Only snapshot and timestamp private keys and their passphrases may
be supplied to GitHub, as secrets of the website repository's `beta-publish` and
`beta-feed-refresh` environments, never repository-level secrets or committed files. Their
encrypted local/cloud backups follow the approved custody above. Public root metadata and public
key IDs are intended to be committed; they contain no private keys or passphrases.

Someone holding only those online keys can never add a package; they could hide
updates for up to the remaining targets lifetime (180 days) or push versions ahead. Recovery: a new
root version, signed offline, replaces those keys; installed clients re-check cached metadata
against the newest root and drop what the revoked keys signed.

**Linux authentication.** No platform signature: first downloads are authenticated by HTTPS from
the release page and the published SHA-256; updates by the Beta TUF root embedded in the package.

**Credentials.** Only the website repository's own `GITHUB_TOKEN` (inside its environments) writes
the feed; the release itself is made with a maintainer's own GitHub credentials. No cross-repository
token is used. Workflow templates live in [`deploy/distribution/`](../deploy/distribution/README.md).

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

### Install and recovery by platform

Every attempt is journalled before each step and resumed from disk by the next launch; the user's
data is set aside before the app changes and restored if the new version does not commit (it
commits only after its window has loaded).

| Platform | Install | Going back |
|---|---|---|
| macOS (ZIP payload) | expanded and checked beside the app, swapped in with one atomic rename; the previous app kept | swap back; restore data |
| Windows (setup payload) | `{app}` set aside with its uninstall registration recorded; the verified setup runs silently inside a kill-on-close job it can never leave (created into the job from its first instruction); accepted only when every packaged file is present and unchanged and the registration names the new version | a crash before `install_verified` always goes back, even when the new identity file exists; previous `{app}` and registration restored exactly |
| Ubuntu (`.deb`) | **Download and prepare** ends with an administrator prompt: root copies the package, the installed version's package and the signed metadata into root-owned storage and authenticates the copies with the full TUF client, including expiry. **Install** asks again: `dpkg --audit` clean, `apt-get --simulate --no-download --no-remove` plans exactly unpack + configure of Refinix, then `dpkg -i` under dpkg's front-end lock | by dpkg state: same-copy repair, `dpkg --configure refinix`, the recorded trigger packages, or the exact recorded previous package; unrelated unfinished package work blocks with steps; root never writes user data |

After an admission, install, resume and rollback re-verify root's copies **without a clock**, so an
update interrupted today can still be recovered later; a **new** import with expired metadata is
refused. Accepted installations never take a preview from any source; previews may move on to
accepted builds. A package whose shipped root is neither the running one nor a newer root
authenticated from it is refused.

**Manual recovery.** macOS: drag the previous Refinix from the release page into Applications.
Windows: run the previous setup from the release page. Ubuntu: open the recovery `.deb` the update
kept in the data folder (`updates/recovery-packages/`, with its SHA-256) or the same version from
the website with App Center. The launch check reconciles the journals and checks the app before
the workspace reopens.

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

Adopted: TUF metadata through python-tuf 7.0.1's client (Apache-2.0 OR MIT; verification only in
the app, pure-Python Ed25519), with consistent snapshots and two signed pointers per lane
(`latest.json` Beta and final, `latest-preview.json` previews). Packages are release assets fetched
through the public TUF calls (`get_targetinfo`, the fetcher, `verify_length_and_hashes`); only those
downloads may follow HTTPS redirects, at most three, and only to hosts listed in the package's feed
configuration (`release-assets.githubusercontent.com`, observed by an anonymous request). Metadata
never follows a redirect. Platform installation uses each OS's own mechanism (atomic rename,
Inno Setup, dpkg). [TUF specification](https://theupdateframework.github.io/specification/latest/).

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
