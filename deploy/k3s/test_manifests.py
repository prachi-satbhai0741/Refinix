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
# The isolation pair talks to Redis; the networking check does not. Assertions
# about credentials and redis-cli apply only to the pair.
ISOLATION_PROBES = [p for p in CHECK_PODS if p.name.startswith("netpolicy-")]


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
                      "the worker Deployment must pin the recorded Ubuntu build")

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
            if kind not in {"Deployment", "Pod", "StatefulSet", "DaemonSet", "Job"}:
                continue
            for forbidden in ("hostNetwork", "hostPID", "hostIPC",
                              "hostPath", "hostPort", "privileged: true"):
                self.assertNotIn(forbidden, text,
                                 f"{filename}/{name} uses {forbidden}")

    def test_service_account_tokens_are_not_mounted(self):
        """Exactly one Pod may talk to the Kubernetes API, and it is named here.

        AF-011 gives the executor a token so it can create validation Jobs.
        That is the ONE exception, so it is written down rather than allowed
        by a relaxed pattern: every other Deployment must still refuse a token,
        and a second one appearing would fail this check.
        """
        for name, text in self.deployments():
            with self.subTest(deployment=name):
                if name == "aegisforge-executor":
                    self.assertRegex(text, r"serviceAccountName:\s*aegisforge-executor")
                    continue
                self.assertRegex(text, r"automountServiceAccountToken:\s*false")

    def test_only_the_executor_names_a_service_account(self):
        named = [name for name, text in self.deployments()
                 if re.search(r"serviceAccountName:", text)]
        self.assertEqual(named, ["aegisforge-executor"])


