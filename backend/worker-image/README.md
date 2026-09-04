# C04 image inputs

**Prepared, not built.** The requester authorised preparation alongside the
two-device correction. The requester accepted C03 on 2026-09-04 and assigned
[C04 implementation to Claude](../../docs/c04-execution-brief.md), with Codex review. These files
prepare the Python/FastAPI/Uvicorn image and package the existing shared
contracts; they do not implement a worker API or clear C04.

After C03 acceptance, implement the actual worker/API against
[`backend/contracts`](../contracts/README.md) and the
[OD-06 pairing policy](../../docs/security.md#41-od-06--the-prototype-pairing-decision),
add its files to the build allowlist and replace the contract-export command.
Only then build the final worker image and obtain its immutable manifest
digest for C05. No fake health endpoint, new authentication scheme, network
listener, model download or cluster manifest is supplied here.

## What is pinned

- The existing OD-08 Python 3.13 / Debian bookworm **linux/amd64** manifest,
  SHA-256 `2f2e5a876c71a6757f55ec57f2add0225ddaf01c802a33fcc29073943f94d907`.
  The manifest bytes were fetched again from Docker Hub and matched this hash.
- Plain FastAPI **0.141.1** and Uvicorn **0.52.4**, with their thirteen total
  direct/transitive wheels pinned and hashed in `requirements.lock`. Optional
  CLI, cloud, reloader and other extras are not included.
- The five existing contract dependencies keep exactly the versions in
  `backend/requirements.txt`. AnyIO **4.12.1** satisfies this target's metadata
  without changing the shared typing-extensions pin. Dependency metadata was
  checked for Python 3.13/Linux; imports inside this image still need a build.
- `Dockerfile.dockerignore` denies everything except the named build inputs
  and contract files. The image runs as UID/GID **10001:10001**. The existing
  eight synthetic contract checks and an API-library import check run during
  the image build with networking disabled.

[`provenance.json`](provenance.json) records official metadata/download URLs,
exact wheel filenames, SHA-256 values, sizes, licences and target dependencies.
No upstream source was modified. Registry metadata is evidence for the selected
artifacts; wheels will be downloaded and hash-checked only during an authorised
build. [pip hash checking](https://pip.pypa.io/en/stable/topics/secure-installs/)
and [Docker build-context exclusions](https://docs.docker.com/build/concepts/context/#dockerignore-files)
are the mechanisms used here.

## Preparation-only Ubuntu build check — not the final C04 worker

Device: **Ubuntu worker**, Ubuntu 24.04.4 LTS, x86_64, bash,
`/home/prachi/SIH/AegisForge`. Use its already reported native Docker socket;
do not change the global Docker context or operate Jenkins on port 8080.
The account already has Docker access; no `sudo` or service changes are needed.

Build downloads come only from the pinned official Python image and the PyPI
wheels recorded above. Compressed image layers total **44,358,563 bytes**;
wheels total **3,250,094 bytes**, plus small registry metadata. Reserve **1 GiB**
in Docker's data filesystem for unpacking/cache; this is a preparation allowance,
not measured final image size. The image/cache are stored by the native daemon;
no model weights or private files are copied. This preparation image is never
deployed as the product worker.

The following commands build only the prepared dependency/contract image.
The next C04 checkpoint must instead use the final worker commands supplied
after implementation and Codex review; running this preparation check is optional:

```sh
cd /home/prachi/SIH/AegisForge
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock build \
  --platform linux/amd64 --target worker-base \
  --file backend/worker-image/Dockerfile \
  --tag aegisforge-worker-base:c04-prep .
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock image inspect \
  aegisforge-worker-base:c04-prep \
  --format 'ID={{.Id}} OS={{.Os}} Arch={{.Architecture}} Bytes={{.Size}} RepoDigests={{json .RepoDigests}}'
```

Return the complete build/check output and the inspect line. Success means
`pip check`, eight contract checks and the FastAPI/Uvicorn import pass, followed
by a `linux/amd64` image result. Missing Docker tooling, package/hash failure
or platform mismatch stays a build failure; do not install a substitute.
**The local `ID` is a configuration digest, not the deployable worker manifest
digest.** Empty `RepoDigests` is normal for this local preparation build and
does not clear C04's final-image gate.

Rollback of this check, if needed, removes only this new image tag:

```sh
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock image rm aegisforge-worker-base:c04-prep
```

No prune, daemon restart, global context change or cleanup of unrelated images
is required. Pairing, the selected model's runtime placement, real inference,
Redis integration and sandbox enforcement remain subsequent execution work.
