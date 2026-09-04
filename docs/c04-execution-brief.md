# C04 — Claude executes; Codex orchestrates

C03 was accepted by the requester on **2026-09-04**. The next authorised chunk
is C04: worker/API implementation, review, then an actual Ubuntu image build.
The first configuration remains the macOS coordinator plus Ubuntu worker.
OCR belongs to C08 Documents. Additional execution devices remain deferred.

## Send this to Claude

```text
Execute C04 in /Users/adityatadge/Documents/GitHub/AegisForge.
C03 is accepted. You implement; Codex reviews and coordinates the device gates.

Read AGENTS.md, the C04 row in tasks.md, backend/contracts/README.md and v1.py,
backend/worker-image/, the OD-06 pairing policy in docs/security.md, and the
relevant OD-03/OD-08 runtime/image decisions. Preserve the current dirty tree.
Do not re-open C03 acceptance or the removed three-device/OCR-worker requirement.

Build the smallest working worker/API and final Docker assets against those
contracts. Reuse existing validation and runtime behavior where appropriate;
do not copy coordinator-owned chat/database/UI logic into the worker. Use the
already pinned FastAPI/Uvicorn worker dependencies and approved model/runtime.
Keep Ubuntu at its measured context settings; the Mac's 8192 measurement is
not permission to raise Ubuntu's context or add models.

Cover truthful health/capabilities, bounded authenticated job admission,
attempt-scoped status/events/cancellation and runtime failures, following the
contract. Never acknowledge work as accepted without the required durable
receipt. Implement the C04 worker pieces needed by the later deployment and
dispatch stages; do not build/deploy the entire C05/C06 stack in this chunk.
If a later dependency is absent, fail closed with a typed unavailable result;
do not present a mock response, permissive auth stub, or in-memory queue as
successful distributed execution. Worker observations are not canonical job
completion. Keep replay, fencing and cancellation semantics compatible with
the existing contract even where integration proof belongs to C06.

Follow OD-06 exactly: pinned TLS and explicitly confirmed fingerprint before
pairing credentials are sent, single-use expiring bootstrap code, scoped
revocable relationship credentials, hashed worker credential storage, and
Mac Keychain for eventual coordinator credentials. No shared development
token, blind trust-on-first-use, verify=False, or secrets in SQLite/logs/Git.
Pairing must remain unavailable wherever its required controls are incomplete.
Implement worker-side prerequisites now; real device pairing is a later gate.

Keep request, runtime, output and capacity bounds; enforce authenticated
workspace/attempt ownership; avoid leaking prompt/body/credential data in
errors. Only advertise capabilities supported by observed local runtime state.
No arbitrary shell execution or new sandbox capability in C04.

Extend the existing build allowlist and provenance, run as non-root, replace
the contract-export image command with the actual worker entry point. Reuse
the pinned linux/amd64 base and hashed dependency lock. Include proportionate
runnable checks for the trust boundaries and worker behavior. Run only checks
available with installed dependencies and synthetic temporary state; if an
API dependency is absent on this Mac, put its check in the reviewed image
build and clearly report that it has not run yet. Do not install it silently.

Prepare exact final Ubuntu build, isolated image-check and artifact-inspection
commands for Codex to review. Device: Ubuntu 24.04.4 LTS, x86_64, bash,
/home/prachi/SIH/AegisForge. Select native Docker explicitly with:
env -u DOCKER_HOST -u DOCKER_CONTEXT docker --host unix:///var/run/docker.sock
Preserve Jenkins on 8080. Distinguish the local image configuration ID from
the actual deployable manifest digest. Specify a supported local artifact
path for the later K3s import, with integrity verification; do not invent a
digest or presume permission to upload an image to a registry.

Your handoff must include exact changed paths, observed checks and unrun
checks, sources/versions/licences/hashes and storage budget for build downloads,
expected Ubuntu evidence, and rollback confined to new task-owned artifacts.
Label source implementation separately from an actually built/verified image.
Keep the September 8–9 internal demo target; report scope that will not fit
instead of weakening acceptance gates.

No Git/GitHub writes, new dependency/model installation, Docker image build,
cluster provisioning/deployment, host/service/firewall changes or LAN listeners
on this Mac. Do not touch real coordinator history. Do not start C05/C06.
Update relevant implementation docs and append the required repository ledger
entries with new unused IDs, linking UP-20260904-010 as the initiating request.
Do not rewrite historical entries or overwrite other agents' changes.

Execute the C04 source work now. Stop at the reviewable Ubuntu image-build
checkpoint and return the handoff to Codex. Ask only for a missing prerequisite
that cannot be resolved from current source and approved decisions.
```