class TestValidationSandbox(unittest.TestCase):
    """AF-011 authority and isolation, read straight out of the manifests."""

    def role(self) -> str:
        found = [t for _, k, n, t in documents()
                 if k == "Role" and n == "aegisforge-validation"]
        self.assertTrue(found, "the validation Role is missing")
        return commands(found[0])

    def policy(self, name: str) -> str:
        found = [t for _, k, n, t in documents()
                 if k == "NetworkPolicy" and n == name]
        self.assertTrue(found, f"{name} is missing")
        return commands(found[0])

    def admission(self) -> str:
        found = [t for _, k, n, t in documents()
                 if k == "ValidatingAdmissionPolicy"
                 and n == "aegisforge-validation-job"]
        self.assertTrue(found, "the validation admission policy is missing")
        return commands(found[0])

    def test_the_role_grants_only_the_six_operations_the_client_performs(self):
        role = self.role()
        self.assertRegex(role, r'resources:\s*\["jobs"\]')
        self.assertRegex(role, r'verbs:\s*\["create", "get", "delete"\]')
        self.assertRegex(role, r'resources:\s*\["pods"\]')
        self.assertRegex(role, r'resources:\s*\["pods/log"\]')

    def test_the_role_grants_nothing_that_would_widen_the_blast_radius(self):
        role = self.role()
        for forbidden in ("secrets", "configmaps", "deployments", "services",
                          "nodes", "pods/exec", "pods/attach",
                          "pods/portforward", "persistentvolumes",
                          "ClusterRole", '"*"', "'*'"):
            with self.subTest(value=forbidden):
                self.assertNotIn(forbidden, role)

    def test_the_role_is_namespaced_rather_than_cluster_wide(self):
        kinds = {k for _, k, n, _ in documents()
                 if n in ("aegisforge-validation", "aegisforge-executor")}
        self.assertNotIn("ClusterRole", kinds)
        self.assertNotIn("ClusterRoleBinding", kinds)

    def test_the_executor_cannot_create_pods_directly(self):
        """`create` on pods would let this ServiceAccount run any Pod spec."""
        role = self.role()
        pods = role.split('resources: ["pods"]', 1)[1].split("- apiGroups", 1)[0]
        self.assertNotIn("create", pods)

    def test_job_creation_is_bound_to_the_exact_sandbox_template(self):
        policy = self.admission()
        for required in (
                "system:serviceaccount:aegisforge:aegisforge-executor",
                "aegisforge-validation'", "automountServiceAccountToken == false",
                "aegisforge-jobs", "persistentVolumeClaim.readOnly == true",
                "backend.worker.validate", "imagePullPolicy == 'Never'",
                "!has(object.spec.template.spec.imagePullSecrets)",
                "object.spec.template.metadata.labels.size() == 2",
                "securityContext.capabilities.add",
                "securityContext.seccompProfile",
                "resources.limits['memory'] == quantity('512Mi')",
                "validationActions: [Deny]"):
            with self.subTest(value=required):
                self.assertIn(required, policy + "\n" + "\n".join(
                    t for _, k, n, t in documents()
                    if k == "ValidatingAdmissionPolicyBinding"
                    and n == "aegisforge-validation-job"))

    def test_validation_jobs_use_the_credential_free_service_account(self):
        accounts = {n: t for _, k, n, t in documents() if k == "ServiceAccount"}
        self.assertIn("aegisforge-validation", accounts)
        self.assertRegex(accounts["aegisforge-validation"],
                         r"automountServiceAccountToken:\s*false")

    def test_the_validation_pod_has_no_egress_exception_at_all(self):
        egress = self.policy("validation-egress")
        self.assertRegex(egress, r"egress:\s*\[\]")
        for forbidden in ("ipBlock", "podSelector:\n            matchLabels",
                          "0.0.0.0/0", "port: 11434", "port: 6379"):
            with self.subTest(value=forbidden):
                self.assertNotIn(forbidden, egress)

    def test_the_validation_pod_accepts_no_ingress(self):
        self.assertRegex(self.policy("validation-ingress"), r"ingress:\s*\[\]")

    def test_the_validation_pod_is_outside_the_runtime_egress_policy(self):
        """It selects `aegisforge-validation`, not `aegisforge-worker`, so it
        inherits no path to the model runtime."""
        runtime = self.policy("worker-egress-runtime")
        self.assertIn("app: aegisforge-worker", runtime)
        self.assertNotIn("aegisforge-validation", runtime)

    def test_the_kubernetes_api_exception_is_a_placeholder_not_a_wide_rule(self):
        """The API ClusterIP is per-cluster and is not recorded here, so the
        manifest must fail closed rather than ship a subnet-wide hole."""
        egress = self.policy("executor-egress-kubernetes")
        self.assertIn("API_SERVER_IP/32", egress)
        for forbidden in ("0.0.0.0/0", "/8", "/16", "/24"):
            with self.subTest(value=forbidden):
                self.assertNotIn(forbidden, egress)

    def test_the_job_package_volume_is_separate_from_pairing_state(self):
        claims = {n for _, k, n, _ in documents() if k == "PersistentVolumeClaim"}
        self.assertIn("aegisforge-jobs", claims)
        self.assertIn("worker-state", claims)
        executor = [t for _, k, n, t in documents()
                    if k == "Deployment" and n == "aegisforge-executor"][0]
        # The executor gets job packages and must NOT get the pairing store.
        self.assertIn("claimName: aegisforge-jobs", executor)
        self.assertNotIn("claimName: worker-state", executor)

    def test_the_validation_image_is_pinned_by_digest(self):
        config = [t for _, k, n, t in documents()
                  if k == "ConfigMap" and n == "executor-config"][0]
        match = re.search(r'AEGIS_VALIDATION_IMAGE:\s*"([^"]+)"', config)
        self.assertIsNotNone(match, "the validation image must be configured")
        self.assertIn("@sha256:", match.group(1))
        provenance = json.loads(
            (ROOT / "backend/worker-image/provenance.json").read_text())
        self.assertIn(provenance["ubuntu_build"]["manifest_digest"],
                      match.group(1),
                      "validation must run the same recorded build as the executor")


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
        """A network outcome must not be reported the same way as DNS, auth,
        missing tooling or a protected-mode rejection.

        Only the modes that mean the same thing on both paths are shared. A
        refusal does not: on the denied path it is the policy enforcing itself,
        on the allowed path it is an unavailable Service. Each path's network
        classification is asserted separately in TestDenialMechanisms.
        """
        for path in ISOLATION_PROBES:
            text = path.read_text()
            with self.subTest(probe=path.name):
                for mode in ("dns-failed", "auth-failed", "tooling-missing",
                             "redis-protected-mode", "empty-output"):
                    self.assertIn(mode, text, f"{path.name} cannot report {mode}")

    def test_probes_classify_exit_status_not_just_output(self):
        """Empty output alone is not proof of blocking."""
        for path in ISOLATION_PROBES:
            text = path.read_text()
            with self.subTest(probe=path.name):
                self.assertIn("124", text, "timeout's exit status must be checked")
                self.assertIn("status=$?", text.replace("status=$?", "status=$?"))


