# Releases, installation and application updates

Status: agreed product contract, recorded 2026-09-14; implementation and platform
qualification remain planned. [prd.md](prd.md) owns scope; [security.md](security.md)
owns security boundaries. No build, signing, hosting or release action is authorised
merely by this document.

## 1. Release readiness

Release when the supported product passes acceptance, not on a calendar deadline.
The first public core includes both clean installation and an update path proven
between two test versions. A downloadable source archive or a working development
checkout is not an end-user installer. Publish the tested OS version/edition,
architecture, GPU/CPU backend and capability matrix; do not promise every existing
computer, driver or Linux distribution is compatible.

Retain the current UI and harness. Package qualified application dependencies and
provide graphical model selection/import. Normal end users should not configure
Python, Kubernetes, certificates or package managers in a terminal. Explain required
OS approvals and unsupported prerequisites. Sandbox installation must be qualified
early; native peer inference does not establish safe local code execution.

Current source boundary: [.github/workflows/ci.yml](../.github/workflows/ci.yml)
checks main pull requests and pushes on a Linux runner. It does not implement the
multi-platform build/sign/publish/update pipeline below. Existing macOS packaging
is a prototype path, not evidence of signed public installers for all platforms.

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
                    publish update metadata last
                               |
              website download / in-app Check for updates

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
  stable feed only after all required artifacts and gates for that release pass.
  A failed or incomplete build leaves the previous stable version advertised.
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
- Start with one stable user channel. Development artifacts must not appear as
  normal updates. A preview channel and staged rollouts can follow a measured need.

GitHub supports tagged releases containing notes and binary assets; an Actions
artifact used during a build is not automatically an end-user release.
[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

## 3. User update workflow

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
   jobs; pause remote admissions and reconcile attempts before replacing processes.
7. Back up affected durable state, perform the qualified platform installation and
   versioned migration, then start and check the new application.
8. Confirm the installed version and preserved state. On failure use the tested
   recovery path and explain what happened, without claiming a successful update.

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
| Chats, instructions, memory and corpus | Preserve outside installation directories; no automatic training or export during update |
| Model weights | Separate versioned artifacts; preserve compatible installed weights, avoid redundant downloads |
| New capabilities | Explain optional downloads, permissions, licence and hardware needs before enablement; no runtime fetching |
| Database/config migrations | Record schema version; preflight storage; consistent snapshot and recoverable migration. Do not merge incompatible stores blindly |
| Corpus/index changes | Preserve source data; rebuild derived indexes when embedding/extraction versions change; block stale/incompatible index use until ready |
| Peer/server protocol | Advertise versions and capabilities; permit qualified mixed-version combinations and reject incompatible jobs before dispatch |
| Worker upgrades | Drain admissions and reconcile accepted jobs; a dropped connection is not proof that work did not execute |
| Rollback | Restore a compatible binary and data state; never open a newer incompatible schema with an older binary |

A rollback snapshot covers affected schemas/configuration and must be tested. Avoid
silently discarding work created after the snapshot: diagnose before restore and
preserve/export recoverable newer data as appropriate. Recovery is a controlled,
known-good operation, distinct from accepting an arbitrary old update from a server.
Snapshots and downloaded packages have visible retention/storage policies.

## 6. Acceptance before first publication

Use two built versions, N and N+1, on every supported installation profile. Record
source commits, package hashes, signing identity/trust result, OS/architecture,
fixture state and actual observations. Required cases:

- Clean install, model setup/import, offline core workflows and first launch.
- Explicit metadata check; no updater traffic before the user requests it.
- Valid full update and verified offline import, followed by an offline restart.
- Interrupted/cancelled download, offline host, missing asset and insufficient disk.
- Modified package/metadata, wrong platform, incompatible version, stale replay and
  invalid signer; no partial installation or user-data changes on rejection.
- Active local/remote jobs, orderly drain/cancel, restart and attempt reconciliation.
- Chats, selected models, personal instructions, corpus permissions and credentials
  retained; derived indexes either valid or explicitly rebuilding.
- Migration failure/crash and recovery with consistent state; later user work is
  not silently overwritten by rollback.
- Supported mixed-version peers and explicit refusal of incompatible combinations.
- Graphical install/update completed by a nontechnical operator; unsupported host
  prerequisites surfaced without terminal debugging.

Passing ordinary unit tests alone does not establish installer or updater acceptance.
Release manifests, evidence and end-user files must agree. The website publishes
only the qualified support matrix and actually available stable artifacts.
