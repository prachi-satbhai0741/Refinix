# C06 — distributed execution handoff

**Devices:** `macOS coordinator` (Apple silicon, zsh) and `Ubuntu worker`
(x86_64, bash). Repository directory: `~/Documents/GitHub/AegisForge` on the
Mac; whatever path the Ubuntu worker already uses for C05.

**Nothing in this document has been run.** The code is implemented and covered
by offline checks with fakes; a live worker, a real TLS handshake, the Keychain,
Redis and a dispatched inference are all device gates. Section K says exactly
what is and is not proven.

---

## The order, and why it is this order

Each step needs something the step before it produces. The two dependencies
that fix the sequence are worth stating up front, because getting them wrong
looks like a working system that quietly cannot pair.

* **The executor cannot be deployed before pairing.** It serves one
  relationship, and that relationship ID is minted by the coordinator when the
  Mac pairs. Deploying it earlier means patching the Secret with an ID nobody
  has yet.
* **Pairing cannot happen before the Mac can reach 30443.** The pairing code is
  presented *over the already-pinned channel*, so the channel has to exist.

```
A  addresses          both      find the two LAN addresses
B  TLS identity       Ubuntu    generate the certificate, read the fingerprint
C  image              Ubuntu    build C06, record the digest, pin both manifests
D  worker API         Ubuntu    deploy the API alone; prove TLS on loopback
E  LAN forwarder      Ubuntu    open 30443 to the one Mac address
F  pair               macOS     confirm the fingerprint, redeem the code
G  relationship ID    both      read it on the Mac, patch the Secret on Ubuntu
H  executor           Ubuntu    deploy the consumer
I  acceptance         both      five checks
```

---

## What changed, in one paragraph

The worker's job routes were fail-closed because two things did not exist. Both
now do: OD-06 pairing issues a per-relationship credential the worker stores
only as a salted hash, and `POST /v1/jobs` commits the validated envelope to a
Redis Stream — atomically, with its receipt — before it answers 202. An
executor Pod, the same image with a different command, consumes that stream and
writes its events back for replay. The Mac pins the worker's certificate as its
sole trust anchor, routes chat to it when it is paired and healthy, and falls
back locally with a visible reason only when it is certain the worker never took
the work.

---

## A. Both devices — find the two LAN addresses

Step E permits exactly one address. Determine both now and use the real values.

**Ubuntu worker:**

```bash
ip -4 addr show scope global | awk '/inet /{print $2, $NF}'
```

**macOS coordinator:**

```bash
ipconfig getifaddr en0 || ipconfig getifaddr en1
```

**Return both.** If the Mac's address comes from DHCP, reserve it on the router
first — a rule pinned to an address that changes tomorrow fails closed, which is
safe but confusing.

Throughout this document, `WORKER_IP` is the Ubuntu address and `MAC_IP` is the
Mac address.

---

## B. Ubuntu worker — generate the worker's identity

The private key never leaves this host and is never committed.

```bash
sudo mkdir -p /etc/aegisforge/tls && sudo chmod 700 /etc/aegisforge/tls
sudo openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout /etc/aegisforge/tls/tls.key \
  -out /etc/aegisforge/tls/tls.crt \
  -subj "/CN=aegisforge-worker" \
  -addext "subjectAltName=IP:WORKER_IP"
sudo chmod 600 /etc/aegisforge/tls/tls.key
sudo chmod 644 /etc/aegisforge/tls/tls.crt
```

Read the fingerprint. **This is the value a human carries to the Mac.**

```bash
sudo openssl x509 -in /etc/aegisforge/tls/tls.crt -noout -fingerprint -sha256
```

**Expected:** one line, `sha256 Fingerprint=AB:CD:…`, 32 colon-separated pairs.

Write it down or read it aloud. Do not email it, paste it into a chat, or copy
it through a shared clipboard — the out-of-band step is the entire security
argument, and a fingerprint that travelled the same path as the connection
proves nothing about the connection.

Print the certificate for the Mac (public half only; safe to copy):

```bash
sudo cat /etc/aegisforge/tls/tls.crt
```

**Rollback:** `sudo rm -rf /etc/aegisforge/tls`. The worker then fails to start
until a certificate exists, which is the correct closed state.

---

## C. Ubuntu worker — build the C06 image and pin it

C05's image contains none of this code. A new build is required.

```bash
cd <repository>
sudo docker build --pull=false -f backend/worker-image/Dockerfile \
  -t aegisforge-worker:c06 .
```

The build runs the offline suites under `--network=none`, including
`backend.worker.test_worker_app` and `backend.worker.test_executor`. **A failing
build is a real failure.** Do not skip the test stage to get past it — that
stage is the only place the FastAPI-dependent worker tests run at all.

