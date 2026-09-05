"""Behavioural checks for the host guard script and its systemd units.

The guard is exercised as a subprocess against a stubbed `iptables`, `ip6tables`
and `ip`, so the real script is tested rather than a paraphrase. No rules are
applied to this machine.

The stub models an ORDERED chain and the tests match simulated packets against
it, because rule presence is not the property that matters: a DROP that overlaps
its own ACCEPT is correct only when the ACCEPT sits above it. An earlier version
of these tests asserted presence alone and passed while `apply ollama` blocked
every Pod it existed to serve.

The stub also renders comments unquoted, which is what iptables actually does
for a comment containing no characters needing escaping. The previous fixture
quoted them, so removal appeared to work while matching nothing on a real host.

    python3 -m unittest deploy.k3s.host.test_guard
"""

import ipaddress
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

# An ordered chain with real insert/delete/check semantics. Each family keeps
# its own state file, so IPv4 and IPv6 coverage are observed separately.
FAKE_IPTABLES = '''#!/usr/bin/env python3
import json, os, sys

family = os.path.basename(sys.argv[0])
path = os.environ["IPT_STATE"] + "." + family
args = sys.argv[1:]
rules = json.loads(open(path).read()) if os.path.exists(path) else []

def save():
    open(path, "w").write(json.dumps(rules))

def spec(parts):
    return " ".join(parts)

if not args:
    sys.exit(0)
if args[0] == "-I":                      # -I INPUT <pos> <rule...>
    rules.insert(int(args[2]) - 1, spec(args[3:])); save(); sys.exit(0)
if args[0] == "-C":                      # -C INPUT <rule...>
    sys.exit(0 if spec(args[2:]) in rules else 1)
if args[0] == "-D":                      # -D INPUT <rule...>
    rule = spec(args[2:])
    if rule in rules:
        rules.remove(rule); save(); sys.exit(0)
    sys.exit(1)
if args[0] == "-S":
    for rule in rules:
        print("-A INPUT " + rule)
    sys.exit(0)
sys.exit(0)
'''


def matches(rule, packet):
    """True when this rule selects the packet. Mirrors the fields we emit."""
    parts = rule.split()
    for flag, value in zip(parts, parts[1:]):
        if flag == "-i" and packet.get("in_interface") != value:
            return False
        if flag == "-d" and packet.get("dest") != value:
            return False
        if flag == "--dport" and str(packet.get("dport")) != value:
            return False
        if flag == "-s":
            source = packet.get("source")
            if source is None:
                return False
            if ipaddress.ip_address(source) not in ipaddress.ip_network(value):
                return False
    return True


def verdict(chain, packet):
    """First matching rule wins, exactly as netfilter walks a chain."""
    for rule in chain:
        if matches(rule, packet):
            parts = rule.split()
            if "-j" in parts:
                return parts[parts.index("-j") + 1]
    return "NO-MATCH"


class GuardCase(unittest.TestCase):
    def run_guard(self, *args, seed4=(), seed6=(), **env_extra):
        """Run the guard and return (result, ipv4 chain, ipv6 chain)."""
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = pathlib.Path(tmp) / "bin"
            bin_dir.mkdir()
            (bin_dir / "ip").write_text(FAKE_IP)
            for name in ("iptables", "ip6tables"):
                (bin_dir / name).write_text(FAKE_IPTABLES)
            for name in ("ip", "iptables", "ip6tables"):
                (bin_dir / name).chmod(0o755)
            state = pathlib.Path(tmp) / "state"
            import json
            for family, seed in (("iptables", seed4), ("ip6tables", seed6)):
                pathlib.Path(f"{state}.{family}").write_text(json.dumps(list(seed)))
            env = {**os.environ,
                   "PATH": f"{bin_dir}:{os.environ['PATH']}",
                   "IPT_STATE": str(state), **env_extra}
            result = subprocess.run(["sh", str(GUARD), *args], env=env,
                                    capture_output=True, text=True, timeout=30)
            chains = []
            for family in ("iptables", "ip6tables"):
                text = pathlib.Path(f"{state}.{family}").read_text()
                chains.append(json.loads(text) if text else [])
            return result, chains[0], chains[1]


