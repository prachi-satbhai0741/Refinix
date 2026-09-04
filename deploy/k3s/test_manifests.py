"""Offline invariant checks for the C05 manifests.

Not schema validation — `kubectl --dry-run=client` needs a live cluster to
resolve API groups, and a schema would not catch what actually matters here:
that pinned digests match what was built, that Redis cannot reach the LAN, and
that no Pod quietly gains privilege.

Standard library only; no cluster, no network.

    python3 -m unittest deploy.k3s.test_manifests
"""

import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFESTS = sorted((ROOT / "deploy" / "k3s").glob("*.yaml"))
CHECK_PODS = sorted((ROOT / "deploy" / "k3s" / "checks").glob("*.yaml"))


def commands(text: str) -> str:
    """Drop comment lines. A check for a forbidden flag must inspect commands,
    not the prose explaining why the flag is forbidden."""
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("#"))


def documents():
    """Split every manifest into (filename, kind, name, text)."""
    out = []
    for path in MANIFESTS:
        for chunk in path.read_text().split("\n---\n"):
            kind = re.search(r"^kind:\s*(\S+)", chunk, re.M)
            name = re.search(r"^\s\sname:\s*(\S+)", chunk, re.M)
            if kind:
                out.append((path.name, kind.group(1),
                            name.group(1) if name else "?", chunk))
    return out


class TestPinnedDigests(unittest.TestCase):
    """A manifest digest that drifts from the recorded build is a silent lie."""

    def test_worker_image_matches_the_recorded_build(self):
        provenance = json.loads(
            (ROOT / "backend/worker-image/provenance.json").read_text())
        built = provenance["ubuntu_build"]["manifest_digest"]
        worker = [t for _, k, n, t in documents()
                  if k == "Deployment" and n == "aegisforge-worker"][0]
        self.assertIn(built, worker,
                      "the worker Deployment must pin the digest C04 produced")

    def test_redis_image_matches_od08(self):
        architecture = (ROOT / "docs/architecture.md").read_text()
        redis = [t for _, k, n, t in documents()
                 if k == "Deployment" and n == "redis"][0]
        digest = re.search(r"image:\s*redis@(sha256:[0-9a-f]{64})", redis).group(1)
        self.assertIn(digest, architecture,
                      "the Redis digest must be the one pinned in OD-08")

    def test_no_floating_tags(self):
        for filename, kind, name, text in documents():
            for image in re.findall(r"^\s+image:\s*(\S+)", text, re.M):
                self.assertIn("@sha256:", image,
                              f"{filename}/{name} uses an unpinned image: {image}")

    def test_worker_never_pulls(self):
        worker = [t for _, k, n, t in documents()
                  if k == "Deployment" and n == "aegisforge-worker"][0]
        self.assertRegex(worker, r"imagePullPolicy:\s*Never",
                         "the worker image is imported locally; the node must "
                         "not reach a registry to run it")


class TestContractPorts(unittest.TestCase):
    def test_service_ports_match_the_contract(self):
        source = (ROOT / "backend/contracts/v1.py").read_text()
        worker_port = re.search(r"WORKER_PORT\s*=\s*(\d+)", source).group(1)
        node_port = re.search(r"WORKER_NODE_PORT\s*=\s*(\d+)", source).group(1)
        service = [t for _, k, n, t in documents()
                   if k == "Service" and n == "aegisforge-worker"][0]
        self.assertRegex(service, rf"port:\s*{worker_port}\b")
        self.assertRegex(service, rf"nodePort:\s*{node_port}\b")


class TestRedisIsNotReachable(unittest.TestCase):
    """security.md: Redis stays behind ClusterIP — not NodePort, LoadBalancer,
    Ingress or a host port."""

    def test_redis_service_is_clusterip(self):
        service = [t for _, k, n, t in documents()
                   if k == "Service" and n == "redis"][0]
        self.assertRegex(service, r"type:\s*ClusterIP")
        self.assertNotIn("nodePort", service)

    def test_no_ingress_or_loadbalancer_anywhere(self):
        for filename, kind, name, _ in documents():
            self.assertNotIn(kind, {"Ingress", "IngressRoute"},
                             f"{filename} defines {kind}")

    def test_redis_accepts_only_the_worker(self):
        policy = [t for _, k, n, t in documents()
                  if k == "NetworkPolicy" and "redis" in n][0]
        self.assertIn("app: aegisforge-worker", policy)