class TestDenialMechanisms(unittest.TestCase):
    """A NetworkPolicy can be enforced by dropping the packet or by rejecting
    it, and the denied probe must accept both.

    The Ubuntu worker runs K3s's default kube-router, whose Redis Pod chain ends
    in `REJECT --reject-with icmp-port-unreachable`. The denied probe returned
    "Connection refused" immediately and was scored a failure, even though that
    refusal *was* the policy working. Refusal must therefore mean the opposite
    thing on each path, so neither probe may be checked against the other.
    """

    def denied(self):
        return (ROOT / "deploy/k3s/checks/netpolicy-denied.yaml").read_text()

    def allowed(self):
        return (ROOT / "deploy/k3s/checks/netpolicy-allowed.yaml").read_text()

    def branches(self, text, marker):
        """Every executable line whose branch contains `marker`."""
        lines = [l.strip() for l in commands(text).splitlines()
                 if marker in l and "RESULT=" in l]
        self.assertTrue(lines, f"no branch reports {marker!r}")
        return lines

    def branch(self, text, marker):
        """The one executable line whose branch contains `marker`."""
        lines = self.branches(text, marker)
        self.assertEqual(len(lines), 1,
                         f"expected exactly one branch matching {marker!r}, "
                         f"found {len(lines)}")
        return lines[0]

    def test_denied_timeout_is_a_blocked_result_exiting_7(self):
        line = self.branch(self.denied(), "124")
        self.assertIn("RESULT=blocked-by-policy", line)
        self.assertIn("exit 7", line)

    def test_denied_refusal_is_a_blocked_result_exiting_7(self):
        line = self.branch(self.denied(), "Connection refused")
        self.assertIn("RESULT=blocked-by-policy", line,
                      "kube-router's REJECT is the policy working, not a fault")
        self.assertIn("exit 7", line)

    def test_both_denial_mechanisms_share_one_stable_prefix(self):
        """The operator matches one string; the mechanism is detail after it."""
        body = commands(self.denied())
        blocked = [l.strip() for l in body.splitlines()
                   if "RESULT=blocked-by-policy" in l]
        self.assertEqual(len(blocked), 2,
                         "exactly two mechanisms report a policy denial")
        for line in blocked:
            self.assertRegex(line, r'RESULT=blocked-by-policy \(',
                             "name the observed mechanism in parentheses")
            self.assertIn("exit 7", line)

    def test_denied_pong_is_policy_not_enforced_exiting_1(self):
        line = self.branch(self.denied(), "PONG")
        self.assertIn("RESULT=POLICY-NOT-ENFORCED", line)
        self.assertIn("exit 1", line)

    def test_denied_non_network_errors_stay_failures(self):
        """DNS, credential, auth, protected-mode and tooling faults mean the
        probe never reached the network, so none may claim a denial."""
        body = commands(self.denied())
        for mode in ("dns-failed", "credential-unreadable", "credential-empty",
                     "auth-failed", "redis-protected-mode", "tooling-missing",
                     "empty-output", "other"):
            for line in self.branches(body, f"RESULT={mode}"):
                with self.subTest(mode=mode, line=line):
                    self.assertNotIn("blocked-by-policy", line)
                    self.assertNotRegex(line, r"exit\s+(0|7)\b",
                                        f"{mode} must not be scored as a denial")

    def test_allowed_refusal_remains_a_failure_exiting_9(self):
        """On the permitted path a refusal is an unavailable Service, never
        successful isolation. Widening the denied probe must not widen this."""
        line = self.branch(self.allowed(), "Connection refused")
        self.assertIn("RESULT=refused", line)
        self.assertIn("exit 9", line)
        self.assertNotIn("blocked-by-policy", commands(self.allowed()),
                         "the allowed probe has no policy-denial success case")

    def test_the_allowed_first_requirement_is_documented(self):
        """A denial proves isolation only once the allowed half has proven the
        same Service and credential work."""
        for text in (self.denied(), self.allowed()):
            prose = "\n".join(l for l in text.splitlines()
                               if l.lstrip().startswith("#"))
            with self.subTest():
                self.assertRegex(prose, r"(?i)first")
                self.assertRegex(prose, r"(?i)credential")
                self.assertIn("netpolicy-", prose,
                              "name the other half of the pair explicitly")


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
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(ISOLATION_PROBES):
            with self.subTest(file=path.name):
                self.assertIn("REDISCLI_AUTH", path.read_text())

    def test_no_unsupported_cli_timeout_flag(self):
        """redis-cli 7.2 has no -t option; it would be parsed as a command."""
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(ISOLATION_PROBES):
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

    def test_client_timeout_clears_the_documented_worst_case(self):
        """The probe's own client budget must outlast what health can take.

        A 3s urllib timeout against a ~13s worst case failed a healthy Pod in
        exactly the state C05 calls normal, while `timeoutSeconds: 20` said
        otherwise. The two numbers must agree with the comment between them.
        """
        worker = self.worker()
        client = [int(n) for n in re.findall(r"urlopen\([^)]*timeout=(\d+)", worker)]
        self.assertTrue(client, "the probe must set an explicit client timeout")
        kubelet = [int(n) for n in re.findall(r"timeoutSeconds:\s*(\d+)", worker)]
        worst_case = [int(n) for n in re.findall(r"about (\d+)s worst case", worker)]
        self.assertTrue(worst_case, "state the worst case, so it can be checked")
        for value in client:
            self.assertGreater(value, max(worst_case),
                               "the client gives up before health can answer")
            self.assertLess(value, min(kubelet),
                            "the client must lose the race to the kubelet, "
                            "so a slow answer is reported rather than truncated")


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
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(ISOLATION_PROBES):
            text = path.read_text()
            with self.subTest(file=path.name):
                self.assertIn("fsGroup: 10002", text)
                self.assertIn("defaultMode: 0440", text)
                self.assertNotIn("defaultMode: 0400", text,
                                 "0400 is unreadable to a non-root group member")

    def test_readability_is_checked_before_use(self):
        for path in [ROOT / "deploy/k3s/10-redis.yaml"] + list(ISOLATION_PROBES):
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
        for path in ISOLATION_PROBES:
            text = path.read_text()
            with self.subTest(probe=path.name):
                self.assertIn("credential-unreadable", text)
                self.assertIn("credential-empty", text)

    def test_client_timeout_terminates_a_hung_process(self):
        for path in ISOLATION_PROBES:
            body = commands(path.read_text())
            with self.subTest(probe=path.name):
                self.assertRegex(body, r"timeout\s+-k\s+\d+\s+\d+",
                                 "use timeout -k so a hung client is terminated")


