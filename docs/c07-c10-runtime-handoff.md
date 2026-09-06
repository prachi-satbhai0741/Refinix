# C07–C10 runtime handoff — the ordered human steps

**Devices:** `macOS coordinator` (Apple silicon, zsh, repository at
`~/Documents/GitHub/AegisForge`) and `Ubuntu worker` (x86_64, bash, whatever
path C05 already uses).

**Nothing in this document has been run.** Source for C08, C09 and C10 is
implemented and covered by offline checks with fakes. A live worker, a real
pairing, a real dispatch, a real Kubernetes Job and a real scan reading are all
device gates. Section J states exactly what is and is not proven.

**C06 is not accepted.** Setup stopped before C06 step E. This document
continues from there and then adds C07–C10; it does not replace
[`c06-distributed-execution-handoff.md`](c06-distributed-execution-handoff.md),
which remains the reference for steps A–D.

---

## Two things that changed since the C06 handoff was written

Read both before starting, because each changes a step you may already have
planned.

### 1. The worker image must be rebuilt first

C09 adds real code to the worker and the executor — resource packages, code
generation, the Kubernetes client, the validation runner. **The pinned C06
image `sha256:daf1052b…` does not contain any of it.**

The image was **not** rebuilt by this change: the Docker daemon was not running
on the Mac, and starting it is a host action that was not authorised. So step A
below builds it, and the digest it produces replaces `daf1052b…` in four
places.

Until step C rolls out the newly pinned image, the deployment still uses the
existing C06 image. Run **step C's loopback TLS check against the new one**.

### 2. Scan reading is currently blocked, and it is not a bug in the code

`MedAIBase/PaddleOCR-VL:0.9b` is installed on the Mac and reports
`capabilities: ["completion"]`. It has no projector layer, and an image request
returns `HTTP 500 image input is not supported`. C08 asks the runtime what a
model can do before sending it a page, so scan reading reports itself
unavailable rather than failing at the first scan.

Step J puts the decision in front of you. Nothing is downloaded without it.

---

## The order, and why it is this order

```
A  image           Ubuntu   rebuild the worker image with C09, record the digest
B  pin             Ubuntu   put the new digest in the four manifest fields
C  loopback TLS    Ubuntu   re-run C06 step D against the new image
D  LAN forwarder   Ubuntu   C06 step E, open 30443 to the one Mac address
E  pair            both     confirm the fingerprint, redeem the code
F  relationship    both     read the ID on the Mac, patch the Secret on Ubuntu
G  C09 components  Ubuntu   jobs volume, RBAC, network policies
H  executor        Ubuntu   deploy the consumer with its ServiceAccount
I  C06 acceptance  both     inference, cancellation, disconnect recovery
J  C08 decision    macOS    choose a scan-reading model, or accept unavailable
K  C09 fixture     both     one real validated patch
L  C10 acceptance  both     concurrency, approve/deny/expire, restart, Proof
```

Two dependencies fix this order and are worth stating, because getting them
wrong looks like a working system that quietly cannot work:

* **The executor cannot be deployed before pairing**, because it serves one
  relationship ID that pairing mints.
* **The C09 components must exist before the executor**, because the executor
  now names a ServiceAccount. Without `50-validation.yaml` applied, the Pod
  does not schedule at all — which is the correct closed state, not a fault.

---

## A. Ubuntu worker — rebuild the image with the C09 changes

Cached inputs only. If Docker asks to pull anything, **stop** and report which
object is missing rather than downloading it.

```bash
cd ~/AegisForge   # or wherever C05 put the repository
git pull          # only if the branch has been merged for you; otherwise copy the tree
```

```bash
sudo docker build --platform linux/amd64 --pull=false --provenance=false --sbom=false -f backend/worker-image/Dockerfile -t aegisforge-worker:c09 .
```

**Expected:** the build runs the offline test layer with `--network=none` and
that layer must pass. It now runs six suites, including the two new ones
(`backend.worker.test_packages`, `backend.worker.test_validation`).

Record the digests:

```bash
sudo docker image inspect aegisforge-worker:c09 --format '{{.Id}} {{.Architecture}}/{{.Os}}'
```

