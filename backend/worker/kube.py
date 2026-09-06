"""AF-011: the smallest Kubernetes API subset a validation Job needs.

Six operations, and deliberately no more: create one Job, read it back, find
its Pod, read that Pod's logs, delete it, and observe the image it ran. There
is no client library here on purpose — the Kubernetes Python SDK would add a
large dependency to a pinned image for six REST calls, and every call it could
then make would be inside the executor's blast radius.

**Authority comes from the mounted ServiceAccount, and is narrow by design.**
`deploy/k3s/50-validation.yaml` grants exactly the verbs used below, namespaced
to `aegisforge`. Secrets, ConfigMaps, Deployments, Services, Nodes, other
namespaces, `exec`, `attach`, `portforward` and every cluster-scoped resource
are absent from that Role, so they are unreachable from here regardless of what
this module asks for.

**TLS is verified against the mounted CA, always.** Verification is never
switched off, there is no fallback to an unverified context, and no
environment variable can disable it. An API server whose certificate does not
chain to the ServiceAccount CA is unreachable, which is the correct closed
state.

**Every call is bounded and fails closed.** A timeout, a 5xx, an unparsable
body and an unreachable API all raise `KubeError`. None of them ever becomes
"the validation passed": the caller has no path from an error to a pass.

Standard library only.
"""

from __future__ import annotations

import http.client
import json
import os
import ssl
import time

