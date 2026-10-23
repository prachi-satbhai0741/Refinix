#!/usr/bin/env python3
"""Report the identities of a saved image archive.

They are different objects and a deployment reference needs the right one:

  manifest digest  the value in `name@sha256:...` — what a deployment pins
  config digest    identifies the image *configuration object* only
  archive checksum integrity of the transferred .tar file itself

Read the manifest descriptor from an explicit OCI export instead of inferring
its identity from `docker image inspect .Id` or the selected build engine.

**Two archive formats exist, and only one carries a manifest digest.**

  OCI layout (`index.json`)      — `buildx build --output type=oci,...`.
  Docker Archive (`manifest.json`) — may be produced by `docker save`, including
                                     after a BuildKit build. No manifest digest
                                     is recorded by this format.
                                     This script says so rather than inventing
                                     a value or presenting the config digest as
                                     if it were one.

    python3 scripts/image-digests.py worker.tar

Standard library only. Reads the archive; changes nothing.
"""

import hashlib
import json
import sys
import tarfile


def _archive_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _member(tar: tarfile.TarFile, name: str):
    try:
        return tar.extractfile(name)
    except KeyError:
        return None


def _oci(tar: tarfile.TarFile, archive: str) -> int:
    index = json.load(_member(tar, "index.json"))
    descriptors = index.get("manifests") or []
    if not descriptors:
        print("index.json lists no manifests", file=sys.stderr)
        return 1
    if len(descriptors) != 1:
        print(f"note: {len(descriptors)} top-level descriptors; build with "
              "--provenance=false --sbom=false for one", file=sys.stderr)

    def blob(digest: str):
        return _member(tar, f"blobs/sha256/{digest.split(':', 1)[1]}")

    top = descriptors[0]
    document = json.load(blob(top["digest"]))
    manifest_digest = top["digest"]

    # An index points at per-platform manifests; unwrap to the linux/amd64 one,
    # skipping attestation descriptors, which carry annotations instead.
    if str(document.get("mediaType", "")).endswith("index.v1+json"):
        platform_manifests = [
            m for m in document.get("manifests", [])
            if m.get("platform", {}).get("architecture") == "amd64"
            and m.get("platform", {}).get("os") == "linux"
            and "annotations" not in m]
        if not platform_manifests:
            print("no linux/amd64 image manifest in this archive", file=sys.stderr)
            return 1
        manifest_digest = platform_manifests[0]["digest"]
        document = json.load(blob(manifest_digest))

    print(f"format           OCI layout (index.json)")
    print(f"manifest_digest  {manifest_digest}")
    print(f"config_digest    {document['config']['digest']}")
    print(f"archive_sha256   sha256:{archive}")
    print(f"layers           {len(document['layers'])}")
    print(f"deployment_ref   <image-name>@{manifest_digest}")
    return 0


def _docker_archive(tar: tarfile.TarFile, archive: str) -> int:
    entries = json.load(_member(tar, "manifest.json"))
    entry = entries[0] if entries else {}
    config_name = entry.get("Config", "")
    config_digest = ("sha256:" + config_name.split("/")[-1].removesuffix(".json")
                     if config_name else "unavailable")
    print("format           Docker Archive (manifest.json)")
    print("manifest_digest  NOT AVAILABLE — this format records no manifest digest")
    print(f"config_digest    {config_digest}")
    print(f"archive_sha256   sha256:{archive}")
    print(f"layers           {len(entry.get('Layers') or [])}")
    print(f"repo_tags        {entry.get('RepoTags')}")
    print("", file=sys.stderr)
    print("A deployment reference needs a manifest digest, which this archive "
          "does not contain. Export explicitly with "
          "`docker buildx build --builder <docker-container-builder> "
          "--output type=oci,dest=worker.oci.tar ...`. See the pinned builder "
          "setup in docs/worker-operations.md. Enabling BuildKit alone "
          "does not select the archive format; do not change Docker's image "
          "store or push to a registry to work around this error.", file=sys.stderr)
    return 2


def main(path: str) -> int:
    archive = _archive_sha256(path)
    with tarfile.open(path) as tar:
        names = set(tar.getnames())
        if "index.json" in names:
            return _oci(tar, archive)
        if "manifest.json" in names:
            return _docker_archive(tar, archive)
    print("unrecognised archive: neither index.json nor manifest.json is present",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