```bash
sudo docker image inspect aegisforge-worker:c06 --format '{{.Id}}'
sudo docker save aegisforge-worker:c06 | sudo k3s ctr images import -
sudo k3s ctr images ls | grep aegisforge-worker
```

**Return the image ID (`sha256:…`) exactly as printed.**

**Do not invent this value.** Both manifests carry a placeholder pinned to the
C04 digest and say so in a comment:

- `deploy/k3s/20-worker.yaml`
- `deploy/k3s/40-executor.yaml`

Update **both**, and `backend/worker-image/provenance.json`. A manifest applied
with the C04 digest starts a worker with none of this code and looks like it
worked.

---

## D. Ubuntu worker — deploy the worker API only, and prove TLS

The executor is **not** applied yet; it has no relationship to serve until
step G.

```bash
sudo k3s kubectl -n aegisforge create secret tls worker-tls \
  --cert=/etc/aegisforge/tls/tls.crt --key=/etc/aegisforge/tls/tls.key

cd <repository>
sudo k3s kubectl apply -f deploy/k3s/20-worker.yaml
sudo k3s kubectl -n aegisforge rollout status deploy/aegisforge-worker --timeout=300s
sudo k3s kubectl -n aegisforge get pods,pvc -o wide
```

**Expected:** the worker Deployment Ready and the `worker-state` PVC `Bound`.
The PVC matters: the pairing hashes live on it, and on an `emptyDir` every Pod
restart would silently unpair the Mac.

**Confirm the NodePort is still loopback-only.** It must stay that way: NodePort
traffic is DNATed and forwarded, so it never traverses `INPUT` and **iptables
cannot restrict it**. The LAN forwarder in step E is what makes the port
filterable at all.

```bash
sudo ss -ltn 'sport = :30443'
grep -n 'nodeport-addresses' /etc/rancher/k3s/config.yaml
```

**Expected:** a listener on `127.0.0.1:30443` and nothing else, and
`nodeport-addresses=127.0.0.1/32` unchanged from C05. **If you are ever told to
widen this to a subnet, that instruction is wrong** — an offline check in
`deploy/k3s/host/test_guard.py` fails the repository if this document says
otherwise.

**Prove TLS, from the node itself:**

```bash
TOKEN=$(sudo k3s kubectl -n aegisforge get secret worker-credential \
  -o jsonpath='{.data.token}' | base64 -d)
curl -sS --cacert /etc/aegisforge/tls/tls.crt --resolve WORKER_IP:30443:127.0.0.1 \
  -H "Authorization: Bearer $TOKEN" -H "X-AegisForge-Contract: 1.0" \
  "https://WORKER_IP:30443/v1/health" | head -c 400; echo
```

`--resolve` points the certificate's own name at the loopback listener, so the
pin is verified against the address it was issued for while the port is still
closed to the LAN. **Do not add `-k`** — it disables the verification this step
exists to perform.

**Expected:** a `Node` record. `"capabilities": []` is correct: nothing is
paired, so the worker honestly advertises nothing.

**And plain HTTP must fail:**

```bash
curl -sS -m 5 --resolve WORKER_IP:30443:127.0.0.1 "http://WORKER_IP:30443/v1/health"
echo "exit=$?"
```

**Expected:** non-zero exit or a garbled reply, **not** a JSON record. A JSON
record means TLS did not start, and step E must not be run.

**Rollback:** `sudo k3s kubectl -n aegisforge delete -f deploy/k3s/20-worker.yaml`
and re-apply the committed version from Git.

---

## E. Ubuntu worker — open 30443 to the one Mac address

**Only after step D proved TLS is live on loopback.**

This reuses the C05 pattern exactly: a `systemd-socket-proxyd` listener on the
LAN address, forwarding to the loopback NodePort, with a guard the socket
*requires* so the listener cannot exist unrestricted. The proxy copies bytes and
never terminates TLS, so the pinned session stays end-to-end between the Mac and
the worker Pod and this host holds no key.

```bash
sudo install -m 0755 deploy/k3s/host/aegisforge-guard.sh \
  /usr/local/lib/aegisforge/aegisforge-guard.sh
sudo install -m 0644 deploy/k3s/host/aegisforge-worker-guard.service \
  deploy/k3s/host/aegisforge-worker-proxy.service \
  deploy/k3s/host/aegisforge-worker-proxy.socket /etc/systemd/system/
```

Fill in the two placeholders, exactly as C05 did for the Ollama forwarder:

```bash
sudo sed -i "s|LAN_ADDRESS|WORKER_IP|" \
  /etc/systemd/system/aegisforge-worker-proxy.socket
sudo sed -i "s|SOCKET_PROXY_PATH|$(command -v systemd-socket-proxyd || echo /usr/lib/systemd/systemd-socket-proxyd)|" \
  /etc/systemd/system/aegisforge-worker-proxy.service
```

