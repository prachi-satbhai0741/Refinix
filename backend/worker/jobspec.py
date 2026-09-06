"""AF-011: building and running one restricted validation Job.

This is the only place a Kubernetes object is constructed, so every restriction
the sandbox depends on is in one screen and one check can read them all:

* non-root, `allowPrivilegeEscalation: false`, all capabilities dropped,
  `RuntimeDefault` seccomp and a read-only root filesystem;
* **no ServiceAccount token** — the Job cannot talk to the API at all;
* the attempt's package mounted **read-only** at a `subPath` that is derived
  from validated opaque IDs, so a Job can only ever see its own attempt;
* a size-limited `emptyDir` for the workspace, and nothing else mounted: no
  home directory, no host path, no Docker socket, no credential, no runtime
  socket, no pairing state, no Redis password;
* CPU, memory, process, file-size, output-size and runtime ceilings;
* `activeDeadlineSeconds` so a hung Job ends, and `ttlSecondsAfterFinished` so
  a finished one is collected;
* no ingress and **default-deny egress with no exception** (the NetworkPolicy
  in `deploy/k3s/50-validation.yaml`);
* one command, from the plan, matched against `validate.ALLOWED_COMMANDS`
  before it runs and executed with `argv` rather than a shell.

The Job's name and labels come from validated UUIDs and a digest, never from a
model, a filename or a request. A Kubernetes name must match a DNS label, so
the name is a fixed prefix plus the attempt's hex — nothing a caller supplies
reaches it unfiltered.

Standard library only.
"""

from __future__ import annotations

import json
import os
import re

from backend.worker import kube, validate

NAMESPACE = os.environ.get("AEGIS_NAMESPACE", "aegisforge")
# The same pinned worker image, running a different command. C09 adds no
# second image and no second build, exactly as C06 did not.
VALIDATION_IMAGE = os.environ.get("AEGIS_VALIDATION_IMAGE", "")
JOBS_CLAIM = os.environ.get("AEGIS_JOBS_CLAIM", "aegisforge-jobs")
PACKAGE_SUBPATH_ROOT = os.environ.get("AEGIS_PACKAGE_SUBPATH", "packages")

ATTEMPT_LABEL = "aegisforge.dev/attempt"
CONTAINER_NAME = "validate"
JOB_PREFIX = "af-validate-"

# Container ceilings. The runner applies its own rlimits as well; these are
# what the kubelet enforces regardless of what the process does.
CPU_LIMIT = os.environ.get("AEGIS_VALIDATION_CPU", "1")
MEMORY_LIMIT = os.environ.get("AEGIS_VALIDATION_MEMORY", "512Mi")
WORKSPACE_LIMIT = os.environ.get("AEGIS_VALIDATION_WORKSPACE", "64Mi")
MAX_RUNTIME_SECONDS = int(os.environ.get("AEGIS_VALIDATION_SECONDS", "300"))
TTL_AFTER_FINISHED = int(os.environ.get("AEGIS_VALIDATION_TTL", "300"))
RUN_AS_UID = int(os.environ.get("AEGIS_VALIDATION_UID", "10001"))
RUN_AS_GID = int(os.environ.get("AEGIS_VALIDATION_GID", "10001"))

_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class ValidationUnavailable(Exception):
    """Sandbox validation could not be attempted. Never a pass."""


def job_name(attempt_id: str) -> str:
    """A DNS-label name derived only from a validated UUID.

    63 characters is the hard limit; the prefix plus 32 hex digits is 44, so
    this cannot be truncated into a collision.
    """
    if not _UUID.fullmatch(attempt_id):
        raise ValidationUnavailable("a validation Job needs a UUIDv4 attempt id")
    return JOB_PREFIX + attempt_id.replace("-", "")


def build_job(envelope, *, image: str, subpath: str,
              runtime_seconds: int) -> dict:
    """The complete Job object. Every restriction is visible here."""
    if not image:
        raise ValidationUnavailable(
            "no validation image digest is configured for this worker")
    name = job_name(envelope.attempt_id)
    seconds = max(10, min(int(runtime_seconds), MAX_RUNTIME_SECONDS))
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "labels": {"app": "aegisforge-validation",
                       ATTEMPT_LABEL: envelope.attempt_id},
        },
        "spec": {
            # One Pod, one try. A retried validation would run the command
            # twice and report whichever finished last.
            "backoffLimit": 0,
            "completions": 1,
            "parallelism": 1,
            "activeDeadlineSeconds": seconds,
            "ttlSecondsAfterFinished": TTL_AFTER_FINISHED,
            "template": {
                "metadata": {
                    "labels": {"app": "aegisforge-validation",
                               ATTEMPT_LABEL: envelope.attempt_id},
                },
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": "aegisforge-validation",
                    # The Job must not be able to reach the Kubernetes API.
                    "automountServiceAccountToken": False,
                    "enableServiceLinks": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": RUN_AS_UID,
                        "runAsGroup": RUN_AS_GID,
                        "fsGroup": RUN_AS_GID,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [{
                        "name": CONTAINER_NAME,
                        "image": image,
                        "imagePullPolicy": "Never",
                        "command": ["python", "-m", "backend.worker.validate",
                                    "/package", "/workspace"],
                        "env": [
                            {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
                            {"name": "HOME", "value": "/workspace"},
                        ],
                        "securityContext": {
                            "allowPrivilegeEscalation": False,
                            "readOnlyRootFilesystem": True,
                            "privileged": False,
                            "capabilities": {"drop": ["ALL"]},
                        },
                        "resources": {
                            "requests": {"cpu": "100m", "memory": "128Mi"},
                            "limits": {"cpu": CPU_LIMIT, "memory": MEMORY_LIMIT},
                        },
                        "volumeMounts": [
                            {"name": "package", "mountPath": "/package",
                             "subPath": subpath, "readOnly": True},
                            {"name": "workspace", "mountPath": "/workspace"},
                        ],
                    }],
                    "volumes": [
                        {"name": "package",
                         "persistentVolumeClaim": {"claimName": JOBS_CLAIM,
                                                   "readOnly": True}},
                        {"name": "workspace",
                         "emptyDir": {"sizeLimit": WORKSPACE_LIMIT}},
                    ],
                },
            },
        },
    }