class TestPodSecurity(unittest.TestCase):
    """security.md section 8: non-root, no privilege escalation, no capabilities,
    RuntimeDefault seccomp, read-only root filesystem, bounded resources."""

    def deployments(self):
        return [(n, t) for _, k, n, t in documents() if k == "Deployment"]

    def test_every_deployment_is_hardened(self):
        for name, text in self.deployments():
            with self.subTest(deployment=name):
                self.assertRegex(text, r"runAsNonRoot:\s*true")
                self.assertRegex(text, r"allowPrivilegeEscalation:\s*false")
                self.assertRegex(text, r"readOnlyRootFilesystem:\s*true")
                self.assertRegex(text, r'drop:\s*\["ALL"\]')
                self.assertRegex(text, r"type:\s*RuntimeDefault")

    def test_every_deployment_bounds_resources(self):
        for name, text in self.deployments():
            with self.subTest(deployment=name):
                self.assertIn("limits:", text)
                self.assertRegex(text, r"limits:\s*\n\s+cpu:")
                self.assertRegex(text, r"memory:\s*\S+")

    def test_nothing_escapes_to_the_host(self):
        for filename, kind, name, text in documents():
            for forbidden in ("hostNetwork", "hostPID", "hostIPC",
                              "hostPath", "hostPort", "privileged: true"):
                self.assertNotIn(forbidden, text,
                                 f"{filename}/{name} uses {forbidden}")

    def test_service_account_tokens_are_not_mounted(self):
        for name, text in self.deployments():
            with self.subTest(deployment=name):
                self.assertRegex(text, r"automountServiceAccountToken:\s*false")


class TestDefaultDeny(unittest.TestCase):
    def test_a_default_deny_policy_exists(self):
        policies = [t for _, k, _, t in documents() if k == "NetworkPolicy"]
        deny = [p for p in policies
                if re.search(r"podSelector:\s*\{\}", p)
                and "Ingress" in p and "Egress" in p]
        self.assertTrue(deny, "the namespace needs a default-deny NetworkPolicy")

    def test_default_deny_is_applied_before_workloads(self):
        """It lives in the lowest-numbered file, so `kubectl apply` in order
        cannot create a workload before the deny rule exists."""
        first = MANIFESTS[0].name
        self.assertTrue(first.startswith("00-"), f"unexpected first file: {first}")
        self.assertIn("default-deny", MANIFESTS[0].read_text())

    def test_worker_egress_is_not_open(self):
        policy = [t for _, k, n, t in documents()
                  if k == "NetworkPolicy" and n == "worker-egress"][0]
        self.assertNotIn("0.0.0.0/0", policy,
                         "worker egress must not be unrestricted")


class TestNoSecretsCommitted(unittest.TestCase):
    def test_no_credential_material_in_the_manifests(self):
        for filename, _, name, text in documents():
            self.assertNotIn("kind: Secret", text,
                             f"{filename} defines a Secret; it must be created "
                             "by the operator, never committed")
            self.assertNotRegex(text, r"AEGIS_WORKER_TOKEN:\s*\S+",
                                f"{filename} appears to inline a token")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestIsolationProbes(unittest.TestCase):
    """The probes must be admitted, or a "failure" proves nothing about the
    network. Restricted Pod Security rejects a non-compliant Pod before any
    connection is attempted."""

    def test_both_halves_exist(self):
        names = {p.name for p in CHECK_PODS}
        self.assertIn("netpolicy-allowed.yaml", names)
        self.assertIn("netpolicy-denied.yaml", names)

    def test_probes_satisfy_restricted_pod_security(self):
        for path in CHECK_PODS:
            text = path.read_text()
            with self.subTest(probe=path.name):
                self.assertRegex(text, r"runAsNonRoot:\s*true")
                self.assertRegex(text, r"allowPrivilegeEscalation:\s*false")
                self.assertRegex(text, r"readOnlyRootFilesystem:\s*true")
                self.assertRegex(text, r'drop:\s*\["ALL"\]')
                self.assertRegex(text, r"type:\s*RuntimeDefault")
                self.assertRegex(text, r"automountServiceAccountToken:\s*false")

    def test_probes_pin_their_image(self):
        for path in CHECK_PODS:
            for image in re.findall(r"^\s+image:\s*(\S+)", path.read_text(), re.M):
                self.assertIn("@sha256:", image, f"{path.name}: {image}")

    def test_allowed_probe_carries_the_selected_label(self):
        text = (ROOT / "deploy/k3s/checks/netpolicy-allowed.yaml").read_text()
        self.assertIn("app: aegisforge-worker", text)

    def test_denied_probe_does_not(self):
        text = (ROOT / "deploy/k3s/checks/netpolicy-denied.yaml").read_text()
        self.assertNotIn("app: aegisforge-worker\n", text.split("spec:")[0])

    def test_probes_distinguish_failure_modes(self):
        """A refusal must not be reported the same way as DNS, auth, missing
        tooling or a protected-mode rejection."""
        for path in CHECK_PODS:
            text = path.read_text()
            with self.subTest(probe=path.name):
                for mode in ("dns-failed", "auth-failed", "tooling-missing",
                             "redis-protected-mode", "timeout-or-blocked",
                             "refused", "empty-output"):
                    self.assertIn(mode, text, f"{path.name} cannot report {mode}")

    def test_probes_classify_exit_status_not_just_output(self):
        """Empty output alone is not proof of blocking."""
        for path in CHECK_PODS:
            text = path.read_text()
            with self.subTest(probe=path.name):
                self.assertIn("124", text, "timeout's exit status must be checked")
                self.assertIn("status=$?", text.replace("status=$?", "status=$?"))