Name the one permitted address. **The guard refuses to apply without it**, so a
forgotten value leaves the port closed rather than open to the LAN:

```bash
sudo systemctl edit --force aegisforge-worker-guard.service
# [Service]
# Environment=AEGIS_MAC_ADDRESS=MAC_IP
sudo systemctl daemon-reload
sudo systemctl enable --now aegisforge-worker-guard.service
sudo systemctl enable --now aegisforge-worker-proxy.socket
```

The unit runs `aegisforge-guard.sh apply worker`, which is also the command to
re-apply by hand if the rules are ever removed manually:

```bash
sudo AEGIS_MAC_ADDRESS=MAC_IP \
  /usr/local/lib/aegisforge/aegisforge-guard.sh apply worker
```

**Verify:**

```bash
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
sudo ss -ltn 'sport = :30443'
```

**Expected:** two IPv4 rules tagged `aegisforge-c06-worker` — an `ACCEPT` from
`MAC_IP/32` above a `DROP` — one IPv6 `DROP`, and listeners on both
`127.0.0.1:30443` and `WORKER_IP:30443`.

**From the Mac:**

```bash
curl -sS --cacert /path/to/tls.crt -H "X-AegisForge-Contract: 1.0" \
  "https://WORKER_IP:30443/v1/health" -o /dev/null -w '%{http_code}\n'
```

**Expected:** `401` — reached, TLS verified, and correctly refusing an
unauthenticated caller. That is a success.

**From a third machine on the LAN:**

```bash
nc -w 5 -vz WORKER_IP 30443
```

**Expected:** refused or timed out.

**Confirm nothing else moved:**

```bash
sudo ss -ltnp | grep -E ':(8080|11434|6443|10250)\b'
systemctl is-active jenkins docker ollama
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
```

**Expected:** Jenkins on 8080, Ollama loopback-only, Docker unchanged,
6443/10250 still closed to the LAN, and the C05 rules still present.

**Rollback, scoped:**

```bash
sudo systemctl disable --now aegisforge-worker-proxy.socket \
                             aegisforge-worker-proxy.service \
                             aegisforge-worker-guard.service
sudo rm -f /etc/systemd/system/aegisforge-worker-*.service \
           /etc/systemd/system/aegisforge-worker-proxy.socket
sudo systemctl daemon-reload
sudo /usr/local/lib/aegisforge/aegisforge-guard.sh status
```

The guard's `ExecStop` removes its own tagged rules; `status` should then show
only the C05 tags. `nodeport-addresses` was never changed, so there is nothing
to restore.

---

## F. macOS coordinator — pair

Start Refinix, open the Control Center, and use **Connected computers →
Connect a computer**.

| Field | Where it comes from |
|---|---|
| Worker address and port | `WORKER_IP`, and `30443` |
| Certificate fingerprint | step B — **compare it by eye against the worker screen** |
| Worker certificate (PEM) | step B's `cat` output |
| One-time pairing code | the command below, on the worker |

On the **Ubuntu worker**, mint the code inside the running API Pod:

```bash
POD=$(sudo k3s kubectl -n aegisforge get pod -l component=api -o name | head -1)
sudo k3s kubectl -n aegisforge exec $POD -- python -m backend.worker.pairing_cli code
```

**Expected:** one short code on stdout, and a warning on stderr that it is
single-use and expires in 10 minutes. It is never printed again; re-running
mints a different one.

Press Connect.

**Expected:** the card shows the worker, its health and its model.
`"Waiting requests"` may read *not reported* until the executor exists — that is
honest, not broken.

| What you see | Meaning |
|---|---|
| "the worker's certificate does not match the pinned fingerprint" | You typed a different fingerprint, or you are not talking to that worker. **Stop.** Re-read it on the worker screen before retyping. |
| "this pairing code is unknown, expired or already used" | Mint a fresh one. A presented code is spent even when the rest failed. |
| "Pairing needs the macOS Keychain" | The credential has nowhere legitimate to go, so Refinix refuses rather than writing it to its database. |

**Confirm the credential is where it should be, and nowhere else:**

```bash
security find-generic-password -s "AegisForge worker credential" -g 2>&1 | head -3
sqlite3 ~/Library/Application\ Support/Refinix/refinix.db \
  "SELECT relationship_id, address, fingerprint, state FROM relationships;"
```

**Expected:** a Keychain entry exists; the database row has an address, a
fingerprint and a state, and **no credential column at all**.

**Rollback:** Control Center → Disconnect this computer. That deletes the
Keychain item, marks the row revoked, fences any attempt in flight, and tells
the worker to drop its hash.

---

## G. Both devices — carry the relationship ID to the executor

The ID printed by the query above is what the executor serves. It exists only
now, which is why the executor could not be deployed earlier.

**macOS coordinator:**

