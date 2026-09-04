# C04 — Ubuntu worker image build handoff

**Device role:** Ubuntu worker. **OS:** Ubuntu 24.04.4 LTS, x86_64.
**Shell:** bash. **Directory:** `/home/prachi/SIH/AegisForge`.

Build the pinned worker image, produce a local deployment artifact, and return
its **manifest digest**. Nothing is deployed here; cluster provisioning is C05.

Run this **only after** the fixes are merged into `dev` and you have pulled it.

## What was prepared

The worker API is implemented in [`backend/worker`](../backend/worker/README.md)
against the `/v1` routes the contract reserves. A `linux/amd64` build was run on
the macOS coordinator **under emulation** to verify the Dockerfile before this
handoff — you are not the first to run it.

That is **Claude-reported Mac evidence, not Ubuntu verification.** It was never
pushed anywhere. The earlier 37-check image digests in `provenance.json` are
historical; no digest for the latest 52-check source is claimed here. Codex has
not independently reproduced the container run.

| Observed on the Mac | Result |
|---|---|
| Wheels | 13, all `--require-hashes` verified against `provenance.json` |
| Latest reported checks inside the image | **52** with `--network=none` — 8 contract, 10 runtime, 34 worker behaviour; source test count independently checked |
| Image | 11 layers, `linux/amd64`, runs as `uid=10001`, `/app` not writable |
| Earlier streaming implementation | first output event at **2.73 s** of a 15.98 s generation, 417 deltas; current HTTP job routes are closed |
| Job routes | **fail closed**: all four return `503` with a typed reason |
| Startup guard | the container **exits 1** with no credential |
| Health | still answers, reporting `degraded` with empty capabilities while closed |

## Three identities, three different values