class TestRedisAuthentication(unittest.TestCase):
    """Protected mode with no password makes Redis reject the worker outright."""

    def redis(self):
        return (ROOT / "deploy/k3s/10-redis.yaml").read_text()

    def test_a_password_is_required(self):
        self.assertIn("requirepass", self.redis())

    def test_the_password_comes_from_a_mounted_secret(self):
        redis = self.redis()
        self.assertIn("secretName: redis-credential", redis)
        self.assertIn("/etc/redis-secret", redis)
        self.assertNotRegex(redis, r"requirepass\s+[A-Za-z0-9]{8,}",
                            "the password must never be an argument literal")

    def test_the_password_never_reaches_process_arguments(self):
        """Shell expansion of --requirepass "$VAR" still places the value in
        argv, readable by anything that can see /proc."""
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(CHECK_PODS):
            text = path.read_text()
            with self.subTest(file=path.name):
                body = commands(text)
                self.assertNotRegex(body, r'requirepass\s+"\$',
                                    "expand into a config file, not into argv")
                self.assertNotRegex(body, r'redis-cli[^\n]*\s-a\s',
                                    "use REDISCLI_AUTH, not -a")

    def test_clients_use_rediscli_auth(self):
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(CHECK_PODS):
            with self.subTest(file=path.name):
                self.assertIn("REDISCLI_AUTH", path.read_text())

    def test_no_unsupported_cli_timeout_flag(self):
        """redis-cli 7.2 has no -t option; it would be parsed as a command."""
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(CHECK_PODS):
            body = commands(path.read_text())
            with self.subTest(file=path.name):
                self.assertNotRegex(body, r"redis-cli[^\n]*\s-t\s",
                                    "redis-cli has no -t; wrap the call in `timeout`")
                if "redis-cli" in body:
                    self.assertIn("timeout ", body,
                                  "the call must be bounded by `timeout`")


class TestWorkerProbes(unittest.TestCase):
    """An httpGet probe cannot send the credential, so /v1/health answers 401
    and Kubernetes restarts a healthy Pod forever."""

    def worker(self):
        return (ROOT / "deploy/k3s/20-worker.yaml").read_text()

    def test_no_unauthenticated_http_probes(self):
        self.assertNotIn("httpGet:", self.worker(),
                         "health requires a bearer credential and the contract header")

    def test_probes_send_both_required_headers(self):
        worker = self.worker()
        self.assertIn("AEGIS_WORKER_TOKEN", worker)
        self.assertIn("X-AegisForge-Contract", worker)

    def test_all_three_probes_are_defined(self):
        worker = self.worker()
        for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
            self.assertIn(probe, worker)


class TestRuntimeEgressIsSeparate(unittest.TestCase):
    def test_default_deployment_grants_no_runtime_egress(self):
        """Check the egress POLICY, not the whole file: the ConfigMap names the
        runtime port deliberately, pointing at Pod loopback where nothing runs."""
        policy = [t for f, k, n, t in documents()
                  if f == "20-worker.yaml" and k == "NetworkPolicy"
                  and n == "worker-egress"][0]
        self.assertNotIn("11434", policy,
                         "runtime egress must be a separate, explicitly applied file")
        self.assertNotIn("ipBlock", policy,
                         "the default worker egress reaches Redis and nothing else")

    def test_the_runtime_policy_is_narrow(self):
        policy = (ROOT / "deploy/k3s/30-runtime-egress.yaml").read_text()
        self.assertIn("/32", policy, "a single host, not a subnet")
        self.assertNotIn("0.0.0.0/0", policy)


