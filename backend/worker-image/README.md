# C04 worker image

Builds the worker service in [`backend/worker`](../worker/README.md) against the
`/v1` routes the contract reserves.

**Ubuntu build pending.** Claude reports 52 offline image checks for the latest
source (8 contract, 10 runtime, 34 worker behaviour). Codex checked that source
count, but has not repeated the container build. The earlier 37-check image and
streaming measurements in `provenance.json` remain historical evidence.

Job routes currently return `503`; pairing and the durable receipt are not
implemented. Health remains available for preflight. C05 uses the manifest
digest from the actual Ubuntu artifact, not a historical Mac image.

## What is pinned

- The existing OD-08 Python 3.13 / Debian bookworm **linux/amd64** manifest,
  SHA-256 `2f2e5a876c71a6757f55ec57f2add0225ddaf01c802a33fcc29073943f94d907`.
  The manifest bytes were fetched again from Docker Hub and matched this hash.
- Plain FastAPI **0.141.1** and Uvicorn **0.52.4**, with their thirteen total
  direct/transitive wheels pinned and hashed in `requirements.lock`. Optional
  CLI, cloud, reloader and other extras are not included.
- The contract dependencies keep exactly the versions in
  `backend/requirements.txt`. AnyIO **4.12.1** satisfies this target's metadata
  without changing the shared typing-extensions pin. Dependency metadata was
  checked for Python 3.13/Linux; the Ubuntu build verifies the imports there.
- `Dockerfile.dockerignore` denies everything except the named build inputs
  and worker/contract files. The image runs as UID/GID **10001:10001**. The
  build runs 52 synthetic contract/runtime/worker checks with networking disabled.

[`provenance.json`](provenance.json) records official metadata/download URLs,
exact wheel filenames, SHA-256 values, sizes, licences and target dependencies.
No upstream source was modified. Registry metadata is evidence for the selected
artifacts; wheels will be downloaded and hash-checked only during an authorised
build. [pip hash checking](https://pip.pypa.io/en/stable/topics/secure-installs/)
and [Docker build-context exclusions](https://docs.docker.com/build/concepts/context/#dockerignore-files)
are the mechanisms used here.

## Ubuntu build checkpoint

Use the [reviewed Ubuntu commands](../../docs/c04-ubuntu-build-handoff.md).
They create a separate, digest-pinned BuildKit **v0.33.0** `docker-container`
builder on `unix:///var/run/docker.sock`, then explicitly export `type=oci`.
The builder's source, Apache-2.0 licence, verified linux/amd64 manifest digest
and download size are recorded in `provenance.json`.

This does not change the global Docker context, selected builder or image store.
It produces an OCI archive directly; it does not load a tag into Docker or use
`docker save`. Reserve 2 GiB for the build's cache and output. The handoff gives
Buildx prerequisites, expected evidence and removal of only task-owned resources.
C05 supplies the reviewed artifact import and runtime verification.