A deployment reference pins the **manifest digest**. These are distinct objects
([OCI image spec](https://github.com/opencontainers/image-spec/blob/main/manifest.md)):

| Value | What it identifies |
|---|---|
| **manifest digest** | the image — this is what goes in `name@sha256:…` |
| config digest | the image *configuration object* only |
| archive checksum | integrity of the transferred `.tar` file |

Do not infer the manifest digest from `docker image inspect .Id`. Read the
explicit OCI artifact with [`scripts/image-digests.py`](../scripts/image-digests.py),
which uses the standard library and changes nothing.

It supports the **OCI layout** (`index.json`). A classic
**Docker Archive** (`manifest.json`) records *no manifest digest at all*; the
script says so and exits `2` rather than presenting the config digest as one.
Enabling BuildKit does not select `docker save`'s archive format. The commands
below explicitly select [`type=oci`](https://docs.docker.com/build/exporters/oci-docker/)
using a dedicated [`docker-container` builder](https://docs.docker.com/build/builders/drivers/docker-container/).

## VERIFY — RUN THESE YOURSELF

Run each block in order and stop on errors. This checkpoint creates a dedicated
BuildKit container/cache and downloads pinned build inputs. It does not change
the global Docker context, selected builder, image store, host services or Jenkins.

```bash
cd /home/prachi/SIH/AegisForge
git status --short --branch
```

This host has two Docker environments reporting different servers and memory, so
select the native endpoint explicitly rather than changing any global context:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock info \
  --format 'Server={{.ServerVersion}} Arch={{.Architecture}} CPUs={{.NCPU}}'
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock buildx version
```

Buildx must already be installed. If its command is missing, return the error;
do not install an unreviewed substitute. The Mac CLI checked during preparation
was Buildx 0.36.1; Ubuntu's version is collected above, not assumed.

Create the task's builder. If this name already exists, stop and return
`docker --host unix:///var/run/docker.sock buildx inspect aegisforge-c04`;
do not replace an existing builder. Omitting `--use` preserves the selected one.

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock buildx create \
  --name aegisforge-c04 --driver docker-container \
  --driver-opt image=docker.io/moby/buildkit:v0.33.0@sha256:a461e7f0ce921972028acfbed628d45663d83e67ac1230722c2b34cf72760a0d \
  --driver-opt memory=2g --driver-opt memory-swap=2g \
  --driver-opt cpu-period=100000 --driver-opt cpu-quota=200000 \
  --driver-opt restart-policy=no \
  unix:///var/run/docker.sock
```

The builder image is **BuildKit v0.33.0, linux/amd64, Apache-2.0** from the
[upstream release](https://github.com/moby/buildkit/releases/tag/v0.33.0).
Its manifest bytes were SHA-256 verified; compressed layers total **112,271,581
bytes**. The existing pinned Python base is **44,358,563 bytes** compressed and
the thirteen pinned wheels total **3,250,094 bytes**. Full sources, licences and
integrity records are in [`provenance.json`](../backend/worker-image/provenance.json)
and `requirements.lock`. Reserve **2 GiB** for builder/image unpacking, cache and
the output archive; this is an allowance, not a measured final disk footprint.
Buildx starts its privileged build container at build time, with 2 GiB memory
and two CPUs allocated. No ports are published by these commands.

Build directly into a fresh output directory. Explicit OCI export works without
changing Ubuntu's image store. The flags omit optional attestations; the digest
reader also handles a supported nested OCI index.

```bash
c04_output=$(mktemp -d /tmp/aegisforge-c04.XXXXXX)
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock buildx build \
  --builder aegisforge-c04 \
  --platform linux/amd64 \
  --provenance=false --sbom=false \
  --file backend/worker-image/Dockerfile \
  --tag aegisforge-worker:c04 \
  --output "type=oci,dest=$c04_output/worker.oci.tar" \
  --progress plain \
  .
```

Expect **52 checks** with `--network=none` and a completed OCI export. A cached
test layer may be reported as `CACHED`; do not describe that as a fresh test run.

Read the artifact's identities in the same shell:

```bash
ls -l "$c04_output/worker.oci.tar"
python3 scripts/image-digests.py "$c04_output/worker.oci.tar"
```

That prints `manifest_digest`, `config_digest`, `archive_sha256`, the layer count
and a deployment-reference template. **The `manifest_digest` is what C05 pins.**
Keep the printed archive path for C05's reviewed import. No image was loaded
into Docker's image store by this export, so a local `docker run` by tag is not
part of this checkpoint.

## Runtime checkpoint

C05 supplies the reviewed import/start commands for this exact artifact. Until
pairing and receipt prerequisites exist, the expected Node has empty capabilities
and degraded/unavailable health; job routes return `503`.

**Container-to-runtime connectivity is deliberately not attempted here.** Ollama
binds `127.0.0.1` by default, so a Docker bridge gateway address does **not**
reach it, and the fix is not to expose Ollama on every interface. The reviewed
arrangement belongs with the Pod networking design in C05. An earlier draft of
this handoff asserted `172.17.0.1:11434` would work; that claim was untested and
has been removed.

## What to return

1. The complete build output, or the exact error if it fails.
2. The full `scripts/image-digests.py` output — especially **`manifest_digest`**.
3. The Docker info and Buildx version lines.
4. The archive path and size; keep the archive for C05.

## Rollback

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock buildx rm aegisforge-c04
```

Run that only for the builder created by this checkpoint; it removes its
container and dedicated cache. Keep the artifact for C05. To abandon this build,
remove only `worker.oci.tar` inside the printed task output directory and remove
that directory if empty. The downloaded builder image may remain cached.

**Do not run `docker system prune`.** This host had 28 images and 26 containers
in use at C02, Jenkins among them. Nothing outside this build's own image and
archive is touched, and the global Docker context is left unchanged.

## What this does not establish

A built image is not a running Pod. Kubernetes readiness, Service exposure,
Redis, NetworkPolicy enforcement, container GPU access and container-to-runtime
networking are all C05 and remain unverified.

The worker's pairing routes return `501`: OD-06 is a recorded decision, not an
implementation. Acceptance inside the worker is **in-memory and is not a durable
receipt** — the contract's "persisted before acknowledging" needs the AF-005
Redis receipt, which does not exist. Attempts do not survive a worker restart and
the worker never claims recovery.

## GIT / GITHUB — RUN THESE YOURSELF

Mac directory: `/Users/adityatadge/Documents/GitHub/AegisForge`.
Observed status: `## aditya...origin/aditya`, with C04 files modified/untracked.
Review the whole C04 diff before staging; these paths include Claude's worker
implementation and Codex's export correction. No Git writes ran in this fix.

```bash
cd /Users/adityatadge/Documents/GitHub/AegisForge
git status -sb
git branch --show-current
git add backend/worker backend/worker-image scripts/image-digests.py docs/c04-ubuntu-build-handoff.md tasks.md
git add -p agent-memory/userprompts.md agent-memory/agentchangelog.md
git diff --cached --stat
git commit -m "Implement fail-closed C04 worker and explicit OCI build handoff"
git push origin aditya
```

Merge through a PR from `aditya` into `dev`. On the clean Ubuntu checkout,
switch to `dev`, pull with `git pull --ff-only origin dev`, then run the build
checkpoint above. Stop on a dirty checkout or pull failure; preserve local work.