SERVICE_ACCOUNT_ROOT = "/var/run/secrets/kubernetes.io/serviceaccount"
DEFAULT_HOST = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
DEFAULT_PORT = int(os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS", "443"))

REQUEST_TIMEOUT = 15.0
MAX_RESPONSE_BYTES = 1 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024


class KubeError(Exception):
    """The API could not be used. Never a validation outcome."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class KubeUnavailable(KubeError):
    """The API was unreachable or unauthenticated. Fail closed, do not retry
    into a different conclusion."""


class Kube:
    """One authenticated, TLS-verified client for one namespace."""

    def __init__(self, *, namespace: str | None = None,
                 host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 root: str = SERVICE_ACCOUNT_ROOT,
                 timeout: float = REQUEST_TIMEOUT):
        self.host, self.port, self.timeout = host, int(port), timeout
        self._root = root
        self._token = self._read(f"{root}/token")
        self.namespace = (namespace or self._read(f"{root}/namespace")
                          or "aegisforge").strip()
        ca_path = f"{root}/ca.crt"
        if not self._token:
            raise KubeUnavailable(
                "no ServiceAccount token is mounted; the Kubernetes API is "
                "unreachable from here")
        if not os.path.exists(ca_path):
            # Without the CA there is no way to verify the API server, and an
            # unverified connection is not an acceptable substitute.
            raise KubeUnavailable(
                "no ServiceAccount CA is mounted; the Kubernetes API cannot be "
                "verified from here")
        self._context = ssl.create_default_context(cafile=ca_path)
        self._context.check_hostname = True
        self._context.verify_mode = ssl.CERT_REQUIRED

    @staticmethod
    def _read(path: str) -> str:
        try:
            with open(path) as handle:
                return handle.read().strip()
        except OSError:
            return ""

    @classmethod
    def available(cls, root: str = SERVICE_ACCOUNT_ROOT) -> bool:
        """Whether a token and CA are mounted. Not whether the API answers."""
        return (os.path.exists(f"{root}/token")
                and os.path.exists(f"{root}/ca.crt"))

    # ---------------------------------------------------------------- http ---

    def _call(self, method: str, path: str, body: dict | None = None,
              *, limit: int = MAX_RESPONSE_BYTES, raw: bool = False):
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Bearer {self._token}",
                   "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))
        connection = http.client.HTTPSConnection(
            self.host, self.port, timeout=self.timeout, context=self._context)
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            data = response.read(limit)
            status = response.status
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise KubeUnavailable(
                f"the Kubernetes API did not answer: {type(exc).__name__}") from exc
        finally:
            connection.close()
        if status in (401, 403):
            raise KubeUnavailable(
                f"the Kubernetes API refused this ServiceAccount ({status})", status)
        if status >= 400:
            raise KubeError(f"the Kubernetes API returned {status}", status)
        if raw:
            return data
        try:
            return json.loads(data)
        except ValueError as exc:
            raise KubeError("the Kubernetes API returned an unreadable body") from exc

    # ---------------------------------------------------------------- jobs ---

    def create_job(self, manifest: dict) -> dict:
        return self._call(
            "POST", f"/apis/batch/v1/namespaces/{self.namespace}/jobs", manifest)

    def get_job(self, name: str) -> dict:
        return self._call(
            "GET", f"/apis/batch/v1/namespaces/{self.namespace}/jobs/{name}")

    def delete_job(self, name: str) -> dict:
        """Delete one Job and the Pod it owns. Never a collection.

        `propagationPolicy: Background` is what removes the Pod too; without it
        a cancelled attempt would leave its Pod running with the package still
        mounted.
        """
        return self._call(
            "DELETE", f"/apis/batch/v1/namespaces/{self.namespace}/jobs/{name}",
            {"apiVersion": "meta.k8s.io/v1", "kind": "DeleteOptions",
             "propagationPolicy": "Background"})

    def find_pod(self, *, label: str, value: str) -> dict | None:
        """The one Pod carrying this attempt's immutable label, or None.

        Selected by label rather than by name: a Job's Pod name has a random
        suffix, and guessing it would either fail or match the wrong Pod.
        """
        listed = self._call(
            "GET", f"/api/v1/namespaces/{self.namespace}/pods"
                   f"?labelSelector={label}%3D{value}&limit=2")
        items = listed.get("items") or []
        return items[0] if len(items) == 1 else (items[0] if items else None)

    def pod_logs(self, name: str, *, container: str = "validate",
                 limit_bytes: int = MAX_LOG_BYTES) -> str:
        """Bounded log read. `limitBytes` is enforced by the API, and the
        result is truncated again here in case it is not."""
        data = self._call(
            "GET", f"/api/v1/namespaces/{self.namespace}/pods/{name}/log"
                   f"?container={container}&limitBytes={int(limit_bytes)}",
            limit=limit_bytes + 4096, raw=True)
        return data[:limit_bytes].decode("utf-8", "replace")

    # ------------------------------------------------------------ observing ---

    def wait_for_completion(self, name: str, *, deadline_seconds: float,
                            poll_seconds: float = 1.0,
                            should_cancel=None) -> dict:
        """Poll one Job to a terminal condition, or stop for a bounded reason.

        Returns the last Job object read plus how it ended. A deadline or a
        cancellation returns `state="unfinished"`: the caller deletes the Job
        and reports it as failed or cancelled, never as passed.
        """
        expires = time.monotonic() + max(1.0, float(deadline_seconds))
        last: dict = {}
        while True:
            if should_cancel is not None and should_cancel():
                return {"state": "cancelled", "job": last}
            last = self.get_job(name)
            status = last.get("status") or {}
            if int(status.get("succeeded") or 0) > 0:
                return {"state": "succeeded", "job": last}
            if int(status.get("failed") or 0) > 0:
                return {"state": "failed", "job": last}
            for condition in status.get("conditions") or []:
                if condition.get("type") == "Failed" and condition.get("status") == "True":
                    return {"state": "failed", "job": last}
            if time.monotonic() > expires:
                return {"state": "unfinished", "job": last}
            time.sleep(max(0.05, poll_seconds))

    @staticmethod
    def pod_evidence(pod: dict | None, *, container: str = "validate") -> dict | None:
        """What the API actually returned about the Pod, or nothing.

        Every field is read off the object; none is inferred. A Pod that has
        not reported a container status yields no image digest rather than the
        digest that was requested in the spec — asking for an image is not
        evidence that it ran.
        """
        if not pod:
            return None
        metadata = pod.get("metadata") or {}
        status = pod.get("status") or {}
        statuses = status.get("containerStatuses") or []
        found = next((item for item in statuses
                      if item.get("name") == container), None)
        image_id = (found or {}).get("imageID") or ""
        digest = image_id.rsplit("sha256:", 1)[-1] if "sha256:" in image_id else None
        return {
            "namespace": metadata.get("namespace"),
            "pod_name": metadata.get("name"),
            "pod_uid": metadata.get("uid"),
            "image_digest": digest,
            "ready": bool((found or {}).get("ready")),
            "restarts": int((found or {}).get("restartCount") or 0),
            "phase": status.get("phase"),
        }