```bash
sqlite3 ~/Library/Application\ Support/Refinix/refinix.db \
  "SELECT relationship_id FROM relationships WHERE state='paired'
   ORDER BY paired_at DESC LIMIT 1;"
```

**Ubuntu worker** — paste that exact value:

```bash
sudo k3s kubectl -n aegisforge patch secret worker-credential \
  --type merge -p '{"stringData":{"relationship-id":"<uuid from the Mac>"}}'
sudo k3s kubectl -n aegisforge get secret worker-credential \
  -o jsonpath='{.data.relationship-id}' | base64 -d; echo
```

**Expected:** the same UUID echoed back. A mismatch means the executor will
serve a relationship that does not exist and consume nothing.

---

## H. Ubuntu worker — deploy the executor

```bash
cd <repository>
sudo k3s kubectl apply -f deploy/k3s/40-executor.yaml
sudo k3s kubectl -n aegisforge rollout status deploy/aegisforge-executor --timeout=300s
sudo k3s kubectl -n aegisforge logs deploy/aegisforge-executor --tail=5
```

**Expected:** Ready, and a log line naming the consumer and the relationship it
serves.

**Rollback:** `sudo k3s kubectl -n aegisforge delete -f deploy/k3s/40-executor.yaml`.
Work already queued stays in Redis and is recovered when an executor returns.

---

## I. Both devices — the acceptance exercise

Five checks, in order. Capture the Control Center card and the chat for each.

**I-1. A real distributed answer.** Ask an ordinary Chat question on the Mac.

**Expected:** the reply arrives and the route reason reads
`paired worker …: healthy, qwen3.5:4b-q4_K_M`. Confirm where it ran:

```bash
sudo k3s kubectl -n aegisforge logs deploy/aegisforge-executor --tail=20
```

**I-2. Cancellation.** Ask a long question and press Stop.

**Expected:** the attempt stops, the conversation keeps the partial text, and
the executor log shows it stopping rather than finishing. The cancel travels
Mac → worker API → Redis key → executor.

**I-3. API restart during work.** Start a long request, then:

```bash
sudo k3s kubectl -n aegisforge delete pod -l component=api
```

**Expected:** the reply still completes. The receipt and the events are in
Redis, not in the API process, so a restarted API answers for work it never
admitted. **This is the check that would have failed before this correction.**

**I-4. Worker loss.** While a request is running:

```bash
sudo k3s kubectl -n aegisforge scale deploy/aegisforge-worker --replicas=0
```

**Expected:** the attempt is interrupted with a visible reason, and the
conversation and history stay usable. Restore with `--replicas=1`.

**I-5. Truthful fallback.** With the worker still at zero replicas, ask a new
question.

**Expected:** the answer arrives **from this computer**, and the record says the
paired worker was unavailable. Two attempts exist for that job: the interrupted
remote one and the local one that answered.

**I-6. Redis restart.**

```bash
sudo k3s kubectl -n aegisforge rollout restart deploy/redis
```

**Expected:** in-flight work becomes visibly interrupted; the Mac's history is
complete and unchanged. Redis holds queue position and replay only.

---

## J. What to return

1. The C06 image digest from step C, verbatim.
2. The two LAN addresses from step A.
3. The `ss`, `nodeport-addresses`, TLS and plain-HTTP output from step D.
4. The guard `status`, `ss`, Mac `401`, third-machine and untouched-services
   output from step E.
5. The Keychain and `relationships` output from step F — with the fingerprint,
   **never** the credential or the pairing code.
6. The echoed relationship ID from step G.
7. The six I results with their route reasons.
8. Anything that differed from "Expected", verbatim rather than summarised.

---

## K. What is proven, and what is not

**Verified offline on the macOS coordinator** — see the counts in the change
record — with stateful fakes for Redis, a fake connection for the pin
comparison, and a fake `iptables` with real insert/delete/check semantics for
the guard. That covers: atomic receipt commit, idempotent replay and conflict,
event ordering, resumable replay and expiry, reconnect without duplication,
restart recovery of poll/replay/cancel, capacity derived from Redis, atomic
owner-checked leases, duplicate suppression after a completed run, pending-work
recovery, cancellation, revocation fencing, route selection and its reasons,
refusal versus receipt-unknown, manifest security contexts, the worker guard's
accept/drop ordering, and the C07 fixtures.

**Not proven by any of that:** a real TLS handshake, the macOS Keychain, a live
Redis, a real Kubernetes deployment, `systemd-socket-proxyd` behaviour, a
dispatched model response, cancellation latency, or real firewall behaviour.
Those are what steps A–I establish. Until the requester reports them, **C06 is
implemented and unverified.**

**Also out of scope here:** Documents and Code are not dispatched. The worker
advertises `text.generate` only, and the coordinator keeps document and code
skills local — those are C08 and C09.
