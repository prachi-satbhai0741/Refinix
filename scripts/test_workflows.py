"""The release and feed workflows keep their triggers, permissions and pins.

Text checks with the standard library only (no YAML parser is installed in
CI): every action is pinned to a full commit SHA; the Beta package workflow
is manual, read-only and never publishes; the feed workflows share one queue,
deploy Pages explicitly from exactly the signed commit, keep signing secrets
out of the deploy and live-check jobs, and never force over a moved branch.

    python3 -m unittest scripts.test_workflows -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
DISTRIBUTION = REPO / "deploy" / "distribution" / "workflows"
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)", re.M)


def jobs(text: str) -> dict[str, str]:
    """Each job's block, split on two-space-indented job keys under `jobs:`."""
    body = text.split("\njobs:\n", 1)[1]
    found, name, lines = {}, None, []
    for line in body.splitlines():
        match = re.match(r"^  ([a-z][a-z0-9-]*):\s*$", line)
        if match:
            if name:
                found[name] = "\n".join(lines)
            name, lines = match.group(1), []
        elif name:
            lines.append(line)
    if name:
        found[name] = "\n".join(lines)
    return found


class TestPins(unittest.TestCase):
    def test_every_action_is_pinned_to_a_commit(self):
        files = list(WORKFLOWS.glob("*.yml")) + list(DISTRIBUTION.glob("*.yml"))
        self.assertTrue(files)
        for path in files:
            for action in USES.findall(path.read_text(encoding="utf-8")):
                with self.subTest(file=path.name, action=action):
                    self.assertRegex(action, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


class TestBetaPackages(unittest.TestCase):
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")

    def test_started_by_hand_only_and_read_only(self):
        triggers = self.text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertIn("workflow_dispatch:", triggers)
        for other in ("push:", "pull_request", "schedule:", "workflow_run"):
            self.assertNotIn(other, triggers)
        self.assertRegex(self.text, r"\npermissions:\n  contents: read\n")
        self.assertNotIn("contents: write", self.text)

    def test_it_builds_only_the_designated_main_commit(self):
        check = jobs(self.text)["check"]
        self.assertIn('[ "$GITHUB_REF" = "refs/heads/main" ]', check)
        self.assertIn('[ "$GITHUB_SHA" = "$REFINIX_COMMIT" ]', check)
        self.assertIn("release.parse", check)

    def test_it_never_publishes(self):
        for word in ("gh release", "softprops/", "upload-release", "git push", "git tag",
                     "deploy-pages"):
            self.assertNotIn(word, self.text)

    def test_the_ubuntu_build_has_the_shared_python_library(self):
        # PyInstaller refuses Ubuntu's system Python without libpython3.12
        # (observed in an Ubuntu 24.04 container, 2026-10-08).
        for name in ("release.yml", "package.yml"):
            self.assertIn("libpython3.12",
                          (WORKFLOWS / name).read_text(encoding="utf-8"), name)

    def test_the_ubuntu_qualification_runs_on_the_built_package_as_root(self):
        package = jobs(self.text)["package"]
        self.assertIn("sudo env REFINIX_QUALIFY_DISPOSABLE=1", package)
        self.assertIn("scripts/qualify_deb.py --real out/refinix_*_amd64.deb", package)
        # Release tooling is installed after the build, never into the package.
        self.assertLess(package.index("desktop/build.py --channel beta"),
                        package.index("requirements-release.lock"))
        # Tests that sign throwaway feeds run only once that lock is installed.
        self.assertLess(package.index("requirements-release.lock"),
                        package.index("desktop.test_deb_root"))

    def test_signing_secrets_appear_only_in_the_signing_environment_job(self):
        package = jobs(self.text)["package"]
        self.assertIn("'beta-sign'", package)
        self.assertNotIn("secrets.", jobs(self.text)["check"])


class TestPackageLocks(unittest.TestCase):
    """A packaging workflow installs exactly the locks the packaging plan ships
    and builds with for that lane: a missing lock is a package without, say,
    its update client, and PyInstaller would build it without complaint."""

    def test_each_lane_installs_the_packaging_plan_locks(self):
        import sys
        sys.path.insert(0, str(REPO))
        from desktop import packaging_plan
        for name in ("release.yml", "package.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            for lane, locks in re.findall(
                    r'\{"lane": "([a-z0-9-]+)", "runner": "[^"]+",\s*"locks": "([^"]+)"\}',
                    text):
                with self.subTest(workflow=name, lane=lane):
                    entry = packaging_plan.LANES[lane]
                    self.assertEqual(sorted(locks.split()),
                                     sorted(entry.locks + entry.build_locks))


class TestFeedWorkflows(unittest.TestCase):
    def read(self, name):
        return (DISTRIBUTION / name).read_text(encoding="utf-8")

    def test_every_deploy_and_feed_change_shares_one_queue(self):
        for name in ("deploy-site.yml", "advance-feed.yml", "refresh-feed.yml"):
            with self.subTest(name=name):
                text = self.read(name)
                self.assertRegex(text, r"concurrency:\n  group: beta-feed\n"
                                       r"  cancel-in-progress: false")
                self.assertRegex(text, r"\npermissions:\n  contents: read\n")

    def test_pages_is_deployed_explicitly_from_the_signed_commit(self):
        for name in ("advance-feed.yml", "refresh-feed.yml"):
            with self.subTest(name=name):
                parts = jobs(self.read(name))
                self.assertIn("contents: write", parts["sign"])
                self.assertNotIn("pages: write", parts["sign"])
                deploy = parts["deploy"]
                self.assertIn("ref: ${{ needs.sign.outputs.commit }}", deploy)
                self.assertIn("pages: write", deploy)
                self.assertIn("id-token: write", deploy)
                self.assertIn("actions/deploy-pages@", deploy)
                for job in ("deploy", "live"):
                    self.assertNotIn("secrets.", parts[job], job)
                self.assertIn("--trust-root", parts["live"])

    def test_signing_never_forces_over_a_moved_branch(self):
        for name in ("advance-feed.yml", "refresh-feed.yml"):
            with self.subTest(name=name):
                sign = jobs(self.read(name))["sign"]
                self.assertIn('--force-with-lease="main:$before"', sign)
                self.assertNotIn("--force ", sign)
                self.assertNotIn("reset --hard", sign)

    def test_advancing_needs_a_reviewer_environment_and_refreshing_runs_daily(self):
        advance = self.read("advance-feed.yml")
        self.assertIn("environment: beta-publish", advance)
        self.assertIn("--packages-url", advance)
        refresh = self.read("refresh-feed.yml")
        self.assertIn("environment: beta-feed-refresh", refresh)
        self.assertRegex(refresh, r"schedule:\n    - cron: ")
        self.assertIn("--monitor", refresh)
        self.assertIn("issues: write", jobs(refresh)["alert"])

    def test_the_site_deploy_never_replaces_a_newer_tree(self):
        deploy = self.read("deploy-site.yml")
        self.assertIn("git ls-remote", deploy)
        self.assertIn("skip=1", deploy)


if __name__ == "__main__":
    unittest.main(verbosity=2)
