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
  *"addr show wlo1"*)     [ -n "${NO_LAN_ADDRESS:-}" ] || echo "3: wlo1    inet 192.168.29.42/24 brd 192.168.29.255 scope global wlo1" ;;
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


class TestWorkerGuard(GuardCase):
    """C06's LAN forwarder for the worker, on 30443.

    The whole reason this guard exists: NodePort traffic is DNATed and
    forwarded, so it never traverses INPUT and iptables cannot restrict it.
    The NodePort therefore stays on loopback and a host socket forwards to it,
    which puts the traffic back in a chain that can be filtered.
    """

    MAC = "192.168.29.31"
    LAN = "192.168.29.42"

    def apply(self, **extra):
        return self.run_guard("apply", "worker", AEGIS_MAC_ADDRESS=self.MAC,
                              **extra)

    def test_the_paired_mac_reaches_the_forwarder(self):
        result, v4, _ = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(verdict(v4, {"dest": self.LAN, "dport": 30443,
                                      "source": self.MAC}), "ACCEPT")

    def test_every_other_lan_address_is_dropped(self):
        _, v4, _ = self.apply()
        for other in ("192.168.29.99", "192.168.29.1", "10.0.0.5"):
            with self.subTest(source=other):
                self.assertEqual(verdict(v4, {"dest": self.LAN, "dport": 30443,
                                              "source": other}), "DROP")

    def test_ipv6_stays_closed(self):
        _, _, v6 = self.apply()
        self.assertEqual(verdict(v6, {"in_interface": "wlo1", "dport": 30443}),
                         "DROP")

    def test_the_accept_precedes_the_drop(self):
        """The DROP is a superset of the ACCEPT, so the reverse order would
        block the paired Mac along with everyone else."""
        _, v4, _ = self.apply()
        indices = [i for i, rule in enumerate(v4) if "30443" in rule]
        self.assertEqual(len(indices), 2)
        self.assertIn("ACCEPT", v4[indices[0]])
        self.assertIn("DROP", v4[indices[1]])

    def test_a_missing_mac_address_refuses_rather_than_opening_the_port(self):
        result, v4, _ = self.run_guard("apply", "worker")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AEGIS_MAC_ADDRESS", result.stderr)
        self.assertEqual([r for r in v4 if "30443" in r], [],
                         "a forgotten address must leave the port closed")

    def test_a_cidr_or_range_is_refused(self):
        """A subnet here would silently widen the one rule that limits who may
        reach the worker."""
        for bad in ("192.168.29.0/24", "192.168.29.31-40", "mac.local", "",
                    "999.1.1.1"):
            with self.subTest(value=bad):
                result, v4, _ = self.run_guard("apply", "worker",
                                               AEGIS_MAC_ADDRESS=bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([r for r in v4 if "30443" in r], [])

    def test_applying_twice_is_idempotent(self):
        self.apply()
        _, v4, v6 = self.apply()
        self.assertEqual(len([r for r in v4 if "30443" in r]), 2)
        self.assertEqual(len([r for r in v6 if "30443" in r]), 1)

    def test_removal_takes_only_this_guard_s_rules(self):
        result, v4, v6 = self.run_guard(
            "remove", "worker", AEGIS_MAC_ADDRESS=self.MAC,
            seed4=["-p tcp --dport 22 -j ACCEPT"], seed6=[])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-p tcp --dport 22 -j ACCEPT", v4)

    def test_the_guard_and_the_other_guards_do_not_interfere(self):
        _, v4, _ = self.run_guard("apply", "cluster")
        self.assertEqual([r for r in v4 if "30443" in r], [],
                         "the cluster guard must not touch the worker port")


class TestNodePortIsNotWidened(unittest.TestCase):
    """Current and archived runbooks must not expose the NodePort to the LAN.

    An earlier draft did exactly that — it set `nodeport-addresses` to the
    whole subnet and then tried to restrict 30443 with INPUT rules, which
    cannot work for DNATed traffic. These read the shipped documentation
    because that is where the instruction lives.
    """

    def documents(self):
        root = HERE.parents[2]
        return [root / "docs/worker-operations.md",
                root / "docs/archive/c06-distributed-execution-handoff.md",
                root / "docs/archive/c05-ubuntu-deployment-handoff.md"]

    def test_nodeport_addresses_is_never_widened_to_a_subnet(self):
        for path in self.documents():
            for line in path.read_text().splitlines():
                if "nodeport-addresses" not in line:
                    continue
                with self.subTest(document=path.name, line=line.strip()[:80]):
                    self.assertNotRegex(
                        line, r"nodeport-addresses=(?!127\.0\.0\.1/32)[0-9]",
                        "the NodePort must stay on loopback; a host forwarder "
                        "is what exposes it to one address")

    def test_the_handoff_never_claims_input_protects_the_nodeport(self):
        for path in self.documents():
            for line in path.read_text().splitlines():
                lowered = line.lower()
                if "iptables" in lowered and "30443" in line and "proxy" not in lowered:
                    with self.subTest(document=path.name, line=line.strip()[:80]):
                        self.assertNotIn("dport 30443", line,
                                         "an INPUT rule on the NodePort does not "
                                         "filter DNATed traffic")

    def test_the_handoff_uses_the_forwarder_and_the_guard(self):
        for path in self.documents()[:2]:  # Current runbook and archived C06.
            with self.subTest(document=path.name):
                text = path.read_text()
                self.assertIn("aegisforge-worker-proxy", text)
                self.assertIn("apply worker", text)
                self.assertIn("AEGIS_MAC_ADDRESS", text)

    def test_the_guard_script_states_why_input_cannot_cover_nodeport(self):
        header = GUARD.read_text()[:4000]
        self.assertIn("DNAT", header.upper().replace("DNATED", "DNAT"))


class TestWorkerProxyUnits(unittest.TestCase):
    def unit(self, name: str) -> str:
        return (HERE / name).read_text()

    def test_the_socket_cannot_listen_without_the_guard(self):
        socket = self.unit("aegisforge-worker-proxy.socket")
        self.assertIn("Requires=aegisforge-worker-guard.service", socket)
        self.assertIn("After=aegisforge-worker-guard.service", socket)

    def test_the_socket_binds_one_address_not_every_interface(self):
        socket = self.unit("aegisforge-worker-proxy.socket")
        self.assertIn("ListenStream=LAN_ADDRESS:30443", socket)
        self.assertNotRegex(socket, r"ListenStream=\d+\s*$",
                            "a bare port binds every interface, including IPv6")

    def test_the_proxy_forwards_to_loopback_not_to_a_lan_address(self):
        service = self.unit("aegisforge-worker-proxy.service")
        self.assertIn("127.0.0.1:30443", service)

    def test_the_proxy_does_not_terminate_tls(self):
        """systemd-socket-proxyd copies bytes, so the pinned session stays
        end-to-end and this host holds no key."""
        service = self.unit("aegisforge-worker-proxy.service")
        self.assertIn("SOCKET_PROXY_PATH", service)
        for forbidden in ("ssl", "tls.key", "certfile", "openssl"):
            self.assertNotIn(forbidden, service.lower())

    def test_the_guard_unit_requires_the_mac_address(self):
        guard = self.unit("aegisforge-worker-guard.service")
        self.assertIn("AEGIS_MAC_ADDRESS", guard)
        self.assertIn("apply worker", guard)
        self.assertIn("remove worker", guard)

    def test_the_guard_does_not_assume_nodeport_is_a_process_listener(self):
        guard = self.unit("aegisforge-worker-guard.service")
        self.assertNotIn("ExecStartPre", guard)


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