**Expected:** one `sha256:…` and `amd64/linux`. **Return that digest.**

Check nothing secret is baked in:

```bash
sudo docker image history --no-trunc aegisforge-worker:c09 | grep -iE 'token|password|secret|key' || echo "clean"
```

**Expected:** `clean`.

Export a persistent archive **outside the repository**:

```bash
sudo docker save aegisforge-worker:c09 -o ~/aegisforge-artifacts/aegisforge-worker-c09.tar && sha256sum ~/aegisforge-artifacts/aegisforge-worker-c09.tar
```

**Never commit the archive.** Return the checksum.

**Rollback:** `sudo docker image rm aegisforge-worker:c09`. The C06 image stays
in place, so the cluster keeps running whatever is already pinned.

---

## B. Ubuntu worker — pin the new digest in four places

Replace `sha256:daf1052b957a1da0107f835debc49e390a19bb18acb670df289cdabd53b95adf`
with the digest from step A in **all four**:

1. `deploy/k3s/20-worker.yaml` — the worker Deployment image
2. `deploy/k3s/40-executor.yaml` — the executor Deployment image
3. `deploy/k3s/40-executor.yaml` — `AEGIS_VALIDATION_IMAGE` in `executor-config`
4. `deploy/k3s/50-validation.yaml` — the admission policy's allowed image

Also update `backend/worker-image/provenance.json` with the observed manifest
digest, config digest and archive checksum.

Then confirm the manifests agree with the recorded build:

```bash
python3 -m unittest -q deploy.k3s.test_manifests
```

**Expected:** OK. Two checks here exist for this exact step: one asserts the
worker Deployment pins the recorded build, and one asserts the validation image
is pinned by digest **and matches** it. A mismatch fails loudly rather than
letting validation run a different build from the executor.

---

## C. Ubuntu worker — re-run the loopback TLS check against the new image

This is C06 step D, repeated because the image changed.

```bash
sudo kubectl -n aegisforge rollout restart deployment/aegisforge-worker && sudo kubectl -n aegisforge rollout status deployment/aegisforge-worker --timeout=180s
```

```bash
curl -sS --cacert /etc/aegisforge/tls/tls.crt --resolve aegisforge-worker:30443:127.0.0.1 https://aegisforge-worker:30443/v1/health -H "Authorization: Bearer $AEGIS_WORKER_TOKEN" -H 'X-AegisForge-Contract: 1.0'
```

**Expected:** a JSON `Node` record. `capabilities` will be `[]` and `health`
will be `degraded` until pairing exists — that is correct and fail-closed, not
a failure. Getting a TLS handshake and an authenticated 200 is the proof this
step is for.

---

## D. Ubuntu worker — C06 step E, the guarded LAN forwarder

**Unchanged.** Follow
[`c06-distributed-execution-handoff.md`](c06-distributed-execution-handoff.md)
step E exactly: open 30443 to the one Mac address only, with the guard service
ordered before the socket. Nothing in C09 changes this step, and its firewall
restriction to a single address still stands.

---

## E–F. Pair, and install the relationship ID

**Unchanged.** Follow the C06 handoff steps F and G: confirm the fingerprint
out of band on the Mac, redeem the pairing code, read the relationship ID on
the Mac, patch the `worker-credential` Secret on Ubuntu.

---

## G. Ubuntu worker — apply the C09 components

**New.** These do not exist yet on the cluster.

Read the Kubernetes API address first. It is per-cluster and is deliberately
**not** recorded in the repository:

```bash
sudo kubectl -n default get service kubernetes -o jsonpath='{.spec.clusterIP}'
```

Substitute that exact value for `API_SERVER_IP` in
`deploy/k3s/50-validation.yaml`, keeping the `/32`. **Do not widen it to a
subnet and do not use `0.0.0.0/0`** — that would give the executor a path to
every Service in the cluster. Leaving the file unapplied fails closed:
validation reports the API unreachable, which is honest.

First confirm this pinned K3s exposes the stable admission API and accepts the
manifest without changing the cluster:

