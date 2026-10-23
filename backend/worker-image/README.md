# C04 worker image

Builds the worker service in [`backend/worker`](../worker/README.md) against the
`/v1` routes the contract reserves.

The image builds current worker/contracts source and runs the synthetic suites
listed in [Dockerfile](Dockerfile), including API, executor and validation checks.
Pairing and durable receipts are implemented; missing configured prerequisites
still refuse jobs. [Current source/evidence](../../docs/evaluation.md#beta-source-audit)
must be distinguished from historical build measurements in `provenance.json`.
No current image build or deployment was rerun during the Beta planning audit.

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
  build runs the suites listed in the Dockerfile with networking disabled.

[`provenance.json`](provenance.json) records official metadata/download URLs,
exact wheel filenames, SHA-256 values, sizes, licences and target dependencies.
No upstream source was modified. Registry metadata is evidence for the selected
artifacts; wheels will be downloaded and hash-checked only during an authorised
build. [pip hash checking](https://pip.pypa.io/en/stable/topics/secure-installs/)
and [Docker build-context exclusions](https://docs.docker.com/build/concepts/context/#dockerignore-files)
are the mechanisms used here.

## Ubuntu build checkpoint

Start with [managed worker operations](../../docs/worker-operations.md) and the
authorised P-task. The [archived Ubuntu commands](../../docs/archive/c04-ubuntu-build-handoff.md)
retain the build method; refresh source/device facts before reuse.
They create a separate, digest-pinned BuildKit **v0.33.0** `docker-container`
builder on `unix:///var/run/docker.sock`, then explicitly export `type=oci`.
The builder's source, Apache-2.0 licence, verified linux/amd64 manifest digest
and download size are recorded in `provenance.json`.

This does not change the global Docker context, selected builder or image store.
It produces an OCI archive directly; it does not load a tag into Docker or use
`docker save`. Reserve 2 GiB for the build's cache and output. The handoff gives
Buildx prerequisites, expected evidence and removal of only task-owned resources.
C05 supplies the reviewed artifact import and runtime verification.
