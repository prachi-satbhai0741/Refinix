"""Behavioural checks for the host guard script and its systemd units.

The guard is exercised as a subprocess against a stubbed `iptables` and `ip`,
so the real script is tested rather than a paraphrase. No rules are applied to
this machine.

    python3 -m unittest deploy.k3s.host.test_guard
"""

import os
import pathlib
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
GUARD = HERE / "aegisforge-guard.sh"

FAKE_IP = """#!/bin/sh
case "$*" in
  *"route show default"*) echo "default via 192.168.29.1 dev wlo1 proto dhcp" ;;
  *"addr show cni0"*)     [ -n "${NO_BRIDGE:-}" ] || echo "2: cni0    inet 10.42.0.1/24 brd 10.42.0.255 scope global cni0" ;;
esac
exit 0
"""

# Records every invocation and reports "rule absent" for -C, so apply inserts.
FAKE_IPTABLES = """#!/bin/sh
echo "$@" >> "$IPT_LOG"
case "$1" in
  -C) exit 1 ;;
  -S) cat "$IPT_STATE" 2>/dev/null; exit 0 ;;
  -D) grep -v -- "aegisforge-c05" "$IPT_STATE" > "$IPT_STATE.new" 2>/dev/null || true
      mv "$IPT_STATE.new" "$IPT_STATE"; exit 0 ;;
esac
exit 0
"""


class GuardCase(unittest.TestCase):
    def run_guard(self, *args, state="", **env_extra):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = pathlib.Path(tmp) / "bin"
            bin_dir.mkdir()
            (bin_dir / "ip").write_text(FAKE_IP)
            (bin_dir / "iptables").write_text(FAKE_IPTABLES)
            for name in ("ip", "iptables"):
                (bin_dir / name).chmod(0o755)
            log = pathlib.Path(tmp) / "calls.log"
            state_file = pathlib.Path(tmp) / "state"
            state_file.write_text(state)
            env = {**os.environ,
                   "PATH": f"{bin_dir}:{os.environ['PATH']}",
                   "IPT_LOG": str(log), "IPT_STATE": str(state_file),
                   **env_extra}
            result = subprocess.run(["sh", str(GUARD), *args], env=env,
                                    capture_output=True, text=True, timeout=30)
            result.calls = log.read_text() if log.exists() else ""
            return result


class TestClusterGuard(GuardCase):
    def test_loopback_and_cluster_traffic_stay_allowed(self):
        result = self.run_guard("apply", "cluster")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-i lo -p tcp --dport 6443 -j ACCEPT", result.calls)
        self.assertIn("-s 10.42.0.0/16 -j ACCEPT", result.calls)
        self.assertIn("-s 10.43.0.0/16 -j ACCEPT", result.calls)

    def test_only_the_lan_interface_is_dropped(self):
        """A blanket drop would break cluster components reaching the API."""
        result = self.run_guard("apply", "cluster")
        # Count inserted rules only; -C is a presence probe, not a rule.
        drops = [line for line in result.calls.splitlines()
                 if "-j DROP" in line and line.startswith("-I")]
        self.assertEqual(len(drops), 1, drops)
        self.assertIn("-i wlo1", drops[0])

    def test_nodeport_is_not_handled_here(self):
        """NodePort traffic is forwarded, never traversing INPUT."""
        result = self.run_guard("apply", "cluster")
        self.assertNotIn("30443", result.calls)

    def test_rules_are_tagged_for_surgical_removal(self):
        result = self.run_guard("apply", "cluster")
        self.assertIn("--comment aegisforge-c05-api", result.calls)

    def test_apply_is_idempotent(self):
        """-C reporting the rule present must skip the insert, not stack it."""
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = pathlib.Path(tmp) / "bin"; bin_dir.mkdir()
            (bin_dir / "ip").write_text(FAKE_IP)
            (bin_dir / "iptables").write_text(
                '#!/bin/sh\necho "$@" >> "$IPT_LOG"\ncase "$1" in -C) exit 0;; esac\nexit 0\n')
            for name in ("ip", "iptables"):
                (bin_dir / name).chmod(0o755)
            log = pathlib.Path(tmp) / "calls.log"
            env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
                   "IPT_LOG": str(log), "IPT_STATE": str(pathlib.Path(tmp) / "s")}
            subprocess.run(["sh", str(GUARD), "apply", "cluster"], env=env,
                           capture_output=True, text=True, timeout=30)
            calls = log.read_text()
            self.assertNotIn("-I INPUT", calls,
                             "an existing rule must not be inserted again")

    def test_removal_never_flushes_a_chain(self):
        state = ('-A INPUT -p tcp --dport 22 -j ACCEPT\n'
                 '-A INPUT -i lo -p tcp --dport 6443 -j ACCEPT '
                 '-m comment --comment "aegisforge-c05-api"\n')
        result = self.run_guard("remove", "cluster", state=state)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("-F", result.calls, "a flush would destroy unrelated rules")
        self.assertIn("-D INPUT", result.calls)
        self.assertNotIn("--dport 22", result.calls,
                         "only AegisForge-tagged rules may be removed")


class TestOllamaGuard(GuardCase):
    def test_forwarder_is_limited_to_the_pod_cidr(self):
        result = self.run_guard("apply", "ollama")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-d 10.42.0.1 --dport 11434 -s 10.42.0.0/16 -j ACCEPT", result.calls)
        self.assertIn("-d 10.42.0.1 --dport 11434 -j DROP", result.calls)

    def test_bridge_address_is_derived_not_assumed(self):
        result = self.run_guard("apply", "ollama", NO_BRIDGE="1")
        self.assertNotEqual(result.returncode, 0,
                            "a missing bridge must fail, not fall back to a guess")
        self.assertIn("no IPv4 address", result.stderr)

    def test_ollama_loopback_is_never_touched(self):
        result = self.run_guard("apply", "ollama")
        self.assertNotIn("127.0.0.1", result.calls,
                         "Ollama's own listener must not be firewalled")


class TestUnits(unittest.TestCase):
    """Protection must be established before the listener, and removed after."""

    def unit(self, name):
        return (HERE / name).read_text()

    def test_k3s_requires_the_cluster_guard(self):
        drop_in = self.unit("k3s-requires-guard.conf")
        self.assertIn("Requires=aegisforge-cluster-guard.service", drop_in)
        self.assertIn("After=aegisforge-cluster-guard.service", drop_in)

    def test_cluster_guard_runs_before_k3s(self):
        self.assertIn("Before=k3s.service", self.unit("aegisforge-cluster-guard.service"))

    def test_proxy_socket_requires_its_guard(self):
        socket = self.unit("aegisforge-ollama-proxy.socket")
        self.assertIn("Requires=aegisforge-ollama-guard.service", socket)
        self.assertIn("After=aegisforge-ollama-guard.service", socket)

    def test_guards_remove_their_rules_on_stop(self):
        for name in ("aegisforge-cluster-guard.service", "aegisforge-ollama-guard.service"):
            with self.subTest(unit=name):
                self.assertIn("ExecStop=", self.unit(name))
                self.assertIn("RemainAfterExit=yes", self.unit(name))

    def test_ollama_guard_waits_for_the_bridge(self):
        unit = self.unit("aegisforge-ollama-guard.service")
        self.assertIn("ExecStartPre=", unit)
        self.assertIn("cni0", unit)

    def test_proxy_targets_the_untouched_loopback_listener(self):
        self.assertIn("127.0.0.1:11434", self.unit("aegisforge-ollama-proxy.service"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