class TestProbeBudget(unittest.TestCase):
    """/v1/health calls runtime.probe(), which makes three HTTP calls. A probe
    timeout shorter than that budget fails a healthy Pod into a restart loop."""

    def test_worker_probe_timeout_covers_the_health_budget(self):
        source = (ROOT / "backend/worker/runtime.py").read_text()
        budget = sum(int(t) for t in
                     re.findall(r'_post\("/api/\w+", timeout=(\d+)\)', source))
        self.assertGreater(budget, 0, "could not read the probe budget")
        worker = (ROOT / "deploy/k3s/20-worker.yaml").read_text()
        timeouts = [int(t) for t in re.findall(r"timeoutSeconds:\s*(\d+)", worker)]
        self.assertTrue(timeouts, "the worker probes declare no timeoutSeconds")
        self.assertTrue(all(t > budget for t in timeouts),
                        f"probe timeouts {timeouts} must exceed the ~{budget}s "
                        "worst-case health budget")

    def test_period_is_not_shorter_than_the_timeout(self):
        worker = (ROOT / "deploy/k3s/20-worker.yaml").read_text()
        pairs = re.findall(r"timeoutSeconds:\s*(\d+)\s*\n\s*periodSeconds:\s*(\d+)",
                           worker)
        for timeout, period in pairs:
            self.assertGreaterEqual(int(period), int(timeout),
                                    "a period shorter than the timeout overlaps probes")


class TestProbePodsAreNotServiceEndpoints(unittest.TestCase):
    """An isolation Pod carrying the Service's full selector would silently join
    the worker Service and receive real traffic."""

    def service_selector(self):
        service = [t for _, k, n, t in documents()
                   if k == "Service" and n == "aegisforge-worker"][0]
        block = service.split("selector:")[1].split("ports:")[0]
        return set(re.findall(r"^\s+([\w.-]+):\s*(\S+)", block, re.M))

    def test_service_selector_has_a_label_the_probes_lack(self):
        selector = self.service_selector()
        self.assertGreater(len(selector), 1,
                           "a single-label selector cannot exclude the probes")
        for path in CHECK_PODS:
            labels = path.read_text().split("spec:")[0]
            with self.subTest(probe=path.name):
                missing = [f"{k}: {v}" for k, v in selector if f"{k}: {v}" not in labels]
                self.assertTrue(missing,
                                f"{path.name} matches the Service selector entirely")


class TestCredentialHandling(unittest.TestCase):
    def test_secret_is_group_readable_with_fsgroup(self):
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(CHECK_PODS):
            text = path.read_text()
            with self.subTest(file=path.name):
                self.assertIn("fsGroup: 10002", text)
                self.assertIn("defaultMode: 0440", text)
                self.assertNotIn("defaultMode: 0400", text,
                                 "0400 is unreadable to a non-root group member")

    def test_readability_is_checked_before_use(self):
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(CHECK_PODS):
            body = commands(path.read_text())
            with self.subTest(file=path.name):
                self.assertIn("-r /etc/redis-secret/password", body,
                              "an unreadable credential must fail explicitly")

    def test_generated_config_lives_in_bounded_memory(self):
        redis = (ROOT / "deploy/k3s/10-redis.yaml").read_text()
        self.assertIn("medium: Memory", redis)
        self.assertIn("sizeLimit:", redis)
        self.assertNotIn("/tmp/redis.conf", redis,
                         "the generated config carries the password; keep it off disk")

    def test_probes_report_credential_problems_distinctly(self):
        for path in CHECK_PODS:
            text = path.read_text()
            with self.subTest(probe=path.name):
                self.assertIn("credential-unreadable", text)
                self.assertIn("credential-empty", text)

    def test_client_timeout_terminates_a_hung_process(self):
        for path in CHECK_PODS:
            body = commands(path.read_text())
            with self.subTest(probe=path.name):
                self.assertRegex(body, r"timeout\s+-k\s+\d+\s+\d+",
                                 "use timeout -k so a hung client is terminated")