```bash
sudo kubectl api-resources | grep -E '^validatingadmissionpolic(y|ies)' && sudo kubectl apply --dry-run=server -f deploy/k3s/50-validation.yaml
```

**Expected:** the admission resource is listed and every object reports
`created (server dry run)`. Stop if either check fails.

Then apply it:

```bash
sudo kubectl apply -f deploy/k3s/50-validation.yaml
```

**Expected:** a PersistentVolumeClaim `aegisforge-jobs`, ServiceAccounts
`aegisforge-executor` and `aegisforge-validation`, a Role and RoleBinding
`aegisforge-validation`, admission policy/binding `aegisforge-validation-job`,
and three NetworkPolicies.

Confirm the authority is as narrow as intended:

```bash
sudo kubectl -n aegisforge auth can-i --as=system:serviceaccount:aegisforge:aegisforge-executor get secrets
```

**Expected:** `no`. Repeat for `create pods`, `get configmaps`,
`create pods/exec` — **every one must answer `no`**. The only `yes` answers
should be `create jobs`, `get jobs`, `delete jobs`, `get pods`, `list pods` and
`get pods/log`.

RBAC alone cannot constrain a Job's Pod template. Prove the executor identity
cannot submit an arbitrary one, even though it may create the approved form:

```bash
sudo kubectl -n aegisforge create job admission-must-deny --as=system:serviceaccount:aegisforge:aegisforge-executor --image=docker.io/library/aegisforge-worker@sha256:daf1052b957a1da0107f835debc49e390a19bb18acb670df289cdabd53b95adf --dry-run=server -- true
```

**Expected:** the server denies it through `aegisforge-validation-job`; no Job
is created. A success is a blocker — do not start the executor.

**Rollback:** `sudo kubectl delete -f deploy/k3s/50-validation.yaml`. The
executor then stops scheduling, which is the closed state.

---

## H. Ubuntu worker — deploy the executor

```bash
sudo kubectl apply -f deploy/k3s/40-executor.yaml && sudo kubectl -n aegisforge rollout status deployment/aegisforge-executor --timeout=180s
```

**Expected:** one Ready Pod. If it stays `Pending` with a ServiceAccount error,
step G was not applied.

---

## I. Both devices — C06 acceptance

**Still required, and still not passed.** From the C06 handoff, section I:

1. one real Chat request that runs on the worker and returns to the Mac;
2. the route reason on the Mac names the paired worker;
3. cancellation stops it and the canonical record says `cancelled`;
4. an executor restart mid-attempt recovers rather than losing the work;
5. cluster loss leaves usable canonical history on the Mac.

**Do not proceed to C09 acceptance until these pass.** C08 and C09 code
existing is not evidence for C06.

---

## J. macOS coordinator — the C08 scan-reading decision

Check what the runtime reports:

```bash
curl -s http://127.0.0.1:11434/api/show -d '{"model":"MedAIBase/PaddleOCR-VL:0.9b"}' | python3 -c "import json,sys; print(json.load(sys.stdin).get('capabilities'))"
```

**Expected, as observed on 2026-09-05:** `['completion']` — no `vision`.

Then choose one:

* **Option 1 — use an already-installed vision-capable model. No download.**
  `qwen3.5:4b-q4_K_M` reports `['completion', 'vision', 'tools', 'thinking']`.
  Set `AEGIS_OCR_MODEL=qwen3.5:4b-q4_K_M` for the coordinator process. Record
  in `docs/model-catalog.md` that the configured OCR model changed and why.
* **Option 2 — install a vision-capable OCR model.** This is a **download**,
  and needs its own approved source, licence, SHA-256 and storage location
  recorded before it happens. It is a separate checkpoint.
* **Option 3 — change nothing.** C08 reports scan reading unavailable with the
  reason. Text and Word documents still work; PDF scans do not.

Whichever you choose, verify the fixture on the Mac:

```bash
desktop/.venv/bin/python -m unittest -v backend.coordinator.test_ocr.TestFixtureAgainstRealModel
```