class TestFailuresAreNotMasked(unittest.TestCase):
    """A probe that reports a failure and still exits 0 will be waited on with
    `--for=Succeeded` and pass. The step E check did exactly that."""

    def expectation(self, path):
        """Each probe declares `# Expect: RESULT=<value>, exit <code>.`"""
        match = re.search(r"Expect:\s*RESULT=(\S+?),\s*exit\s*(\d+)",
                          path.read_text())
        self.assertIsNotNone(match, f"{path.name} declares no expectation")
        return match.group(1), match.group(2)

    def test_every_probe_declares_its_expected_outcome(self):
        for path in CHECK_PODS:
            with self.subTest(probe=path.name):
                self.expectation(path)

    def test_the_declared_outcome_is_the_one_the_code_produces(self):
        for path in CHECK_PODS:
            expected, code = self.expectation(path)
            body = commands(path.read_text())
            with self.subTest(probe=path.name):
                line = [l for l in body.splitlines() if f"RESULT={expected}" in l]
                self.assertTrue(line, f"{path.name} never emits {expected}")
                self.assertIn(f"exit {code}", line[0],
                              f"{path.name}: the header promises exit {code}")

    def test_every_other_result_exits_non_zero(self):
        """A probe reporting a failure and exiting 0 passes --for=Succeeded."""
        for path in CHECK_PODS:
            expected, _ = self.expectation(path)
            body = commands(path.read_text())
            with self.subTest(probe=path.name):
                for line in body.splitlines():
                    if "RESULT=" not in line or f"RESULT={expected}" in line:
                        continue
                    exits = re.findall(r"exit\s+(\d+)", line)
                    self.assertTrue(exits,
                                    f"{path.name}: no exit on {line.strip()!r}")
                    for value in exits:
                        self.assertNotEqual(value, "0",
                                            f"{path.name}: {line.strip()!r} "
                                            "reports a failure and exits 0")


class TestPodNetworkCheck(unittest.TestCase):
    """Replaces the inline `kubectl run --overrides` blob from step E."""

    def path(self):
        return ROOT / "deploy/k3s/checks/pod-network-check.yaml"

    def test_the_check_exists_as_a_reviewable_manifest(self):
        self.assertTrue(self.path().exists(),
                        "an inline --overrides blob hid a shell bug in review")

    def test_dev_tcp_is_only_used_under_an_explicit_bash(self):
        """/dev/tcp is a bash feature; this image's `sh` is dash."""
        for path in CHECK_PODS:
            body = commands(path.read_text())
            with self.subTest(probe=path.name):
                if "/dev/tcp" not in body:
                    continue
                self.assertRegex(body, r"bash -c",
                                 "/dev/tcp needs bash, not sh")
                self.assertIn("command -v bash", body,
                              "absence of bash must be reported, not assumed")

    def test_a_blocked_api_is_distinguished_from_an_unreachable_one(self):
        body = commands(self.path().read_text())
        self.assertIn("124", body, "timeout's exit status must be classified")
        for mode in ("dns-failed", "pod-to-api-ok", "tooling-missing"):
            self.assertIn(mode, body)



