# C05 — Ubuntu cluster deployment handoff

**Device role:** Ubuntu worker. **OS:** Ubuntu 24.04.4 LTS, x86_64.
**Shell:** bash. **Directory:** `/home/prachi/SIH/AegisForge`.

One ordered sequence, **A** to **K**. Every step is a host change and stays at
this checkpoint. Nothing here has been executed.

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
are 6443 and 10250; the worker uses NodePort 30443, restricted to loopback by
kube-proxy. **Nothing touches 8080.** K3s uses its own containerd, so Docker's
28 images and 26 containers are untouched, and Ollama's configuration is never
modified.

---

## A. Read-only preflight

```bash
cd /home/prachi/SIH/AegisForge
git status --short --branch
git rev-parse --short HEAD

for tool in iptables ip ss curl python3 sha256sum timeout openssl systemd-socket-proxyd; do
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
`iptables` or `systemd-socket-proxyd` is missing** — the guards depend on both.

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

## C. Obtain the installer

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

`--kube-proxy-arg=nodeport-addresses=127.0.0.1/32` is what restricts NodePort
30443. An `INPUT` rule cannot: that traffic is DNATed and forwarded, never
traversing `INPUT`
([iptables proxy mode](https://kubernetes.io/docs/reference/networking/virtual-ips/#iptables-proxy-mode)).

Install the guard, which protects the API listener. **The API stays reachable
by cluster components** — only the LAN interface is dropped:

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

The drop-in makes `k3s.service` **require** the guard, so a failure to establish
protection prevents the cluster starting. Now start it:

```bash
sudo systemctl enable --now k3s
sudo systemctl is-active aegisforge-cluster-guard k3s
sudo k3s kubectl get nodes -o wide
```

**If k3s fails to start, stop and return the logs.** There is no fallback that
removes the API restriction — starting unprotected is not an option.

## E. Verify cluster networking

```bash
sudo k3s kubectl -n kube-system get pods -l k8s-app=kube-dns
sudo k3s kubectl -n kube-system rollout status deploy/coredns --timeout=120s
```

DNS resolution and API reachability **from inside a Pod**:

```bash
sudo k3s kubectl run netprobe --rm -i --restart=Never \
  --image=redis@sha256:e17e3a1993da428251cbd88dbdb3de8c8d4007f840d7350eb17a2d8695fa705f \
  --overrides='{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":10002,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"netprobe","image":"redis@sha256:e17e3a1993da428251cbd88dbdb3de8c8d4007f840d7350eb17a2d8695fa705f","command":["sh","-c","getent hosts kubernetes.default.svc.cluster.local && timeout 5 sh -c \"echo > /dev/tcp/kubernetes.default.svc.cluster.local/443\" && echo RESULT=pod-to-api-ok || echo RESULT=pod-networking-failed"],"securityContext":{"allowPrivilegeEscalation":false,"readOnlyRootFilesystem":true,"capabilities":{"drop":["ALL"]}}}]}}' \
  -- sh -c true
```

**Expect `RESULT=pod-to-api-ok`.** This proves DNS and that a Pod reaches the
API through its Service — which the LAN guard must not have broken.

## F. Import the image, credentials and manifests

```bash
sudo k3s ctr images import /home/prachi/.aegisforge/artifacts/c04/worker.tar
sudo k3s ctr images ls | grep aegisforge-worker
```

The digest must match step B. Then the namespace and credentials — **existing
Secrets are reused, never silently rotated**:

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

Validate before applying, then apply:

```bash
sudo k3s kubectl apply --dry-run=server -f deploy/k3s/10-redis.yaml -f deploy/k3s/20-worker.yaml
sudo k3s kubectl apply -f deploy/k3s/10-redis.yaml -f deploy/k3s/20-worker.yaml
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

**Allowed first.** A denial means nothing until the allowed path is proven:

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

**Expect `RESULT=timeout-or-blocked` and exit code 7.** `RESULT=POLICY-NOT-ENFORCED`
means the policy is not applied — **report immediately**; every later isolation
claim depends on it. Capture the logs and exit code **before** deleting either
Pod. A Pod that never starts is an admission problem, not a network one — send
`kubectl describe pod` for that case.

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

```bash
BRIDGE=$(ip -4 -o addr show cni0 | awk '{split($4,a,"/"); print a[1]}')
PROXY=$(ls /usr/lib/systemd/systemd-socket-proxyd /lib/systemd/systemd-socket-proxyd 2>/dev/null | head -1)
[ -n "$BRIDGE" ] && [ -n "$PROXY" ] && echo "bridge=$BRIDGE proxy=$PROXY" || echo "STOP: bridge or proxy missing"

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

Return, concisely: the A preflight, the C checksum, the B digests, the D start
and guard status, the E `RESULT=` line, the F import digest and Secret list, the
G readiness plus **both** isolation `RESULT=` lines with exit codes, the H
listeners and inference JSON with its exit status, the I closed-port and
coordinator results, and the J service checks. **No tokens or passwords.**

Scoped rollback, in reverse order — stop listeners before removing protection,
and touch only AegisForge-owned units and rules:

```bash
sudo systemctl disable --now aegisforge-ollama-proxy.socket aegisforge-ollama-proxy.service
sudo systemctl disable --now aegisforge-ollama-guard.service
sudo rm -f /etc/systemd/system/aegisforge-ollama-proxy.{socket,service} \
           /etc/systemd/system/aegisforge-ollama-guard.service
sudo k3s kubectl delete -f deploy/k3s/30-runtime-egress.yaml \
  -f deploy/k3s/20-worker.yaml -f deploy/k3s/10-redis.yaml
sudo k3s kubectl delete namespace aegisforge
sudo systemctl disable --now k3s
sudo systemctl disable --now aegisforge-cluster-guard.service
sudo rm -f /etc/systemd/system/aegisforge-cluster-guard.service \
           /etc/systemd/system/k3s.service.d/aegisforge.conf
sudo systemctl daemon-reload
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
```

To remove K3s entirely: `sudo /usr/local/bin/k3s-uninstall.sh`.

The guards delete only their own tagged rules and never flush a chain. Ollama's
configuration is never modified, so there is nothing to revert there — **do not
run `systemctl revert ollama`**, which would discard pre-existing drop-ins.