class TestClusterGuard(GuardCase):
    def test_lan_traffic_to_both_admin_ports_is_dropped(self):
        result, v4, _ = self.run_guard("apply", "cluster")
        self.assertEqual(result.returncode, 0, result.stderr)
        for port in (6443, 10250):
            with self.subTest(port=port):
                self.assertEqual(
                    verdict(v4, {"in_interface": "wlo1",
                                 "source": "192.168.29.50", "dport": port}),
                    "DROP")

    def test_loopback_reaches_both_admin_ports(self):
        """The apiserver reaches the kubelet over lo; a blanket drop breaks it."""
        _, v4, _ = self.run_guard("apply", "cluster")
        for port in (6443, 10250):
            with self.subTest(port=port):
                self.assertEqual(
                    verdict(v4, {"in_interface": "lo",
                                 "source": "127.0.0.1", "dport": port}), "ACCEPT")

    def test_pods_reach_the_api_and_the_kubelet(self):
        """metrics-server scrapes the kubelet from a Pod; that must survive."""
        _, v4, _ = self.run_guard("apply", "cluster")
        for port in (6443, 10250):
            with self.subTest(port=port):
                self.assertEqual(
                    verdict(v4, {"in_interface": "cni0",
                                 "source": "10.42.0.9", "dport": port}), "ACCEPT")

    def test_service_cidr_reaches_the_api(self):
        _, v4, _ = self.run_guard("apply", "cluster")
        self.assertEqual(
            verdict(v4, {"in_interface": "cni0",
                         "source": "10.43.0.7", "dport": 6443}), "ACCEPT")

    def test_ipv6_lan_is_dropped_and_loopback_kept(self):
        """The listeners bind dual-stack; an IPv4-only guard leaves a path."""
        _, _, v6 = self.run_guard("apply", "cluster")
        self.assertNotEqual(v6, [], "IPv6 must be covered, not skipped")
        for port in (6443, 10250):
            with self.subTest(port=port):
                self.assertEqual(
                    verdict(v6, {"in_interface": "wlo1", "dport": port}), "DROP")
                self.assertEqual(
                    verdict(v6, {"in_interface": "lo", "dport": port}), "ACCEPT")

    def test_every_drop_is_scoped_to_the_lan_interface(self):
        _, v4, v6 = self.run_guard("apply", "cluster")
        for rule in [r for r in v4 + v6 if "-j DROP" in r]:
            with self.subTest(rule=rule):
                self.assertIn("-i wlo1", rule,
                              "an unscoped drop would break cluster components")

    def test_nodeport_is_not_handled_here(self):
        """NodePort traffic is forwarded, never traversing INPUT."""
        _, v4, v6 = self.run_guard("apply", "cluster")
        self.assertNotIn("30443", " ".join(v4 + v6))

    def test_rules_are_tagged_for_surgical_removal(self):
        _, v4, v6 = self.run_guard("apply", "cluster")
        for rule in v4 + v6:
            with self.subTest(rule=rule):
                self.assertIn("--comment aegisforge-c05-api", rule)

    def test_apply_twice_does_not_stack_rules(self):
        _, once, _ = self.run_guard("apply", "cluster")
        with tempfile.TemporaryDirectory() as tmp:
            pass
        # Re-apply over the chain the first run produced.
        _, twice, _ = self.run_guard("apply", "cluster", seed4=once)
        self.assertEqual(once, twice, "re-applying must be a no-op, not a stack")

    def test_removal_deletes_our_rules_and_keeps_the_hosts(self):
        unrelated = "-p tcp --dport 22 -j ACCEPT"
        _, applied, applied6 = self.run_guard("apply", "cluster", seed4=[unrelated])
        self.assertIn(unrelated, applied)
        result, v4, v6 = self.run_guard("remove", "cluster",
                                        seed4=applied, seed6=applied6)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(v4, [unrelated], "only tagged rules may be removed")
        self.assertEqual(v6, [], "IPv6 rules must be removed too")

    def test_removal_reports_what_it_removed(self):
        _, applied, applied6 = self.run_guard("apply", "cluster")
        result, _, _ = self.run_guard("remove", "cluster",
                                      seed4=applied, seed6=applied6)
        self.assertIn("removed 8 IPv4 and 4 IPv6", result.stdout)

    def test_removal_leaves_the_other_guards_rules_alone(self):
        _, cluster4, _ = self.run_guard("apply", "cluster")
        _, both4, _ = self.run_guard("apply", "ollama", seed4=cluster4)
        ollama_rules = [r for r in both4 if "aegisforge-c05-ollama" in r]
        self.assertTrue(ollama_rules)
        _, after, _ = self.run_guard("remove", "cluster", seed4=both4)
        self.assertEqual(after, ollama_rules,
                         "removing one guard must not disturb the other")


class TestOllamaGuard(GuardCase):
    def test_pods_reach_the_forwarder(self):
        """The regression that matters: an ACCEPT below its DROP is dead."""
        result, v4, _ = self.run_guard("apply", "ollama")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            verdict(v4, {"dest": "10.42.0.1", "source": "10.42.0.9",
                         "dport": 11434}),
            "ACCEPT",
            "the worker Pod must reach the runtime forwarder")

    def test_everything_else_is_dropped_at_the_forwarder(self):
        _, v4, _ = self.run_guard("apply", "ollama")
        self.assertEqual(
            verdict(v4, {"dest": "10.42.0.1", "source": "192.168.29.50",
                         "dport": 11434}),
            "DROP")

    def test_accept_is_ordered_above_the_drop(self):
        _, v4, _ = self.run_guard("apply", "ollama")
        ours = [r for r in v4 if "aegisforge-c05-ollama" in r]
        targets = ["ACCEPT" if "-j ACCEPT" in r else "DROP" for r in ours]
        self.assertEqual(targets, ["ACCEPT", "DROP"],
                         "this DROP is a superset of its ACCEPT, so order decides")

    def test_bridge_address_is_derived_not_assumed(self):
        result, _, _ = self.run_guard("apply", "ollama", NO_BRIDGE="1")
        self.assertNotEqual(result.returncode, 0,
                            "a missing bridge must fail, not fall back to a guess")
        self.assertIn("no IPv4 address", result.stderr)

    def test_ollama_loopback_is_never_touched(self):
        _, v4, v6 = self.run_guard("apply", "ollama")
        self.assertNotIn("127.0.0.1", " ".join(v4 + v6),
                         "Ollama's own listener must not be firewalled")

    def test_removal_is_complete(self):
        _, applied, _ = self.run_guard("apply", "ollama")
        result, v4, _ = self.run_guard("remove", "ollama", seed4=applied)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(v4, [])


class TestRemovalDoesNotParseSaveOutput(unittest.TestCase):
    """iptables quotes a comment only when it needs escaping. A remover keyed
    to quoted output matches nothing on a real host and silently succeeds."""

    def test_no_rule_text_is_parsed_back_out_of_iptables(self):
        body = GUARD.read_text()
        removal = body.split("remove_rules()")[1].split("apply_rules()")[0]
        self.assertNotIn("-S", removal,
                         "removal must reconstruct specs, not parse -S output")
        self.assertNotIn("grep", removal)
        self.assertNotIn("sed", removal)


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