class TestExecutorAndTLS(unittest.TestCase):
    """C06 additions: the executor Pod, the TLS listener and the state volume."""

    def executor(self) -> str:
        return (ROOT / "deploy/k3s/40-executor.yaml").read_text()

    def worker(self) -> str:
        return (ROOT / "deploy/k3s/20-worker.yaml").read_text()

    def test_the_executor_reuses_the_worker_image(self):
        """A second image would mean a second build, a second digest and a
        second supply chain for one process difference."""
        worker_images = set(re.findall(r"image:\s*(\S+)", self.worker()))
        executor_images = set(re.findall(r"image:\s*(\S+)", self.executor()))
        self.assertTrue(executor_images)
        self.assertTrue(executor_images <= worker_images,
                        "the executor must run the worker image")

    def test_the_executor_has_no_service_and_no_ingress(self):
        """Cancellation arrives through Redis, so a listener would be an
        attack surface with no caller."""
        self.assertNotIn("kind: Service", self.executor())
        self.assertNotIn("containerPort", self.executor())
        self.assertRegex(self.executor(), r"ingress:\s*\[\]")

    def test_the_executor_is_not_an_endpoint_of_the_worker_service(self):
        """The Service selects app + component; the executor carries a
        different component, so it can share the NetworkPolicy without
        receiving LAN traffic."""
        self.assertIn("component: executor", self.executor())
        self.assertIn("component: api", self.worker())

    def test_the_executor_serves_one_configured_relationship(self):
        """Scanning Redis for whatever relationships exist would serve a
        revoked one."""
        self.assertIn("AEGIS_RELATIONSHIP_ID", self.executor())
        self.assertIn("secretKeyRef", self.executor())

    def test_no_credential_is_inline_in_the_new_manifests(self):
        for text in (self.executor(), self.worker()):
            for line in commands(text).splitlines():
                if "AEGIS_REDIS_PASSWORD" in line or "AEGIS_WORKER_TOKEN" in line:
                    self.assertNotIn("value:", line,
                                     "credentials come from a Secret reference")

    def test_the_listener_terminates_tls_with_the_pinned_certificate(self):
        body = commands(self.worker())
        self.assertIn("--ssl-certfile", body)
        self.assertIn("--ssl-keyfile", body)
        self.assertIn("secretName: worker-tls", body)

    def test_the_non_root_worker_can_read_its_tls_key(self):
        worker = self.worker()
        self.assertIn("fsGroup: 10001", worker)
        self.assertIn("defaultMode: 0440", worker)

    def test_the_tls_key_is_not_committed(self):
        """The private key is the worker's identity. It is created on the
        worker host and mounted from a Secret the operator makes."""
        for path in sorted((ROOT / "deploy" / "k3s").rglob("*.yaml")):
            text = path.read_text(errors="ignore")
            self.assertNotIn("BEGIN PRIVATE KEY", text, str(path))
            self.assertNotIn("BEGIN RSA PRIVATE KEY", text, str(path))

    def test_pairing_state_survives_a_restart(self):
        """Relationship hashes on an emptyDir would silently unpair the
        coordinator every time the Pod moved."""
        worker = self.worker()
        self.assertIn("AEGIS_PAIRING_STATE", worker)
        self.assertIn("kind: PersistentVolumeClaim", worker)
        self.assertIn("claimName: worker-state", worker)

    def test_redis_stays_internal_after_c06(self):
        redis = commands((ROOT / "deploy/k3s/10-redis.yaml").read_text())
        self.assertIn("type: ClusterIP", redis)
        # Comments stripped: the file's own header names these to forbid them.
        for forbidden in ("NodePort", "LoadBalancer", "hostPort", "kind: Ingress"):
            self.assertNotIn(forbidden, redis)

    def test_the_executor_digest_is_pinned(self):
        self.assertRegex(self.executor(), r"image:\s*\S+@sha256:[0-9a-f]{64}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