def parse_result(logs: str) -> dict | None:
    """The one JSON line the runner printed, verified against its own digest.

    Pod logs can carry anything a process wrote, so the last parsable object
    is taken and then checked: a result whose recorded digest does not match
    its content is discarded rather than believed.
    """
    for line in reversed((logs or "").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            found = json.loads(line)
        except ValueError:
            continue
        if not isinstance(found, dict) or \
                found.get("result_version") != validate.RESULT_VERSION:
            continue
        recorded = found.get("result_sha256")
        if not isinstance(recorded, str) or \
                validate.result_digest(found) != recorded:
            continue
        return found
    return None


class JobValidator:
    """Creates one Job per attempt, waits for it, and reports what it saw."""

    def __init__(self, *, client=None, image: str | None = None,
                 namespace: str = NAMESPACE):
        self._client = client
        self.image = image if image is not None else VALIDATION_IMAGE
        self.namespace = namespace

    def client(self):
        if self._client is None:
            if not kube.Kube.available():
                raise ValidationUnavailable(
                    "no Kubernetes ServiceAccount is mounted in this Pod")
            self._client = kube.Kube(namespace=self.namespace)
        return self._client

    def subpath(self, envelope) -> str:
        for value in (envelope.relationship_id, envelope.workspace_id,
                      envelope.attempt_id):
            if not value or not _UUID.fullmatch(str(value)):
                raise ValidationUnavailable(
                    "a validation Job is addressed by UUIDv4 identifiers")
        return (f"{PACKAGE_SUBPATH_ROOT}/{envelope.relationship_id}/"
                f"{envelope.workspace_id}/{envelope.attempt_id}")

    def run(self, envelope, *, package_root, deadline_seconds: float,
            should_cancel=None) -> dict:
        """One Job, start to finish. Returns evidence, never a verdict of its own."""
        stored = package_root.manifest(
            relationship_id=envelope.relationship_id,
            workspace_id=envelope.workspace_id, attempt_id=envelope.attempt_id)
        if stored is None:
            raise ValidationUnavailable(
                "this attempt has no package to validate")
        client = self.client()
        manifest = build_job(envelope, image=self.image,
                             subpath=self.subpath(envelope),
                             runtime_seconds=int(deadline_seconds))
        name = manifest["metadata"]["name"]
        created = client.create_job(manifest)
        job_uid = ((created.get("metadata") or {}).get("uid"))
        try:
            outcome = client.wait_for_completion(
                name, deadline_seconds=deadline_seconds,
                should_cancel=should_cancel)
            pod = client.find_pod(label=ATTEMPT_LABEL, value=envelope.attempt_id)
            evidence = kube.Kube.pod_evidence(pod)
            if outcome["state"] == "cancelled":
                # Delete only THIS Job, by the name derived from this attempt.
                self._delete(client, name)
                return {"cancelled": True, "observed": False, "job_name": name,
                        "job_uid": job_uid, "pod": evidence}
            logs = ""
            if evidence and evidence.get("pod_name"):
                try:
                    logs = client.pod_logs(evidence["pod_name"],
                                           container=CONTAINER_NAME)
                except kube.KubeError:
                    logs = ""
            result = parse_result(logs)
            if outcome["state"] == "unfinished":
                # Out of time. The Job is removed and the attempt fails; a
                # deadline is never reported as a pass.
                self._delete(client, name)
                return {"cancelled": False, "observed": False, "job_name": name,
                        "job_uid": job_uid, "pod": evidence,
                        "error": "the validation Job did not finish in time"}
            passed = bool(outcome["state"] == "succeeded" and result
                          and result.get("passed") is True
                          and result.get("exit_status") == 0)
            return {
                "cancelled": False,
                "observed": result is not None,
                "job_name": name,
                "job_uid": job_uid,
                "job_state": outcome["state"],
                "pod": evidence,
                # `passed` comes from the runner's own recorded exit status,
                # never from the Job's phase and never from its creation.
                "passed": passed,
                "result": result,
                "package_sha256": stored.get("package_sha256"),
            }
        except kube.KubeError:
            self._delete(client, name)
            raise
        except ValidationUnavailable:
            self._delete(client, name)
            raise

    @staticmethod
    def _delete(client, name: str) -> None:
        try:
            client.delete_job(name)
        except kube.KubeError:
            # The TTL collects it regardless; failing to delete must not turn
            # a failed validation into an exception the caller misreads.
            pass