## VERIFY — RUN THESE YOURSELF

### Connect the devices to the same trusted LAN

1. On both devices, join the same trusted router's regular Wi-Fi, or connect
   by Ethernet to that router. Avoid its guest network. On macOS use Control
   Center → Wi-Fi; on Ubuntu use the top-right network menu → Wi-Fi settings.
   This is network preparation, not application pairing. If they are in
   different locations, first bring them onto a shared reachable network.
2. **Mac coordinator:** macOS 26.6.2, arm64, zsh, any directory. Run this after
   changing Wi-Fi to obtain the current address:

   ```sh
   /usr/sbin/ipconfig getifaddr en0
   ```

   Codex observed `192.168.68.132` on 2026-09-04, through gateway
   `192.168.68.1`. That address can change after switching networks.
3. **Ubuntu worker:** Ubuntu 24.04.4 LTS, x86_64, bash, any directory. Run:

   ```sh
   ip -4 -brief address show scope global
   ip -4 route
   ping -c 3 192.168.68.132
   ```

   The ping uses the Mac address just observed. If step 2 reports a different
   address, replace the address in the ping command with that result.
   Return these three outputs to Codex. Successful replies show basic
   Ubuntu-to-Mac reachability; Codex can check the reverse direction after
   receiving Ubuntu's current address. A failed ping needs diagnosis because
   ICMP filtering or client isolation can block it; it does not by itself prove
   the application cannot connect. Different IPv4 ranges alone are also not
   proof that two machines cannot communicate.
4. Keep the Mac app at <http://127.0.0.1:8770> and Ollama on loopback. There is
   no working application pairing button to use yet. C04 builds the worker,
   C05 deploys and integrates it, and C06 proves the complete paired workflow.
   The worker uses reviewed TLS exposure at 8443/30443; Redis stays internal.
   Do not expose 8770/11434, forward router ports, disable firewalls, or enable
   SSH merely to perform these checks.

These commands install nothing. Changing Wi-Fi can be rolled back by rejoining
the previous network. Missing LAN evidence does not block C04 source work;
successful ping does not clear deployment or pairing gates.

### Return from Claude

Give Codex Claude's changed files and execution summary. Codex independently
reviews the source and permitted checks, resolves defects, and then supplies
the reviewed final Ubuntu image-build commands. Do not use the old
`worker-base:c04-prep` build as the final C04 worker.

Direct dispatch status at handoff: Claude Code **2.1.246** is installed, but
`claude auth status` reports `loggedIn: false`; no existing Claude browser
session is available through the enabled browser tool. This brief has **not
been sent or executed** by Claude. Paste the block into the existing Claude
conversation to start; no new CLI setup is required for that route.

## GIT / GITHUB — RUN THESE YOURSELF

Repository: `/Users/adityatadge/Documents/GitHub/AegisForge`.
Observed status: `## aditya...origin/aditya [ahead 1]`, with existing C03 changes.
No Git writes were performed. These are the exact paths for this acceptance
and orchestration update; inspect existing hunks before staging shared files:

```sh
cd /Users/adityatadge/Documents/GitHub/AegisForge
git status -sb
git branch --show-current
git diff -- tasks.md backend/worker-image/README.md agent-memory/userprompts.md agent-memory/agentchangelog.md
git add tasks.md backend/worker-image/README.md docs/c04-execution-brief.md
git add -p agent-memory/userprompts.md agent-memory/agentchangelog.md
git add docs/c03-repair-handoff.md
git diff --cached --stat
git commit -m "Record C03 acceptance and prepare Claude C04 execution handoff"
```

`docs/c03-repair-handoff.md` is still untracked and includes the prior C03
repair handoff: stage it only after reviewing that whole file. The ledger
files also contain earlier changes. Follow the member branch → dev → main
flow when a later Git transfer is explicitly authorised; worker code must
reach the Ubuntu checkout before its image build can run.