**Expected under option 1 or 2:** 4 tests pass, in roughly 15–20 s. They assert
that every fixture fact appears **on the scan page the fixture names**, that the
illegible gauge stays `NOT RECORDED`, that the countersignature is reported
absent, and that no page carries an invented confidence.
**Expected under option 3:** 4 skipped, with the reason printed.

Then open the Word output and compare it against the scan yourself. That
comparison is the C08 acceptance gate; a passing fixture is a floor, not proof
of OCR quality on any other document.

---

## K. Both devices — the C09 validated-patch fixture

On the Mac, connect `fixtures/c07/code/pumpcheck` as a project in the Code
surface, select all four fixture files — `pumpcheck/__init__.py`,
`pumpcheck/limits.py`, `tests/__init__.py`, and `tests/test_limits.py` — and ask
for the change the fixture expects. The model may edit only `limits.py`, but the
sandbox needs the test module and package markers to discover a real test.

**Expected:**

1. the request routes to the Ubuntu worker, and the route reason says so;
2. a diff appears on the Mac and **the fixture directory is unchanged** —
   confirm with `git status --short fixtures/c07/code`;
3. sandbox validation creates one Job:

   ```bash
   sudo kubectl -n aegisforge get jobs -l app=aegisforge-validation
   ```

   **Expected:** one `af-validate-…` Job, completing within its deadline and
   collected by its TTL afterwards.
4. the recorded result shows `python3 -m unittest`, exit status 0 and at least
   one discovered test;
5. the canonical repository is **still** unchanged until you approve the write.

Confirm the sandbox really is isolated, while the Job exists:

```bash
sudo kubectl -n aegisforge describe pod -l app=aegisforge-validation | grep -E 'Image:|Mounts:|Service Account'
```

**Expected:** the pinned image digest, only `/package` (read-only) and
`/workspace`, and **no** service account token.

---

## L. Both devices — C10 acceptance

1. **Concurrency.** Start a Documents request on the Mac and a Code request to
   the worker at the same time. Both should show as running together, with
   separate attempts and separate artifacts. Documents will show **no Pod and
   no queue depth** — it runs locally, and claiming either would be false.
2. **Approve, deny, expire.** Deny one write and confirm nothing changed on
   disk. Let one expire and confirm the same. Approve one and confirm exactly
   one write.
3. **Restart during a final write.** Approve a multi-file change and quit the
   app while it is applying. Relaunch. **Expected:** the write finishes, files
   already written are not written again, and a file you edited yourself in the
   meantime is left alone and reported stale.
4. **Proof Cards.** Open Control Center, press **Proof** on a job. Check that
   every value names its source, that Documents shows no Pod row, that the
   validation attempt shows no model, and that network evidence says
   unavailable rather than zero.

---

## M. What to return

* the new image digest, architecture line, and archive SHA-256 (step A);
* the `auth can-i` answers (step G);
* the five C06 acceptance results (step I);
* which C08 option was chosen, and the fixture result (step J);
* the Job name, exit status and `describe pod` output (step K);
* the four C10 results (step L).

---

## N. What is proven, and what is not

**Proven offline, on the macOS coordinator, 2026-09-05:**

* 786 Python checks pass across contracts, coordinator, worker, manifests and
  fixtures, plus 90 browser checks;
* the Quartz renderer produces deterministic PNG pages from the real C07 scan;
* with an installed vision-capable model, the full extraction path recovers the
  fixture's known facts and does not take the `must_not_be` trap;
* the package format, the Job object, the validation runner, approval binding,
  durable write recovery and Proof Card honesty are all covered by checks that
  fail when their protection is removed.

**NOT proven, and not claimed anywhere:**

* no Kubernetes Job has ever been created — the whole AF-011 path has only been
  driven against a fake API;
* no package has crossed a real network;
* no code has been generated on the Ubuntu worker;
* no scan has been read by the configured OCR model, because it cannot accept
  images;
* the C09 worker image **has not been built**;
* zero egress, sandbox isolation, distributed behaviour, OCR quality and model
  quality are all **unavailable** as evidence;
* C05, C06, C07, C08, C09 and C10 are **all unaccepted**.
