# C05 — Ubuntu cluster deployment handoff

> Historical prototype record/template. Retained for reproduction and dated evidence.
> Current scope and order are in [tasks.md](../../tasks.md#numbered-execution-tasks);
> refresh source/device facts and obtain applicable authorisation before using old steps.

**Device role:** Ubuntu worker. **OS:** Ubuntu 24.04.4 LTS, x86_64.
**Shell:** bash. **Directory:** `/home/prachi/SIH/AegisForge`.

One ordered sequence, **A** to **K**. Every step is a host change and stays at
this checkpoint.

## Execution state (2026-09-04)

**A, B and D are complete on the Ubuntu host; E onward are not.** The host is
currently powered down and off this network, so nothing can proceed until it is
back.

| Step | State |
|---|---|
| A preflight | done — see the adaptation below |
| B artifact | done — all three digests matched provenance |
| C installer | **skipped, and correctly so** — K3s was already installed |
| D protection and start | done — adapted, see below |
| E Pod networking | not run |
| F image and manifests | **partially done** — namespace, Secrets, Redis and worker applied; the worker Pod is not running |
| G–K | not run |

**The adaptation.** The preflight found K3s already installed and running:
`v1.36.4+k3s1`, exactly the OD-08 pin, but a stock install — `ExecStart` was a
bare `k3s server` with no options, so Traefik and ServiceLB were enabled, there
was no `nodeport-addresses` restriction, and 6443 and 10250 were listening on
every address. The cluster held nothing: four default namespaces, no
NetworkPolicy, no workloads.

Steps C and D as originally written assume a clean host and were **not** run.
Instead the settings were applied through `/etc/rancher/k3s/config.yaml`, K3s's
[documented persistent equivalent to CLI options](https://docs.k3s.io/installation/configuration#configuration-file),
and the cluster restarted. Reinstalling would have cost a teardown to reach the
same state and would have buried the settings in the unit's `ExecStart`. **D
below is the adapted procedure, and it is what was actually run.**

Recorded evidence: all guard rules present *after* the restart, so K3s's own
iptables reconciliation did not flush them; `nc -w 5 -vz 192.168.68.207 6443`
from the Mac **timed out**, where the same command connected beforehand;
CoreDNS rolled out; node `Ready`; Jenkins, nginx and Ollama untouched.

## What C05 proves, and what it does not

**Proves:** Ready workloads, working cluster DNS and Pod-to-API networking,
Redis internal-only with *both* allowed and denied access demonstrated, real
bounded inference through the worker's runtime adapter inside its Pod, shared
contract/version evidence, coordinator metadata surviving a restart, and Jenkins,
Docker and Ollama still working.

**Does not prove:** paired Mac-to-worker dispatch through Redis, durable
receipts, cancellation or recovery. Those are C06. The worker's public job
routes stay **fail-closed** throughout — they are not opened to manufacture a
C05 result, and **adapter-level inference is not distributed completion**.

## Jenkins and your existing services

K3s runs without Traefik or ServiceLB, so it binds no port 80 or 443. Its ports
are 6443 and 10250, both closed to the LAN by the cluster guard; the worker uses
NodePort 30443, restricted to loopback by kube-proxy. **Nothing touches 8080.**
K3s uses its own containerd, so Docker's images and containers are untouched,
and Ollama's configuration is never modified.

The preflight on this host also found **nginx on port 80**, unrelated to K3s and
predating this work. It is left alone. Nothing in C05 needs port 80.

---

## A. Read-only preflight

```bash
cd /home/prachi/SIH/AegisForge
git status --short --branch
git rev-parse --short HEAD

for tool in iptables ip6tables ip ss curl python3 sha256sum timeout openssl systemd-socket-proxyd; do
  printf '%-24s %s\n' "$tool" "$(command -v "$tool" || echo MISSING)"
done
ls /usr/lib/systemd/systemd-socket-proxyd /lib/systemd/systemd-socket-proxyd 2>/dev/null

systemctl is-active k3s 2>/dev/null || echo "k3s: not installed"
ip -brief address show
ip route show default
sudo iptables -S INPUT | head -20
sudo nft list ruleset 2>/dev/null | head -5 || echo "nftables: no ruleset or not installed"
sudo ss -ltnp '( sport = :6443 or sport = :10250 or sport = :30443 or sport = :8080 or sport = :11434 )'
df -h / /var/lib
```

Return this. It settles the firewall backend, the LAN interface, whether the
ports are free, and that `timeout` and `systemd-socket-proxyd` exist. **Stop if
`iptables`, `ip6tables` or `systemd-socket-proxyd` is missing** — the guards
depend on all three. `ip6tables` is required because the API and kubelet
listeners bind dual-stack and the LAN interface carries a link-local IPv6
address, so an IPv4-only guard would leave a reachable path.

Also record `systemctl cat k3s | grep ExecStart -A6` if `k3s` reports active:
an existing installation changes step D, and its options decide how.

Expect Jenkins on 8080 and Ollama on `127.0.0.1:11434`. Roughly 3 GB of free
space covers K3s, its images and the worker.

## B. Confirm the preserved artifact and the reviewed revision

```bash
ls -l /home/prachi/.aegisforge/artifacts/c04/worker.tar
python3 scripts/image-digests.py /home/prachi/.aegisforge/artifacts/c04/worker.tar
python3 -c "import json;d=json.load(open('backend/worker-image/provenance.json'))['ubuntu_build'];print(d['manifest_digest']);print(d['archive_sha256'])"
```

The `manifest_digest` and `archive_sha256` must match provenance.json exactly:

```
manifest sha256:a1eb434c91ff5e51a095ccbdc5becd10e98a099a281302ef68e86b531543a295
archive  sha256:53eb20e4d77b222e783d7bd50fb3339663fbd5001feb9a704f4482800d108a9a
```

**If either differs, stop and report.** Do not rebuild: the manifests pin this
digest and C04 is accepted as it stands.

## C. Obtain the installer — only if K3s is absent

**Skip this entirely if step A reported `k3s` active.** It was skipped on this
host, which already had `v1.36.4+k3s1`.

| | |
|---|---|
| Component | K3s `v1.36.4+k3s1` — the `stable` channel at OD-08 |
| Source | `https://get.k3s.io` (Rancher's official installer) |
| Licence | Apache-2.0 |
| Download | installer ~40 KB, K3s binary ~60 MB, images ~250 MB |
| Installs | `/usr/local/bin/k3s`, a `k3s` systemd unit, `/etc/rancher/k3s/` |

```bash
curl -sfL https://get.k3s.io -o /tmp/k3s-install.sh
sha256sum /tmp/k3s-install.sh
head -5 /tmp/k3s-install.sh
```

Return that checksum **before running anything**, so the script that ran is on
the record.

## D. Establish protection, then start the cluster

Two paths. **D-adapt** is what was run here and applies whenever K3s already
exists at the pinned version. **D-fresh** applies to a clean host.

Either way the ordering is the same and is the point: the settings are staged,
the guard is established, and only then does a listener exist.

### D-adapt — an existing K3s at the pinned version

Version must match before anything else:

```bash
sudo k3s --version | head -1        # must read v1.36.4+k3s1
```

**A different version stops here.** Adapting across versions is not covered;
uninstall and use D-fresh instead.

Stage the settings. This changes nothing until K3s restarts:

```bash
sudo tee /etc/rancher/k3s/config.yaml >/dev/null <<'EOF'
disable:
  - traefik
  - servicelb
write-kubeconfig-mode: "0640"
kube-proxy-arg:
  - "nodeport-addresses=127.0.0.1/32"
EOF
sudo cat /etc/rancher/k3s/config.yaml
```

`nodeport-addresses=127.0.0.1/32` is what restricts NodePort 30443. An `INPUT`
rule cannot: that traffic is DNATed and forwarded, never traversing `INPUT`
([iptables proxy mode](https://kubernetes.io/docs/reference/networking/virtual-ips/#iptables-proxy-mode)).

Then install the guard and restart — the shared step below.

### D-fresh — a clean host

Install **without enabling or starting**, so no listener exists before its
restriction ([installer options](https://docs.k3s.io/reference/env-variables)):

```bash
INSTALL_K3S_VERSION=v1.36.4+k3s1 \
INSTALL_K3S_SKIP_ENABLE=true \
INSTALL_K3S_SKIP_START=true \
  sh /tmp/k3s-install.sh \
    --disable traefik --disable servicelb \
    --write-kubeconfig-mode 640 \
    --kube-proxy-arg=nodeport-addresses=127.0.0.1/32
systemctl is-active k3s || echo "not started — correct at this point"
```

### Both paths — install the guard, then start

The guard covers **6443 and 10250, on IPv4 and IPv6**. The API stays reachable
by cluster components: loopback, the Pod CIDR and the Service CIDR are allowed,
and only the LAN interface is dropped. The Pod CIDR allowance is what keeps
`metrics-server` able to scrape the kubelet.

```bash
sudo install -D -m 0755 deploy/k3s/host/aegisforge-guard.sh \
  /usr/local/lib/aegisforge/aegisforge-guard.sh
sudo install -m 0644 deploy/k3s/host/aegisforge-cluster-guard.service \
  /etc/systemd/system/
sudo install -D -m 0644 deploy/k3s/host/k3s-requires-guard.conf \
  /etc/systemd/system/k3s.service.d/aegisforge.conf
sudo systemctl daemon-reload
sudo systemctl enable --now aegisforge-cluster-guard.service
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
```

Expect **twelve** rules: eight IPv4 (four per port) and four IPv6 (two per
port). The drop-in makes `k3s.service` **require** the guard, so a failure to
establish protection prevents the cluster starting.

Now start it — `restart` on the adapt path, `enable --now` on the fresh one:

```bash
sudo systemctl restart k3s          # D-adapt
# sudo systemctl enable --now k3s   # D-fresh
sudo systemctl is-active aegisforge-cluster-guard k3s
sudo k3s kubectl get nodes -o wide
```

**If k3s fails to start, stop and return the logs.** There is no fallback that
removes the API restriction — starting unprotected is not an option.

**Verify the rules survived the start.** K3s rebuilds large parts of the
firewall for its own networking, so presence beforehand proves nothing:

```bash
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
sudo k3s kubectl get pods -A          # traefik and svclb must be gone
sudo k3s kubectl -n kube-system get deploy metrics-server
```

On the adapt path a `helm-delete-traefik` job runs for a minute or two; the
`traefik` Service disappears when it finishes. `metrics-server` must stay
`READY 1/1` — it scrapes the kubelet on 10250 from a Pod, which is the path the
guard's Pod-CIDR allowance exists to keep open.

Then, from the **Mac**:

```zsh
nc -w 5 -vz <ubuntu-lan-ip> 6443
nc -w 5 -vz <ubuntu-lan-ip> 10250
```

**Both must time out**, not refuse: a `DROP` is silent, so a refusal would mean
the packet reached a closed port rather than the guard.

**Untested here:** the 10250 and IPv6 rules were added after the recorded Mac
denial, which exercised IPv4 6443 only. Confirm both above before treating
either as proven.

## E. Verify cluster networking

```bash
sudo k3s kubectl -n kube-system get pods -l k8s-app=kube-dns
sudo k3s kubectl -n kube-system rollout status deploy/coredns --timeout=120s
```

DNS resolution and API reachability **from inside a Pod** — the paths the guard
could plausibly have broken:

```bash
sudo k3s kubectl apply -f deploy/k3s/checks/pod-network-check.yaml
sudo k3s kubectl -n aegisforge wait --for=jsonpath='{.status.phase}'=Succeeded \
  pod/netcheck-pod-network --timeout=90s
sudo k3s kubectl -n aegisforge logs netcheck-pod-network
sudo k3s kubectl -n aegisforge get pod netcheck-pod-network \
  -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}{"\n"}'
sudo k3s kubectl -n aegisforge delete pod netcheck-pod-network
```

**Expect `RESULT=pod-to-api-ok` and exit code 0.** `RESULT=api-timeout-or-blocked`
points at the cluster guard. Capture the logs and exit code **before** deleting
the Pod.

This check needs the `aegisforge` namespace, so run it after the namespace is
created in step F if it does not exist yet.

## F. Import the image, credentials and manifests

The Deployment references the image **by digest** with `imagePullPolicy: Never`,
so containerd must hold that exact name. The archive imports under a *tag*
(`docker.io/library/aegisforge-worker:c04`), and containerd resolves by name,
so the digest reference has to be created explicitly:

```bash
DIGEST=sha256:a1eb434c91ff5e51a095ccbdc5becd10e98a099a281302ef68e86b531543a295
REF=docker.io/library/aegisforge-worker@$DIGEST

sudo k3s ctr images import /home/prachi/.aegisforge/artifacts/c04/worker.tar
sudo k3s ctr images ls | grep aegisforge-worker
```

The digest in that output must match step B. Then create the reference the
Deployment asks for, and **assert it exists** — the assertion is the evidence,
not the command that preceded it:

```bash
TAG=$(sudo k3s ctr images ls -q | grep '^docker.io/library/aegisforge-worker:' | head -1) &&
  echo "source tag: $TAG" &&
  { sudo k3s ctr images tag "$TAG" "$REF" 2>/dev/null || echo "(reference already present)"; } &&
  sudo k3s ctr images ls -q | grep -Fx "$REF" &&
  echo "OK: the Deployment's exact reference exists" ||
  echo "STOP: $REF is absent — the Pod cannot start; do not run the next block"
```

**If that prints `STOP`, stop.** `imagePullPolicy: Never` means there is no
fallback: the Pod will sit in `ErrImageNeverPull` indefinitely.

Do not substitute `ctr images import --digests` for the explicit tag. That flag
names digest images from a base-name prefix — `import-<date>@sha256:…` by
default — not from the archive's own reference, so it does not produce the name
required here
([import implementation](https://github.com/containerd/containerd/blob/main/cmd/ctr/commands/images/import.go)).
If it was run, remove the stray image:

```bash
sudo k3s ctr images ls -q | grep '^import-' || echo "(none)"
# sudo k3s ctr images rm <the import-… name>
```

Then the namespace and credentials — **existing Secrets are reused, never
silently rotated**:

```bash
sudo k3s kubectl apply -f deploy/k3s/00-namespace.yaml

sudo k3s kubectl -n aegisforge get secret worker-credential >/dev/null 2>&1 \
  && echo "worker-credential exists — reusing" \
  || sudo k3s kubectl -n aegisforge create secret generic worker-credential \
       --from-literal=token="$(openssl rand -hex 32)" \
       --from-literal=node-id="$(cat /proc/sys/kernel/random/uuid)"

sudo k3s kubectl -n aegisforge get secret redis-credential >/dev/null 2>&1 \
  && echo "redis-credential exists — reusing" \
  || sudo k3s kubectl -n aegisforge create secret generic redis-credential \
       --from-literal=password="$(openssl rand -hex 32)"

sudo k3s kubectl -n aegisforge get secret
```

Return the Secret **table only** — names, types, ages. Never the values.

Validate before applying, then apply:

```bash
sudo k3s kubectl apply --dry-run=server -f deploy/k3s/10-redis.yaml -f deploy/k3s/20-worker.yaml
sudo k3s kubectl apply -f deploy/k3s/10-redis.yaml -f deploy/k3s/20-worker.yaml
```

If the worker was already applied before the digest reference existed, restart
it so the image is resolved again:

```bash
sudo k3s kubectl -n aegisforge delete pod -l app=aegisforge-worker
sudo k3s kubectl -n aegisforge get pods -o wide
```

## G. Workload readiness and both isolation cases

```bash
sudo k3s kubectl -n aegisforge rollout status deploy/redis --timeout=180s
sudo k3s kubectl -n aegisforge rollout status deploy/aegisforge-worker --timeout=180s
sudo k3s kubectl -n aegisforge get pods,svc,networkpolicy,endpoints -o wide
```

Check the worker Service's endpoints list **only** the worker Pod.

Worker reachable from the host, now that its Service exists:

```bash
TOKEN=$(sudo k3s kubectl -n aegisforge get secret worker-credential \
  -o jsonpath='{.data.token}' | base64 -d)
curl -s -H "Authorization: Bearer $TOKEN" -H "X-AegisForge-Contract: 1.0" \
  http://127.0.0.1:30443/v1/health
echo
```

Expect a `Node` record. `"capabilities": []` is correct — the API answers, but
the worker cannot accept jobs while its routes are fail-closed. **Do not treat
`ss` output alone as proof of exposure, and do not expect a NodePort listener
before the Service exists.**

**Allowed first, and this is a gate, not an ordering preference.** The denied
probe only shows that *one* Pod could not reach Redis, which is equally
consistent with a stopped Redis, a wrong Secret or a broken Service. It becomes
evidence of isolation only after the allowed probe has proven that the same
Service name and the same mounted credential do work. **If the allowed probe
does not exit 0, stop and report — do not run the denied half.**

```bash
sudo k3s kubectl apply -f deploy/k3s/checks/netpolicy-allowed.yaml
sudo k3s kubectl -n aegisforge wait --for=jsonpath='{.status.phase}'=Succeeded \
  pod/netcheck-allowed --timeout=90s
sudo k3s kubectl -n aegisforge logs netcheck-allowed
sudo k3s kubectl -n aegisforge get pod netcheck-allowed \
  -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}{"\n"}'
sudo k3s kubectl -n aegisforge delete pod netcheck-allowed
```

**Expect `RESULT=allowed-reached-redis` and exit code 0.**

**Then denied:**

```bash
sudo k3s kubectl apply -f deploy/k3s/checks/netpolicy-denied.yaml
sudo k3s kubectl -n aegisforge wait --for=jsonpath='{.status.phase}'=Failed \
  pod/netcheck-denied --timeout=90s || \
sudo k3s kubectl -n aegisforge wait --for=jsonpath='{.status.phase}'=Succeeded \
  pod/netcheck-denied --timeout=30s
sudo k3s kubectl -n aegisforge logs netcheck-denied
sudo k3s kubectl -n aegisforge get pod netcheck-denied \
  -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}{"\n"}'
sudo k3s kubectl -n aegisforge delete pod netcheck-denied
```

**Expect `RESULT=blocked-by-policy` and exit code 7.** A NetworkPolicy may be
enforced by dropping the packet or by rejecting it, and **both are the policy
working**:

| Observed | Meaning | Reported as |
|---|---|---|
| the client hangs, `timeout` exits 124 | the packet is dropped | `RESULT=blocked-by-policy (timeout exit 124)`, exit 7 |
| immediate `Connection refused` | the packet is rejected | `RESULT=blocked-by-policy (connection refused: …)`, exit 7 |

Match on the `RESULT=blocked-by-policy` prefix; the parenthesised mechanism is
detail. **A fast refusal is not a failure here** — K3s's default kube-router
enforces NetworkPolicy by rejecting rather than dropping, so an immediate
refusal is the expected result on this cluster.

`RESULT=POLICY-NOT-ENFORCED` (exit 1) means the policy is not applied —
**report immediately**; every later isolation claim depends on it. Every other
result — `dns-failed`, `credential-unreadable`, `credential-empty`,
`auth-failed`, `redis-protected-mode`, `tooling-missing`, `empty-output`,
`other` — is a failure, not a denial: each means the probe never reached the
network, so it says nothing about isolation either way.

Capture the logs and exit code **before** deleting either Pod. A Pod that never
starts is an admission problem, not a network one — send `kubectl describe pod`
for that case.

**Observed on the Ubuntu worker.** Redis and worker Deployments rolled out; the
Redis Service had the live endpoint `10.42.0.28:6379`; the allowed probe
returned `RESULT=allowed-reached-redis`, exit 0; the denied probe returned
`Connection refused` immediately, exit 9 under the previous wording. Isolation
had in fact worked: `iptables-save` showed the kube-router chain for the Redis
Pod ending in `REJECT --reject-with icmp-port-unreachable`, an explicit
rejection rule. The probe, not the cluster, was wrong; it is corrected above.
The rule's displayed packet counter read zero, and **that counter is not
evidence about the denied attempt** — it was not sampled around that connection,
so nothing here rests on it. The refusal itself, paired with the allowed probe's
`PONG` over the same Service and credential, is the evidence.

## H. Protected runtime proxy and bounded Pod inference

**Ollama keeps its loopback listener.** A `systemd-socket-proxyd` forwarder
listens on the CNI bridge instead. Its guard must be in place first, and the
socket **requires** the guard, so the listener cannot exist unprotected.

**Access boundary, stated plainly:** allowing the Pod CIDR allows **every Pod on
this node**, not the worker alone. NetworkPolicy does not govern a Pod's
connection to its own node
([documented limitation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)),
so `30-runtime-egress.yaml` restricts the worker's *egress intent* but does not
make the runtime worker-exclusive.

Establish the two values first, in a block of its own. The install commands are
deliberately **not** in this block: an earlier version printed `STOP` and then
carried straight on to install with empty values.

```bash
BRIDGE=$(ip -4 -o addr show cni0 | awk '{split($4,a,"/"); print a[1]}')
PROXY=$(ls /usr/lib/systemd/systemd-socket-proxyd /lib/systemd/systemd-socket-proxyd 2>/dev/null | head -1)
[ -n "$BRIDGE" ] && [ -n "$PROXY" ] \
  && echo "OK bridge=$BRIDGE proxy=$PROXY" \
  || echo "STOP: bridge or proxy missing — do not run the next block"
```

**Only if that printed `OK`**, and in the same shell so `$BRIDGE` and `$PROXY`
survive:

```bash
sudo install -m 0644 deploy/k3s/host/aegisforge-ollama-guard.service /etc/systemd/system/
sed "s|BRIDGE_ADDRESS|$BRIDGE|" deploy/k3s/host/aegisforge-ollama-proxy.socket \
  | sudo tee /etc/systemd/system/aegisforge-ollama-proxy.socket >/dev/null
sed "s|SOCKET_PROXY_PATH|$PROXY|" deploy/k3s/host/aegisforge-ollama-proxy.service \
  | sudo tee /etc/systemd/system/aegisforge-ollama-proxy.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now aegisforge-ollama-guard.service
sudo systemctl enable --now aegisforge-ollama-proxy.socket
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
sudo ss -ltnp 'sport = :11434'
```

**Expect two listeners: `127.0.0.1:11434` (Ollama, untouched) and
`$BRIDGE:11434` (the forwarder).** If the loopback listener is gone, something
rebound Ollama — stop and report.

Confirm the original listener still serves local clients:

```bash
curl -s --max-time 5 http://127.0.0.1:11434/api/version; echo
```

If the bridge is not `10.42.0.1`, edit the `/32` in
`deploy/k3s/30-runtime-egress.yaml` to match before applying:

```bash
sudo k3s kubectl -n aegisforge set env deploy/aegisforge-worker \
  AEGIS_RUNTIME_HOST="http://${BRIDGE}:11434"
sudo k3s kubectl apply -f deploy/k3s/30-runtime-egress.yaml
sudo k3s kubectl -n aegisforge rollout status deploy/aegisforge-worker --timeout=180s
sh deploy/k3s/checks/inference-in-pod.sh
echo "inference exit status: $?"
```

**Expect a JSON block and `PASS: bounded inference completed normally`, exit 0.**
It fails on an empty, wrong or truncated answer, a `done_reason` other than
`stop`, missing token counts, or its own deadline — enforced by `SIGALRM`, which
interrupts a blocked read.

Access from outside the permitted boundary must fail. From the **Mac**:

```zsh
nc -z -w 3 <ubuntu-lan-ip> 11434 && echo "REACHABLE — report this" || echo "closed, as intended"
```

## I. Mac connection denials and coordinator persistence

From the **macOS coordinator**, zsh:

```zsh
nc -z -w 3 <ubuntu-lan-ip> 30443 && echo "REACHABLE — report this" || echo "closed, as intended"
nc -z -w 3 <ubuntu-lan-ip> 6443  && echo "REACHABLE — report this" || echo "closed, as intended"
```

Both must be closed: the worker speaks plain HTTP and pinned TLS is OD-06 work.

Then coordinator metadata, using the real `meta(key, value)` schema:

```zsh
cd /Users/adityatadge/Documents/GitHub/AegisForge
PYTHONPATH=. ./.venv/bin/python -m backend.coordinator
```

Send one request in the browser, then in a second terminal:

```zsh
sqlite3 ~/.aegisforge/coordinator.sqlite3 \
  "SELECT value FROM meta WHERE key='contract_version';
   SELECT state, node_id, route_reason, runtime_ms IS NOT NULL FROM attempts
     ORDER BY created_at DESC LIMIT 1;
   SELECT COUNT(*) FROM events WHERE job_id=(SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT 1);"
```

Expect `1.0` — matching the worker's `supported_contract_versions` from step G —
an attempt with a node id, route reason and recorded runtime, and a non-zero
event count. **Ctrl+C, restart, and run the query again**: the same rows must
still be there. That is persistence, not a cache.

## J. Confirm the existing host services

```bash
sudo ss -ltnp 'sport = :8080'
sudo systemctl is-active jenkins
docker ps --format '{{.Names}}' | wc -l
env -u DOCKER_HOST -u DOCKER_CONTEXT \
  docker --host unix:///var/run/docker.sock info --format 'Server={{.ServerVersion}}'
curl -s --max-time 5 http://127.0.0.1:11434/api/version; echo
sudo systemctl show ollama -p FragmentPath -p DropInPaths
```

Jenkins active on 8080, the Docker container count unchanged from step A, and
Ollama answering on loopback with **no AegisForge drop-in** among its paths.

Restart resilience:

```bash
sudo systemctl restart k3s
sleep 20
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
sudo k3s kubectl get nodes
```

The guard rules must still be present after the restart.

## K. Return evidence, and rollback only if needed

Return, concisely: the A preflight (including the `ExecStart` line if K3s was
already installed), the B digests, the C checksum **only if the installer was
downloaded**, the D guard status plus the Mac denials for 6443 **and** 10250,
the E `RESULT=` line, the F digest-reference assertion and Secret list, the G
readiness plus **both** isolation `RESULT=` lines with exit codes, the H
listeners and inference JSON with its exit status, the I closed-port and
coordinator results, and the J service checks. **No tokens or passwords.**

### Rollback

Scoped, in reverse order — stop listeners before removing protection, and touch
only AegisForge-owned units, rules and objects.

**Which cluster you are rolling back matters.** On this host K3s predates C05,
so disabling it would remove something that was not ours to remove. Take the
branch that matches how step D was run.

Common to both — the workloads and the runtime proxy:

```bash
sudo systemctl disable --now aegisforge-ollama-proxy.socket aegisforge-ollama-proxy.service
sudo systemctl disable --now aegisforge-ollama-guard.service
sudo rm -f /etc/systemd/system/aegisforge-ollama-proxy.{socket,service} \
           /etc/systemd/system/aegisforge-ollama-guard.service
sudo k3s kubectl delete -f deploy/k3s/30-runtime-egress.yaml \
  -f deploy/k3s/20-worker.yaml -f deploy/k3s/10-redis.yaml
sudo k3s kubectl delete namespace aegisforge
```

**If step D was D-adapt** — leave the cluster running, and return its settings
to what they were:

```bash
sudo rm -f /etc/rancher/k3s/config.yaml
sudo rm -f /etc/systemd/system/k3s.service.d/aegisforge.conf
sudo systemctl daemon-reload
sudo systemctl restart k3s
sudo systemctl disable --now aegisforge-cluster-guard.service
sudo rm -f /etc/systemd/system/aegisforge-cluster-guard.service
sudo systemctl daemon-reload
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
```

The guard is disabled **after** the drop-in is removed and K3s has restarted
without it; disabling it first would take K3s down with it, since the drop-in
makes K3s require it. Removing `config.yaml` restores Traefik and ServiceLB,
which is the state the host was found in.

**If step D was D-fresh** — the cluster was ours, so it goes:

```bash
sudo systemctl disable --now k3s
sudo systemctl disable --now aegisforge-cluster-guard.service
sudo rm -f /etc/systemd/system/aegisforge-cluster-guard.service \
           /etc/systemd/system/k3s.service.d/aegisforge.conf
sudo systemctl daemon-reload
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
```

To remove K3s entirely: `sudo /usr/local/bin/k3s-uninstall.sh`. **Do not run
this on the adapt path** — it deletes a cluster that predates C05.

The guards delete only their own tagged rules, on both address families, and
never flush a chain. Ollama's configuration is never modified, so there is
nothing to revert there — **do not run `systemctl revert ollama`**, which would
discard pre-existing drop-ins.
