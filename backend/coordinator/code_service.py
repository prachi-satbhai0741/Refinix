"""The Code surface's backend: one gate, then bounded work.

Every repository operation enters through `CodeService`, and the first thing
each one does is ask `policy.decide`. The HTTP handlers below it carry no mode
logic at all, so there is exactly one place to read and one place to test.

What the page and the model can influence:

* the page sends an opaque repository id, validated relative paths, a request
  in words, a mode chosen from a fixed list, and an approval id plus a yes/no.
  It never sends a filesystem path, a digest, a mode for a pending action, an
  `approved` flag, or replacement content;
* the model returns a summary and whole-file replacements for files it was
  given. It cannot name an unselected path, change a base hash, approve itself,
  or ask for an action that is not in the policy table.

The absolute root stays inside the coordinator. It is never returned to a
surface, put in a URL, or included in a model message.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time

from backend.contracts import v1
from backend.coordinator import (codeflow, db, dispatch, pairing, policy, repo,
                                 runtime)

# One proposal is one bounded local model call.
PROPOSAL_DEADLINE_SECONDS = 240
PROPOSAL_NUM_PREDICT = 2048

# AF-011. The ONLY command a validation Job may be asked to run, from the C07
# approved fixture. It is configuration on this side and is checked again
# against `backend.worker.validate.ALLOWED_COMMANDS` inside the sandbox, so a
# change here alone cannot widen what actually executes.
VALIDATION_COMMAND = ["python3", "-m", "unittest"]
VALIDATION_MINIMUM_TESTS = 1
VALIDATION_DEADLINE_SECONDS = 300
REMOTE_OUTPUT_BYTES = 1_048_576


class CodeError(ValueError):
    """A refusal the interface can show, with a code a test can assert."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class ApprovalNeeded(Exception):
    """Not an error: the operation is waiting for the person to decide."""

    def __init__(self, approval: dict):
        super().__init__("approval required")
        self.approval = approval


# Where a proposal was generated and where it may be applied. Recorded on the
# proposal, never inferred: "the worker did not answer" is not permission to
# write to somebody's files without the sandbox that normally gates it.
TARGET_LOCAL = "this_device"
TARGET_DISTRIBUTED = "distributed"
EXECUTION_TARGETS = (TARGET_LOCAL, TARGET_DISTRIBUTED)
DEFAULT_TARGET = TARGET_DISTRIBUTED

# What a local proposal's validation actually is. It is not a sandbox result
# and must never be shown or stored as one.
LOCAL_VALIDATION_NOTE = "Not sandbox tested — local device mode"


def normalise_target(raw) -> str:
    """Validate a target arriving from a request. Unknown values are refused."""
    if raw is None:
        return DEFAULT_TARGET
    if raw not in EXECUTION_TARGETS:
        raise CodeError("unknown_target", "That execution target does not exist.")
    return raw


def stored_target(proposal: dict | None) -> str:
    """The one place a persisted target is interpreted.

    Missing means `distributed`, because every proposal written before the
    column existed came from that path and it is the strict one.

    Anything else — a corrupted row, a value written by a future version, a
    hand-edited database — is **not** silently treated as either path. Two
    separate comparisons used to decide this: `apply` asked "is it
    distributed?" and the write step asked "is it this_device?", so a third
    value slipped between them, skipping sandbox validation *and* skipping the
    backup, and still reached the write loop. There is one answer now, and an
    unrecognised value raises rather than resolving to the permissive side.
    """
    raw = (proposal or {}).get("execution_target")
    if raw is None or raw == "":
        return DEFAULT_TARGET
    if raw not in EXECUTION_TARGETS:
        raise CodeError(
            "unknown_target",
            "That change records an execution target Refinix does not "
            f"recognise ({str(raw)[:40]!r}), so nothing was read or written. "
            "Ask for the change again.", 409)
    return raw


class CodeService:
    def __init__(self, coordinator):
        self.c = coordinator
        self._cancels: dict[str, threading.Event] = {}
        self._mutating: set[str] = set()
        self._lock = threading.Lock()

    # -- helpers ----------------------------------------------------------

    @property
    def conn(self):
        return self.c.conn

    @property
    def workspace_id(self) -> str:
        return self.c.workspace_id

    def _require_platform(self, repo_id: str | None = None) -> None:
        """Refuse the whole surface where containment cannot be guaranteed.

        Checked before the policy gate, so an unsupported computer never even
        creates an approval for work it could not carry out safely.
        """
        if repo.descriptor_traversal_supported():
            return
        db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                        action="repo.platform", outcome="denied",
                        detail={"reason": repo.PLATFORM_NOTE})
        raise CodeError("platform", repo.PLATFORM_NOTE, 501)

    def _repository(self, repo_id: str) -> dict:
        record = db.public_repository(self.conn, repo_id, self.workspace_id)
        if record is None:
            # An id from another workspace or another coordinator resolves to
            # nothing at all, rather than to somebody else's folder.
            raise CodeError("unknown_repository",
                            "That project is not connected to this workspace.", 404)
        return record

    def _root(self, repo_id: str):
        found = db.repository_root(self.conn, repo_id, self.workspace_id)
        if found is None:
            raise CodeError("unknown_repository",
                            "That project is not connected to this workspace.", 404)
        root, identity = found
        if not repo.root_is_intact(root, identity):
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=policy.ACTION_READ, outcome="rejected_stale",
                            detail={"reason": "the connected folder moved or was replaced"})
            raise CodeError("moved_root",
                            "The connected folder has moved or been replaced. "
                            "Connect it again.", 409)
        return root

    def _bind_conversation_repo(self, conversation_id: str, repo_id: str) -> None:
        current = db.code_conversation(self.conn, conversation_id,
                                       self.workspace_id)
        if current and current["repo_id"] != repo_id:
            db.set_conversation_repo(self.conn, conversation_id,
                                     self.workspace_id, repo_id)

    def _gate(self, repo_id: str, action: str, *, digest: str, target: str,
              approval_id: str | None, payload: dict, proposal_id: str | None = None,
              claim=None, binding: dict | None = None,
              conversation_id: str | None = None):
        """The one place an access mode decides anything.

        Returns the audit outcome to record on success. Raises `CodeError` for
        a denial and `ApprovalNeeded` when the person has to decide first.

        `claim` replaces the default consume step. `apply` supplies one that
        consumes the approval and creates the durable write record in a single
        transaction, so there is no window in which a decision is spent and
        nothing records what it authorised. The caller keeps the result in its
        own local; nothing about one call's claim is stored on the service. `binding` carries the workflow,
        job, step and attempt an approval belongs to, which is what makes an
        approval refer to one exact attempt's output rather than to a digest
        that some attempt somewhere produced.
        """
        record = self._repository(repo_id)
        mode = record["mode"]
        decision = policy.decide(mode, action)
        if decision.denied:
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=action, outcome="denied", mode=mode,
                            conversation_id=conversation_id,
                            detail={"reason": decision.reason, "target": target})
            raise CodeError("denied", decision.reason, 403)

        if decision.automatic:
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=action, outcome="allowed_automatically", mode=mode,
                            conversation_id=conversation_id,
                            detail={"reason": decision.reason, "target": target,
                                    "digest": digest})
            return "allowed_automatically"

        if approval_id:
            try:
                claimed = (claim(approval_id) if claim is not None else
                           db.claim_approval(self.conn, approval_id, self.workspace_id,
                                             action, digest, repo_id=repo_id,
                                             proposal_id=proposal_id,
                                             conversation_id=conversation_id))
            except db.ApprovalError as exc:
                outcome = {"expired": "expired", "denied": "denied"}.get(exc.code, "rejected_stale")
                db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                                action=action, outcome=outcome, mode=mode,
                                conversation_id=conversation_id,
                                approval_id=approval_id,
                                detail={"reason": str(exc), "target": target})
                raise CodeError(exc.code, str(exc), 409) from exc
            if claimed.get("repo_id") != repo_id:
                raise CodeError("mismatch", "That approval was for another project.", 409)
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=action, outcome="approved", mode=mode,
                            conversation_id=conversation_id,
                            approval_id=approval_id,
                            detail={"target": target, "digest": digest})
            return "approved"

        approval = db.request_approval(
            self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
            proposal_id=proposal_id, action=action, target=target,
            action_sha256=digest, conversation_id=conversation_id,
            payload={**payload, "repo_id": repo_id, "repo_name": record["name"],
                     "mode": mode},
            **(binding or {}))
        db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                        action=action, outcome="awaiting_approval", mode=mode,
                        conversation_id=conversation_id,
                        approval_id=approval["approval_id"],
                        detail={"target": target, "digest": digest})
        raise ApprovalNeeded(approval)

    # -- connection -------------------------------------------------------

    def connect(self, selected_path: str) -> dict:
        """Register a folder the person chose in the native dialog.

        Only the desktop bridge reaches this: no HTTP route accepts a path.
        """
        self._require_platform()
        root = repo.canonical_root(selected_path, state_dir=self.c.state_path.parent)
        record = db.register_repository(
            self.conn, workspace_id=self.workspace_id, name=root.name or str(root),
            root=str(root), identity=repo.root_identity(root),
            mode=policy.DEFAULT_MODE)
        db.record_audit(self.conn, workspace_id=self.workspace_id,
                        repo_id=record["repo_id"], action="repo.connect",
                        outcome="allowed_automatically", mode=record["mode"],
                        detail={"name": record["name"]})
        return record

    def repositories(self) -> list[dict]:
        return db.list_repositories(self.conn, self.workspace_id)

    def set_mode(self, repo_id: str, mode: str) -> dict:
        try:
            mode = policy.normalise_mode(mode)
        except ValueError as exc:
            raise CodeError("bad_mode", "That access mode does not exist.") from exc
        record = db.set_repository_mode(self.conn, repo_id, self.workspace_id, mode)
        if record is None:
            raise CodeError("unknown_repository",
                            "That project is not connected to this workspace.", 404)
        db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                        action="repo.mode", outcome="applied", mode=mode,
                        detail={"mode": mode})
        return record

    def forget(self, repo_id: str, discard_undo: bool = False) -> dict:
        """Disconnect a project. Never touches a file inside it.

        Refused while work for that project is in flight. The JavaScript
        check was not enough on its own: a second window, a retried request or
        a direct call could disconnect the project mid-apply, and the write
        loop would then lose the root under it. Enforced here so the answer is
        the same however the request arrives.
        """
        if not isinstance(discard_undo, bool):
            raise CodeError("bad_confirmation", "The Undo confirmation was invalid.")
        with self._lock:
            if repo_id in self._cancels or repo_id in self._mutating:
                raise CodeError(
                    "busy",
                    "A change is being prepared for this project. Wait for it "
                    "to finish or stop it, then remove the project.", 409)
            unfinished = self.conn.execute(
                "SELECT COUNT(*) AS open FROM write_operations"
                " WHERE repo_id=? AND workspace_id=? AND state NOT IN"
                " ('applied','partially_applied','failed','cancelled')",
                (repo_id, self.workspace_id)).fetchone()
            if unfinished and unfinished["open"]:
                raise CodeError(
                    "busy",
                    "A write to this project has not finished. Refinix keeps it "
                    "connected so the change can complete or be recovered.", 409)
            undoable = self.conn.execute(
                "SELECT COUNT(*) AS kept FROM write_backups WHERE repo_id=? AND"
                " workspace_id=? AND state='stored'",
                (repo_id, self.workspace_id)).fetchone()
            kept = int(undoable["kept"]) if undoable else 0
            if kept and not discard_undo:
                return {"confirmation_required": True, "undo_lost": kept}
            if not db.forget_repository(self.conn, repo_id, self.workspace_id):
                raise CodeError("unknown_repository",
                                "That project is not connected to this workspace.", 404)
            return {"disconnected": repo_id, "undo_lost": kept}

    # -- listing ----------------------------------------------------------

    def view(self, repo_id: str, path: str,
             approval_id: str | None = None,
             conversation_id: str | None = None) -> dict:
        """One file, for the person's own screen.

        Gated as `repo.view`, which is deliberately not `repo.read`: opening a
        file here puts it in front of the person and nowhere else. Nothing in
        this method adds the file to a prompt, and the reply says so, so
        "Ask before actions" can protect the model boundary without also
        stopping someone looking at their own code.

        The browser never learns where the folder is. Only the relative path
        the person clicked comes in, and only relative paths go back.
        """
        self._require_platform(repo_id)
        conversation_id = self.conversation(conversation_id)
        self._bind_conversation_repo(conversation_id, repo_id)
        relative = repo.normalise_relative(path)
        digest = codeflow.read_digest(repo_id, [relative])
        self._gate(repo_id, policy.ACTION_VIEW, digest=digest, target=relative,
                   approval_id=approval_id,
                   conversation_id=conversation_id,
                   payload={"summary": f"Open {relative} on this screen.",
                            "paths": [relative]})
        root = self._root(repo_id)
        try:
            text, identity = repo.read_text_file(root, relative)
        except repo.RepositoryError as exc:
            # The reasons are kept apart — too large, binary, not UTF-8,
            # missing, a link — because each one is a different thing for the
            # person to do about it.
            raise CodeError(exc.code, str(exc), 409) from exc
        lines = text.split("\n")
        return {
            "repo_id": repo_id, "path": relative,
            "name": relative.rsplit("/", 1)[-1],
            "lines": lines, "line_count": len(lines),
            "byte_size": identity.size, "sha256": identity.sha256,
            "truncated": False,
            # Stated in the payload so the surface can show it rather than the
            # page having to assert it on the coordinator's behalf.
            "sent_to_model": False,
            "note": ("Opened on this computer. This file has not been sent to "
                     "the model; add it to the request selection to do that."),
        }

    def files(self, repo_id: str, approval_id: str | None = None,
              conversation_id: str | None = None) -> dict:
        self._require_platform(repo_id)
        conversation_id = self.conversation(conversation_id)
        self._bind_conversation_repo(conversation_id, repo_id)
        digest = codeflow.read_digest(repo_id, ["<listing>"])
        self._gate(repo_id, policy.ACTION_LIST, digest=digest, target="file listing",
                   approval_id=approval_id,
                   conversation_id=conversation_id,
                   payload={"summary": "List the text files in this project."})
        root = self._root(repo_id)
        files = repo.list_text_files(root)
        return {"files": files, "limits": {
            "max_files": repo.MAX_SELECTED_FILES,
            "max_file_bytes": repo.MAX_FILE_BYTES,
            "max_total_bytes": repo.MAX_TOTAL_BYTES}}

    # -- proposal ---------------------------------------------------------

    def _read_selection(self, root, paths: list[str]) -> list[dict]:
        if not isinstance(paths, list) or not paths:
            raise CodeError("no_selection", "Select at least one file to change.")
        if len(paths) > repo.MAX_SELECTED_FILES:
            raise CodeError("too_many",
                            f"Select at most {repo.MAX_SELECTED_FILES} files.")
        selected, total = [], 0
        for raw in paths:
            try:
                relative = repo.normalise_relative(raw)
                text, identity = repo.read_text_file(root, relative)
            except repo.RepositoryError as exc:
                raise CodeError(exc.code, str(exc)) from exc
            total += identity.size
            if total > repo.MAX_TOTAL_BYTES:
                raise CodeError("too_large",
                                f"The selected files add up to more than "
                                f"{repo.MAX_TOTAL_BYTES // 1024} KB.")
            selected.append({"path": relative, "text": text,
                             "sha256": identity.sha256, "bytes": identity.size})
        return selected

    def cancel(self, repo_id: str) -> bool:
        with self._lock:
            event = self._cancels.get(repo_id)
        if event is None:
            return False
        event.set()
        return True

    def _begin_mutation(self, repo_id: str) -> None:
        with self._lock:
            if repo_id in self._mutating:
                raise CodeError("busy", "Another write or Undo is still running.", 409)
            self._mutating.add(repo_id)

    def _end_mutation(self, repo_id: str) -> None:
        with self._lock:
            self._mutating.discard(repo_id)

    def propose(self, repo_id: str, request: str, paths: list[str],
                approval_id: str | None = None,
                conversation_id: str | None = None,
                execution_target: str | None = None) -> dict:
        """Read the selection, ask the local model, validate, and store a diff.

        Nothing is written here. The result is a reviewable proposal.
        """
        self._require_platform(repo_id)
        if not isinstance(request, str) or not request.strip():
            raise CodeError("no_request", "Describe the change you want.")
        target = normalise_target(execution_target)
        if not isinstance(paths, list) or not paths:
            # Refuse before the gate, so an empty request cannot leave a
            # pointless approval waiting for the person in Ask mode.
            raise CodeError("no_selection", "Select at least one file to change.")
        try:
            normalised = sorted({repo.normalise_relative(p) for p in paths})
        except repo.RepositoryError as exc:
            raise CodeError(exc.code, str(exc)) from exc
        conversation_id = self.conversation(conversation_id)
        self._bind_conversation_repo(conversation_id, repo_id)
        digest = codeflow.read_digest(repo_id, normalised)

        # In Ask mode this one approval covers exactly this immutable batch of
        # reads plus sending them to the local model. A later added path
        # changes the digest and needs a new approval.
        # One gate for one action: reading the selection and sending it to the
        # local model. In Ask mode a single approval covers exactly this
        # immutable batch, and the audit below records that same authorisation
        # rather than calling the model call automatic afterwards.
        cancel = threading.Event()
        job_id = attempt_id = None
        with self._lock:
            if repo_id in self._cancels:
                raise CodeError("busy", "Wait for this project's proposal to finish or stop it.", 409)
            self._cancels[repo_id] = cancel
        try:
            authorised = self._gate(
                repo_id, policy.ACTION_READ, digest=digest,
                target=f"{len(normalised)} file(s)", approval_id=approval_id,
                conversation_id=conversation_id,
                payload={"paths": normalised,
                         "summary": policy.ACTION_LABELS[policy.ACTION_READ].capitalize()})
            root = self._root(repo_id)
            selection = self._read_selection(root, normalised)
            # AF-006 routing, asking for the capability this step actually
            # needs. Code generation runs on the paired worker when one is
            # healthy and advertises `code.generate`; otherwise it runs here,
            # and the attempt records which and why.
            model_id = self.c.model_for("code")
            if target == TARGET_LOCAL:
                # Explicitly this device. No preflight, no route decision and
                # no worker call: local permission is something the person
                # chose, never something inferred from the worker failing.
                route = dispatch.Route(
                    "local", "local coordinator: this device was chosen for "
                             "this request", node_id=self.c.node_id,
                    model=self.c.local_model_ref(model_id))
            else:
                route = self.c.choose_route(required=["code.generate"],
                                            model_id=model_id)
            if route.remote:
                parsed, job_id, attempt_id, model = self._propose_remote(
                    repo_id, request, selection, route, cancel, conversation_id)
                reasoning = False
            else:
                # A local proposal opens a real job and attempt in the chosen
                # conversation, exactly as the remote path does. Without this
                # the conversation id was accepted and dropped, so New and
                # History were controls over nothing.
                job_id = self._code_job(request, conversation_id)
                attempt_id = db.create_attempt(
                    self.conn, job_id=job_id, node_id=self.c.node_id,
                    route_reason=route.reason, model=route.model)
                # The declared lifecycle, walked properly rather than jumped:
                # created -> context_preparing -> queued -> routing -> running.
                for following in ("context_preparing", "queued", "routing",
                                  "running"):
                    db.set_job_state(self.conn, job_id, following)
                db.set_attempt_state(self.conn, attempt_id, "running")
                model = route.model or {"model_id": model_id}
                reply, reasoning = self._ask_model(
                    codeflow.build_messages(request, selection), cancel, model_id,
                    attempt_id=attempt_id)
                try:
                    parsed = codeflow.parse_proposal(reply, selection)
                except codeflow.ProposalError as first:
                    # Exactly one bounded repair attempt, on the same context.
                    if first.code not in ("not_json", "not_object", "unknown_fields"):
                        raise
                    retry, _ = self._ask_model(
                        codeflow.repair_messages(
                            codeflow.build_messages(request, selection), reply), cancel,
                        model_id, attempt_id=attempt_id, stage="repair_generation")
                    parsed = codeflow.parse_proposal(retry, selection)
        except codeflow.PackageError as exc:
            self._fail_code_job(job_id, attempt_id, exc.code, str(exc))
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=policy.ACTION_READ, outcome="failed",
                            conversation_id=conversation_id,
                            approval_id=approval_id,
                            detail={"reason": str(exc), "code": exc.code})
            raise CodeError(exc.code, str(exc), 422) from exc
        except codeflow.ProposalError as exc:
            self._fail_code_job(job_id, attempt_id, exc.code, str(exc))
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=policy.ACTION_READ, outcome="failed",
                            conversation_id=conversation_id,
                            approval_id=approval_id,
                            detail={"reason": str(exc), "code": exc.code})
            raise CodeError(exc.code, str(exc), 422) from exc
        except runtime.RuntimeUnavailable as exc:
            self._fail_code_job(job_id, attempt_id, "runtime", str(exc))
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=policy.ACTION_READ, outcome="failed",
                            conversation_id=conversation_id,
                            approval_id=approval_id, detail={"reason": str(exc)})
            raise CodeError("runtime", str(exc), 503) from exc
        except CodeError as exc:
            self._fail_code_job(job_id, attempt_id, exc.code, str(exc))
            raise
        except Exception as exc:
            self._fail_code_job(job_id, attempt_id, "internal_error", str(exc))
            raise
        finally:
            with self._lock:
                if self._cancels.get(repo_id) is cancel:
                    self._cancels.pop(repo_id)

        write_digest = codeflow.action_digest(repo_id, parsed["edits"])
        proposal = db.create_proposal(
            self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
            job_id=job_id, attempt_id=attempt_id, request=request,
            summary=parsed["summary"], digest=write_digest, edits=parsed["edits"],
            selection=[{"path": item["path"], "sha256": item["sha256"]}
                       for item in selection],
            execution_target=target)
        # `authorised` is what the gate actually decided — `approved` with the
        # approval id in Ask mode, `allowed_automatically` otherwise.
        db.record_audit(
            self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
            action="model.proposed", outcome=authorised, approval_id=approval_id,
            conversation_id=conversation_id,
            detail={"proposal_id": proposal["proposal_id"],
                    "authorised_by": policy.ACTION_READ,
                    "edits": len(parsed["edits"]),
                    "model": (model or {}).get("model_id"),
                    "node": "worker" if target == TARGET_DISTRIBUTED else "coordinator",
                    "conversation_id": self.conn.execute(
                        "SELECT chat_id FROM jobs WHERE job_id=?",
                        (job_id,)).fetchone()["chat_id"] if job_id else None,
                    "reasoning_enabled": reasoning, "digest": write_digest})
        # The request and the result are persisted in the conversation, so
        # reopening it shows the work rather than an empty panel.
        if job_id:
            chat_id = self.conn.execute(
                "SELECT chat_id FROM jobs WHERE job_id=?",
                (job_id,)).fetchone()["chat_id"]
            db.add_message(self.conn, chat_id, "user", request, job_id=job_id)
            db.add_message(self.conn, chat_id, "assistant",
                           parsed["summary"], job_id=job_id)
            if attempt_id and target == TARGET_LOCAL:
                db.set_attempt_state(self.conn, attempt_id, "validating")
                db.set_attempt_state(self.conn, attempt_id, "completed")
            if target == TARGET_LOCAL:
                db.set_job_state(self.conn, job_id, "validating")
                db.set_job_state(self.conn, job_id, "completed")
        return proposal

    def _propose_remote(self, repo_id: str, request: str, selection: list[dict],
                        route, cancel: threading.Event,
                        conversation_id: str | None = None):
        """Generate the proposal on the paired worker.

        The worker returns the model's reply and nothing more. The diff, every
        digest re-check and the canonical write boundary all stay here, because
        this side is the only one that knows where the project actually is —
        the worker never receives an absolute path.
        """
        job_id = self._code_job(request, conversation_id)
        step = self._remote_step(
            job_id=job_id, route=route, request=request,
            package=lambda attempt_id: codeflow.build_package(
                selection, workspace_id=self.workspace_id,
                relationship_id=route.relationship_id, attempt_id=attempt_id),
            capability="code.generate", cancel=cancel)
        # Parsed against exactly the selection that was packaged, on this side.
        # A reply naming an unselected path, a wrong base hash or an unknown
        # field is refused here, where the repository is.
        parsed = codeflow.parse_proposal(step["text"], selection)
        return parsed, job_id, step["attempt_id"], route.model

    # -- AF-010/AF-011 remote code ----------------------------------------

    def _code_job(self, request: str, conversation_id: str | None = None) -> str:
        """One persisted job for a Code request, created BEFORE any dispatch.

        The job belongs to exactly one Code conversation. Isolation between
        conversations is then the `chat_id` foreign key the rest of the system
        already uses, rather than a second mechanism that could disagree with
        it. With no conversation named, the workspace conversation is used, so
        history recorded before conversations existed still resolves.
        """
        return db.create_job(
            self.conn, workspace_id=self.workspace_id,
            chat_id=self.conversation(conversation_id),
            request=request, task_type="code")

    def conversation(self, conversation_id: str | None = None) -> str:
        """Resolve a Code conversation id, refusing one that is not Code.

        A Chat conversation id passed here would put code jobs into the
        person's ordinary history, so it is rejected rather than accepted.
        """
        if conversation_id is None:
            return db.code_chat(self.conn, self.workspace_id)
        row = self.conn.execute(
            "SELECT chat_id FROM chats WHERE chat_id=? AND workspace_id=? AND kind=?",
            (conversation_id, self.workspace_id, db.CODE_KIND)).fetchone()
        if row is None:
            raise CodeError("unknown_conversation",
                            "That Code conversation does not exist.", 404)
        return row["chat_id"]

    def new_conversation(self, title: str = "", repo_id: str | None = None) -> dict:
        """Start a Code conversation. Projects stay connected."""
        if repo_id is not None:
            self._repository(repo_id)
        return db.create_code_conversation(
            self.conn, self.workspace_id, title=title or "New code conversation",
            repo_id=repo_id)

    def conversations(self) -> list[dict]:
        return db.code_conversations(self.conn, self.workspace_id)

    def update_conversation(self, conversation_id: str, repo_id: str | None,
                            open_path: str | None = None) -> dict:
        conversation_id = self.conversation(conversation_id)
        if repo_id is not None:
            self._repository(repo_id)
        if open_path is not None:
            if repo_id is None:
                raise CodeError("no_repository", "Open files belong to a project.")
            try:
                open_path = repo.normalise_relative(open_path)
            except repo.RepositoryError as exc:
                raise CodeError(exc.code, str(exc)) from exc
        db.set_conversation_repo(self.conn, conversation_id, self.workspace_id,
                                 repo_id)
        db.set_conversation_open_path(self.conn, conversation_id,
                                      self.workspace_id, open_path)
        return db.code_conversation(self.conn, conversation_id, self.workspace_id)

    def reject(self, repo_id: str, proposal_id: str,
               conversation_id: str | None) -> dict:
        conversation_id = self.conversation(conversation_id)
        proposal = db.get_proposal(self.conn, proposal_id, self.workspace_id)
        if proposal is None or proposal["repo_id"] != repo_id:
            raise CodeError("unknown_proposal", "That proposal no longer exists.", 404)
        if self._proposal_conversation(proposal) != conversation_id:
            raise CodeError("mismatch", "That change belongs to another conversation.", 409)
        if not db.reject_proposal(self.conn, proposal_id, self.workspace_id,
                                  conversation_id, self.c.node_id):
            raise CodeError("not_pending", "That change is no longer awaiting a decision.", 409)
        db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                        conversation_id=conversation_id, action="proposal.reject",
                        outcome="denied", detail={"proposal_id": proposal_id})
        return {"proposal_id": proposal_id, "state": "rejected"}

    def _remote_step(self, *, job_id: str, route, request: str, package: dict,
                     capability: str, cancel: threading.Event):
        """Upload the package, dispatch one attempt, and read it back.

        The order is load-bearing. The package is uploaded first, because the
        worker refuses a code envelope whose package is absent — so an accepted
        receipt means the attempt can actually run. The job and the attempt are
        already in SQLite before either call, so a failure anywhere below
        leaves a complete local record rather than a hole.

        Ambiguity is handled exactly as C06 handles it: once the submit has
        begun, a missing answer means the worker MAY be running this attempt,
        and there is no local fallback from that point. Falling back would run
        the same request twice.
        """
        relationship = db.get_relationship(self.conn, route.relationship_id,
                                           self.workspace_id)
        if relationship is None or relationship["state"] != "paired":
            raise CodeError("worker", "The pairing was revoked before dispatch.", 409)
        attempt_id = db.create_attempt(
            self.conn, job_id=job_id, node_id=route.node_id,
            route_reason=route.reason, model=route.model)
        db.set_attempt_relationship(self.conn, attempt_id, route.relationship_id)
        job = dict(self.conn.execute("SELECT * FROM jobs WHERE job_id=?",
                                     (job_id,)).fetchone())
        step = self.conn.execute("SELECT step_id FROM attempts WHERE attempt_id=?",
                                 (attempt_id,)).fetchone()["step_id"]
        built = package(attempt_id)
        client = self.c.worker_client(relationship)
        try:
            client.upload_package({**built["body"],
                                   "workspace_id": self.workspace_id,
                                   "relationship_id": route.relationship_id,
                                   "attempt_id": attempt_id})
            envelope = dispatch.build_envelope(
                job=job, attempt_id=attempt_id, step_id=step, route=route,
                coordinator_node_id=self.c.node_id, request_text=request,
                task_type="code", required_capabilities=[capability],
                context=[v1.ResourceRef(**item) for item in built["resources"]],
                output=v1.OutputContract(
                    kind="patch",
                    validators=(["patch.applies"] if capability == "code.generate"
                                else ["patch.applies", "sandbox.exit_zero"]),
                    schema_ref=None),
                runtime_seconds=(VALIDATION_DEADLINE_SECONDS
                                 if capability == "code.validate"
                                 else PROPOSAL_DEADLINE_SECONDS),
                output_bytes=REMOTE_OUTPUT_BYTES)
            client.submit(envelope, dispatch.idempotency_key_for(attempt_id))
        except dispatch.ReceiptUnknown as exc:
            db.set_attempt_state(self.conn, attempt_id, "running")
            db.set_attempt_state(self.conn, attempt_id, "interrupted", error={
                "code": "worker_lost",
                "message": ("the worker did not confirm the request; it may be "
                            f"running there, so it was not re-run here. {exc}")[:256],
                "retryable": True})
            raise CodeError(
                "receipt_unknown",
                "The worker did not confirm the request. It may be running there, "
                "so Refinix did not run it again here.", 409) from exc
        except pairing.IdentityMismatch as exc:
            db.set_attempt_state(self.conn, attempt_id, "running")
            db.set_attempt_state(self.conn, attempt_id, "failed", error={
                "code": "permission_denied", "message": str(exc)[:256],
                "retryable": False})
            raise CodeError("identity", str(exc), 409) from exc
        except (dispatch.DispatchUnavailable, pairing.PairingError) as exc:
            db.set_attempt_state(self.conn, attempt_id, "running")
            db.set_attempt_state(self.conn, attempt_id, "failed", error={
                "code": "unavailable", "message": str(exc)[:256], "retryable": True})
            raise CodeError("worker", str(exc), 503) from exc

        db.set_attempt_state(self.conn, attempt_id, "running")
        try:
            outcome = dispatch.consume(
                client, envelope,
                should_cancel=lambda: cancel.is_set() or self.c.stopping.is_set())
        except pairing.IdentityMismatch as exc:
            # Deliberately NOT flattened into "unavailable". A changed worker
            # identity mid-stream is the event pinning exists to surface, and
            # it must reach the operator as itself rather than as a traceback.
            db.set_attempt_state(self.conn, attempt_id, "failed", error={
                "code": "permission_denied", "message": str(exc)[:256],
                "retryable": False})
            raise CodeError("identity", str(exc), 409) from exc
        for event in outcome.events:
            db.append_event(self.conn, job_id=job_id, attempt_id=attempt_id,
                            node_id=route.node_id, data=event.data.model_dump())
        if outcome.text:
            db.append_output(self.conn, attempt_id, outcome.text)
        if outcome.state != "completed":
            db.set_attempt_state(self.conn, attempt_id, outcome.state,
                                 error=outcome.failure)
            raise CodeError("worker",
                            (outcome.failure or {}).get("message",
                                                        "the worker did not finish"),
                            409)
        db.set_attempt_state(self.conn, attempt_id, "validating")
        db.set_attempt_state(self.conn, attempt_id, "completed")
        return {"attempt_id": attempt_id, "step_id": step, "text": outcome.text,
                "node_id": route.node_id, "package": built}

    def validate(self, repo_id: str, proposal_id: str,
                 conversation_id: str | None = None) -> dict:
        """Run the approved command against the reviewed change, in the sandbox.

        A SEPARATE attempt from generation, on purpose: it runs on a different
        thing (a restricted Job, not a model) and produces different evidence,
        and one Proof record must never describe two of those as one attempt.

        The canonical repository is not touched. What travels is a second
        package holding the originals, the reviewed replacements and the plan —
        all covered by one digest the worker verifies.
        """
        self._require_platform(repo_id)
        proposal = db.get_proposal(self.conn, proposal_id, self.workspace_id)
        if proposal is None or proposal["repo_id"] != repo_id:
            raise CodeError("unknown_proposal", "That proposal no longer exists.", 404)
        conversation_id = self._check_proposal_conversation(
            proposal, conversation_id)
        if not proposal["edits"]:
            raise CodeError("no_edits", "That proposal contains no file changes.")
        target = stored_target(proposal)
        if target != TARGET_DISTRIBUTED:
            raise CodeError(
                "not_distributed",
                "This-device changes are not sent to the Ubuntu sandbox. Review "
                "the diff and apply them locally, or request a distributed change.",
                409)
        route = self.c.choose_route(required=["code.validate"], require_model=False)
        if not route.remote:
            raise CodeError(
                "no_sandbox",
                "Sandbox validation runs on the paired worker, and it is not "
                f"available: {route.reason}", 503)

        root = self._root(repo_id)
        contents = db.proposal_edit_contents(self.conn, proposal_id)
        selected = proposal["selection"] or [
            {"path": edit["path"], "sha256": edit["base_sha256"]}
            for edit in contents]
        originals = []
        for item in selected:
            try:
                text, identity = repo.read_text_file(root, item["path"])
            except repo.RepositoryError as exc:
                raise CodeError(exc.code, str(exc)) from exc
            if identity.sha256 != item["sha256"]:
                raise CodeError(
                    "stale",
                    f"{item['path']} changed since the proposal was reviewed, so "
                    "it was not validated.", 409)
            originals.append({"path": item["path"], "text": text,
                              "sha256": identity.sha256, "bytes": identity.size})

        plan = {"command": list(VALIDATION_COMMAND),
                "minimum_tests": VALIDATION_MINIMUM_TESTS,
                "replacements": [{"path": edit["path"],
                                  "base_sha256": edit["base_sha256"],
                                  "after_sha256": edit["after_sha256"]}
                                 for edit in contents],
                "runtime_seconds": VALIDATION_DEADLINE_SECONDS}
        selection = [
            {"path": f"original/{item['path']}", "text": item["text"],
             "sha256": item["sha256"], "bytes": item["bytes"]}
            for item in originals]
        selection += [
            {"path": f"replacement/{edit['path']}", "text": edit["content"],
             "sha256": edit["after_sha256"],
             "bytes": len(edit["content"].encode("utf-8"))}
            for edit in contents]
        plan_text = json.dumps(plan, sort_keys=True)
        selection.append({"path": "plan.json", "text": plan_text,
                          "sha256": hashlib.sha256(
                              plan_text.encode("utf-8")).hexdigest(),
                          "bytes": len(plan_text.encode("utf-8"))})

        job_id = self._code_job(
            f"validate {proposal_id}", conversation_id)
        cancel = threading.Event()
        try:
            step = self._remote_step(
                job_id=job_id, route=route, request=f"validate {proposal_id}",
                package=lambda attempt_id: codeflow.build_package(
                    selection, workspace_id=self.workspace_id,
                    relationship_id=route.relationship_id, attempt_id=attempt_id),
                capability="code.validate", cancel=cancel)
        except codeflow.PackageError as exc:
            raise CodeError(exc.code, str(exc), 422) from exc
        try:
            result = json.loads(step["text"])
        except ValueError as exc:
            raise CodeError("bad_result",
                            "The sandbox returned an unreadable result.", 502) from exc
        if not isinstance(result, dict):
            raise CodeError("bad_result", "The sandbox returned an unreadable result.",
                            502)
        record = db.record_validation(
            self.conn, workspace_id=self.workspace_id, proposal_id=proposal_id,
            job_id=job_id, attempt_id=step["attempt_id"], node_id=step["node_id"],
            result=result, patch_sha256=proposal["digest"],
            detail=None if result.get("observed") else result.get("error"))
        db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                        action="sandbox.validate",
                        outcome="applied" if record["passed"] else "failed",
                        conversation_id=conversation_id,
                        detail={"proposal_id": proposal_id,
                                "job_name": record["job_name"],
                                "observed": record["observed"],
                                "exit_status": record["exit_status"]})
        return record

    def _fail_code_job(self, job_id: str | None, attempt_id: str | None,
                       code: str, message: str) -> None:
        """Close any local lifecycle opened before proposal parsing failed."""
        if code == "cancelled":
            attempt_state, job_state, failure_code = (
                "cancelled", "cancelled", "cancelled_by_user")
        else:
            attempt_state, job_state = "failed", "failed"
            failure_code = ({"runtime": "unavailable",
                             "internal_error": "internal_error"}.get(
                                 code, "validation_failed"))
        error = {"code": failure_code, "message": (message or code)[:256],
                 "retryable": True}
        if attempt_id:
            row = self.conn.execute(
                "SELECT state, metrics_json FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if row and row["state"] not in v1.TERMINAL_ATTEMPT_STATES:
                metrics = json.loads(row["metrics_json"]) if row["metrics_json"] else {}
                metrics.setdefault("failure_stage", "repair_validation" if metrics.get("stage") == "repair_generation" else "validation")
                db.set_attempt_metrics(self.conn, attempt_id, metrics)
                db.set_attempt_state(self.conn, attempt_id, attempt_state, error=error)
        if job_id:
            row = self.conn.execute(
                "SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row and row["state"] not in v1.TERMINAL_JOB_STATES:
                db.set_job_state(self.conn, job_id, job_state)

    def _ask_model(self, messages, cancel: threading.Event,
                   model_id: str, *, attempt_id: str | None = None,
                   stage: str = "generation") -> tuple[str, bool]:
        """One bounded local model call with its setting and diagnostics recorded."""
        reasoning = db.get_reasoning(self.conn, model_id)
        if attempt_id:
            db.set_attempt_reasoning(self.conn, attempt_id, model_id, reasoning)
        deadline = time.monotonic() + PROPOSAL_DEADLINE_SECONDS
        collected, metrics = [], {}
        completed = False
        try:
            for kind, payload in runtime.stream_chat(
                    messages, model=model_id, think=reasoning,
                    response_format=codeflow.PROPOSAL_SCHEMA,
                    num_predict=PROPOSAL_NUM_PREDICT,
                    should_cancel=lambda: cancel.is_set() or time.monotonic() > deadline
                    or self.c.stopping.is_set()):
                if kind == "delta":
                    collected.append(payload)
                elif kind == "cancelled":
                    if not cancel.is_set() and time.monotonic() > deadline:
                        raise runtime.RuntimeUnavailable("code proposal generation timed out")
                    raise CodeError("cancelled", "That request was stopped.", 409)
                elif kind == "done":
                    metrics = {key: value for key, value in payload.items() if key in (
                        "done_reason", "limit_reason", "context_window",
                        "output_token_limit", "eval_count", "prompt_tokens",
                        "prompt_eval_ms", "eval_ms", "load_ms", "total_ms",
                        "tokens_per_s")}
            if metrics.get("done_reason") != "stop":
                raise runtime.RuntimeUnavailable(
                    "the runtime did not finish the code proposal cleanly")
            completed = True
        finally:
            if attempt_id:
                metrics["stage"] = stage
                if not completed:
                    metrics["failure_stage"] = stage
                db.set_attempt_metrics(self.conn, attempt_id, metrics)
        return "".join(collected), reasoning

    # -- apply ------------------------------------------------------------

    def apply(self, repo_id: str, proposal_id: str,
              approval_id: str | None = None,
              conversation_id: str | None = None) -> dict:
        self._begin_mutation(repo_id)
        try:
            return self._apply(repo_id, proposal_id, approval_id, conversation_id)
        finally:
            self._end_mutation(repo_id)

    def _apply(self, repo_id: str, proposal_id: str,
               approval_id: str | None = None,
               conversation_id: str | None = None) -> dict:
        """Apply a stored proposal, one exact atomic file replacement at a time.

        The approval is consumed and the durable write record is created in one
        transaction (`db.claim_approval_for_write`), so a coordinator that stops
        immediately afterwards restarts with a record of exactly what was
        authorised and how far it got. `_run_operation` is then the same code
        path for the first run and for the recovery.
        """
        self._require_platform(repo_id)
        proposal = db.get_proposal(self.conn, proposal_id, self.workspace_id)
        if proposal is None or proposal["repo_id"] != repo_id:
            raise CodeError("unknown_proposal", "That proposal no longer exists.", 404)
        conversation_id = self._check_proposal_conversation(
            proposal, conversation_id)
        if proposal["state"] not in ("proposed", "partially_applied"):
            raise CodeError("not_pending", "That change is no longer awaiting a decision.", 409)
        if not proposal["edits"]:
            raise CodeError("no_edits", "That proposal contains no file changes.")
        # The proposal's recorded target decides which gate applies. A row
        # with no target defaults to `distributed`, so nothing written before
        # this existed can become locally applicable by omission.
        target = stored_target(proposal)
        if target == TARGET_DISTRIBUTED:
            validation = db.latest_validation(self.conn, proposal_id, self.workspace_id)
            if not validation or not validation["observed"] or not validation["passed"] \
                    or validation["patch_sha256"] != proposal["digest"]:
                raise CodeError(
                    "validation_required",
                    "Run sandbox validation and get a current passing result before applying.",
                    409)
        else:
            # Local mode. There is no sandbox result and none is invented: a
            # fabricated passing row here would be the single worst thing this
            # module could do. The proposal is still gated by the access mode,
            # still shown as a complete diff, still digest-checked against the
            # files on disk, and its originals are backed up before any write.
            existing = db.latest_validation(self.conn, proposal_id, self.workspace_id)
            if existing and existing["passed"]:
                # A passing row against a local proposal means a digest was
                # reused from somewhere it did not belong. Refuse rather than
                # accept evidence this proposal did not earn.
                raise CodeError(
                    "validation_mismatch",
                    "That local proposal carries a sandbox result it did not "
                    "produce. It was not applied.", 409)
        paths = [e["path"] for e in proposal["edits"]]
        contents = db.proposal_edit_contents(self.conn, proposal_id)
        plan = [{"path": edit["path"], "edit_id": edit["edit_id"],
                 "base_sha256": edit["base_sha256"],
                 "after_sha256": edit["after_sha256"]} for edit in contents]

        # The claim is captured in a LOCAL, closed over by this call's own
        # lambda. It must never live on `self`: C10 runs two workflows at once,
        # and a shared slot would let one thread pick up another thread's
        # authorised write record and apply the wrong change.
        claimed: list[dict] = []

        def claim_write(given: str) -> dict:
            record = db.claim_approval_for_write(
                self.conn, given, self.workspace_id,
                action=policy.ACTION_WRITE, action_sha256=proposal["digest"],
                repo_id=repo_id, proposal_id=proposal_id, edits=plan,
                conversation_id=conversation_id)
            claimed.append(record)
            return record

        outcome = self._gate(
            repo_id, policy.ACTION_WRITE, digest=proposal["digest"],
            target=", ".join(paths), approval_id=approval_id,
            conversation_id=conversation_id,
            proposal_id=proposal_id,
            binding={"job_id": proposal.get("job_id"),
                     "attempt_id": proposal.get("attempt_id")},
            claim=claim_write,
            payload={"paths": paths, "summary": proposal["summary"],
                     "proposal_id": proposal_id})

        if outcome == "approved":
            operation = claimed[0] if claimed else None
            if not operation or "operation_id" not in operation:
                # The claim path must always produce the record; refusing here
                # is what keeps a spent approval from writing unrecorded.
                raise CodeError("no_operation",
                                "That approval could not be bound to a write record.",
                                409)
        else:
            # Full access: no approval, same durable record.
            operation = db.create_write_operation(
                self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                proposal_id=proposal_id, action=policy.ACTION_WRITE,
                action_sha256=proposal["digest"], edits=plan)
        return self._run_operation(operation, allowed_by=outcome,
                                   approval_id=approval_id)

    def undo(self, repo_id: str, proposal_id: str,
             conversation_id: str | None = None) -> dict:
        self._begin_mutation(repo_id)
        try:
            return self._undo(repo_id, proposal_id, conversation_id)
        finally:
            self._end_mutation(repo_id)

    def _undo(self, repo_id: str, proposal_id: str,
              conversation_id: str | None = None) -> dict:
        """Put back exactly the files this one local proposal replaced.

        The digest check is the whole safety property. A file is restored only
        while it still holds precisely what this proposal wrote; if anything
        touched it afterwards — a person, an editor, another tool — that later
        work is not this module's to discard, so the restore is refused as
        stale and the file is left exactly as it is.

        Restoration goes through the same hardened replacement path as the
        apply did. It is not Git, it invokes no Git, and it restores nothing
        that this proposal did not write.
        """
        self._require_platform(repo_id)
        proposal = db.get_proposal(self.conn, proposal_id, self.workspace_id)
        if proposal is None or proposal["repo_id"] != repo_id:
            raise CodeError("unknown_proposal", "That change no longer exists.", 404)
        conversation_id = self._check_proposal_conversation(
            proposal, conversation_id)
        if stored_target(proposal) != TARGET_LOCAL:
            raise CodeError(
                "not_local",
                "Undo restores changes this device applied. That change was "
                "applied through the distributed path.", 409)
        backups = db.proposal_backups(self.conn, proposal_id, self.workspace_id)
        if not backups:
            raise CodeError(
                "no_backup",
                "There is no stored original for that change, so it cannot be "
                "undone here.", 409)

        root = self._root(repo_id)
        store = db.backups_root(self.c.state_path)
        results, restored = [], 0
        for row in backups:
            path = row["path"]
            current = self._current_digest(root, path)
            if current is None:
                detail = "That file is no longer in the project."
                results.append({"path": path, "state": "missing", "detail": detail})
                continue
            if current == row["original_sha256"]:
                # Never written, or already put back. There is nothing to undo
                # here, and calling that "changed after Refinix wrote it"
                # would blame the person for a write that never happened.
                results.append({"path": path, "state": "unchanged",
                                "detail": "That file was never changed."})
                restored += 1
                continue
            if current != row["proposed_sha256"]:
                # Somebody changed it after Refinix did. Their work stands.
                detail = ("That file changed after Refinix wrote it, so it was "
                          "left alone.")
                db.record_audit(self.conn, workspace_id=self.workspace_id,
                                repo_id=repo_id, action=policy.ACTION_WRITE,
                                outcome="rejected_stale",
                                conversation_id=conversation_id,
                                detail={"path": path, "reason": detail,
                                        "stage": "undo",
                                        "proposal_id": proposal_id})
                results.append({"path": path, "state": "rejected_stale",
                                "detail": detail})
                continue
            try:
                original = db.verify_backup(store, row)
            except db.BackupError as exc:
                results.append({"path": path, "state": "failed",
                                "detail": f"The stored original could not be read: {exc}"})
                continue
            try:
                repo.replace_text_file(root, path,
                                       expected_sha256=row["proposed_sha256"],
                                       text=original.decode("utf-8"))
            except (repo.RepositoryError, UnicodeDecodeError) as exc:
                results.append({"path": path, "state": "failed", "detail": str(exc)})
                continue
            db.record_audit(self.conn, workspace_id=self.workspace_id,
                            repo_id=repo_id, action=policy.ACTION_WRITE,
                            outcome="applied",
                            conversation_id=conversation_id,
                            detail={"path": path, "stage": "undo",
                                    "proposal_id": proposal_id,
                                    "restored_sha256": row["original_sha256"]})
            results.append({"path": path, "state": "restored"})
            restored += 1

        if restored == len(backups):
            db.consume_backups(self.conn, store, proposal_id, self.workspace_id)
            db.set_proposal_state(self.conn, proposal_id, "undone")
        return {"proposal_id": proposal_id, "restored": restored,
                "total": len(backups), "files": results,
                "complete": restored == len(backups)}

    def _back_up_originals(self, operation: dict, proposal: dict,
                           contents: list[dict]) -> list[dict]:
        """Copy every original this proposal will replace, before any of them
        is replaced.

        All of them, or none: a half-backed-up multi-file change would leave
        files that Undo could not restore. Each original is re-read from disk
        and re-hashed here rather than trusted from the proposal, so a file
        that moved under the proposal is caught before it is overwritten.
        """
        root = self._root(operation["repo_id"])
        store = db.backups_root(self.c.state_path)
        made: list[dict] = []
        existing = {row["path"] for row
                    in db.proposal_backups(self.conn, proposal["proposal_id"],
                                           self.workspace_id)}
        for edit in contents:
            path = edit["path"]
            if path in existing:
                # A row is not a backup. It is proved below, with every other
                # planned file, before the write loop starts.
                continue
            try:
                text, identity = repo.read_text_file(root, path)
            except repo.RepositoryError as exc:
                raise db.BackupError(f"{path} could not be re-read: {exc}") from exc
            if identity.sha256 == edit["after_sha256"]:
                # A restart found this file already written. There is nothing
                # left to back up — the original is gone — and refusing here
                # would strand a half-applied operation instead of finishing
                # it. It is skipped, and `undo` simply has no copy to offer
                # for this path rather than claiming one it does not hold.
                continue
            if identity.sha256 != edit["base_sha256"]:
                raise db.BackupError(
                    f"{path} changed since the change was reviewed, so it was "
                    "left alone.")
            made.append(db.record_backup(
                self.conn, store, workspace_id=self.workspace_id,
                repo_id=operation["repo_id"],
                conversation_id=self._proposal_conversation(proposal),
                proposal_id=proposal["proposal_id"],
                proposal_digest=proposal["digest"], path=path,
                original=text.encode("utf-8"), original_sha256=identity.sha256,
                proposed_sha256=edit["after_sha256"]))
        db.prune_backups(self.conn, store, self.workspace_id)
        self._prove_backups(operation, proposal, contents, store)
        return made

    def _prove_backups(self, operation: dict, proposal: dict,
                       contents: list[dict], store) -> None:
        """Every file this operation will write has one verified original.

        Run after the copies are taken and before the write loop, so a row
        whose file vanished or changed between a restart and now stops the
        operation instead of being skipped. A file already at its after-hash
        is excluded: it was written before a crash, its original is genuinely
        gone, and demanding a copy for it would strand a half-applied change.
        """
        root = self._root(operation["repo_id"])
        rows = {row["path"]: row for row
                in db.proposal_backups(self.conn, proposal["proposal_id"],
                                       self.workspace_id)}
        for edit in contents:
            path = edit["path"]
            if self._current_digest(root, path) == edit["after_sha256"]:
                continue
            row = rows.get(path)
            if row is None:
                raise db.BackupError(
                    f"no stored original is recorded for {path}.")
            # Bound to this exact proposal and this exact change, so a copy
            # taken for some other proposal can never stand in for this one.
            if row["proposal_digest"] != proposal["digest"] \
                    or row["repo_id"] != operation["repo_id"] \
                    or row["original_sha256"] != edit["base_sha256"] \
                    or row["proposed_sha256"] != edit["after_sha256"]:
                raise db.BackupError(
                    f"the stored original for {path} belongs to a different "
                    "change.")
            db.verify_backup(store, row)

    def _proposal_conversation(self, proposal: dict) -> str | None:
        job_id = proposal.get("job_id")
        if not job_id:
            return None
        row = self.conn.execute("SELECT chat_id FROM jobs WHERE job_id=?",
                                (job_id,)).fetchone()
        return row["chat_id"] if row else None

    def _check_proposal_conversation(self, proposal: dict,
                                     conversation_id: str | None) -> str | None:
        owner = self._proposal_conversation(proposal)
        if conversation_id is None:
            return owner
        conversation_id = self.conversation(conversation_id)
        if owner != conversation_id:
            raise CodeError("mismatch", "That change belongs to another conversation.", 409)
        return owner

    def _run_operation(self, operation: dict, *, allowed_by: str,
                       approval_id: str | None = None) -> dict:
        """Carry out one authorised write record, from wherever it got to.

        Called by `apply` and again by `resume_writes` after a restart. It
        never consults an approval: the authority question was settled when the
        record was created, and re-checking a consumed approval here would fail
        exactly the recovery this record exists to make possible.
        """
        repo_id, proposal_id = operation["repo_id"], operation["proposal_id"]
        operation_id = operation["operation_id"]
        proposal = db.get_proposal(self.conn, proposal_id, self.workspace_id)
        conversation_id = self._proposal_conversation(proposal) if proposal else None

        # The backup happens HERE rather than in `apply`, because this is the
        # single place that writes. `resume_writes` reaches this method
        # directly after a restart, and an operation recovered that way must
        # not be able to replace a file whose original was never copied.
        if proposal is not None and stored_target(proposal) == TARGET_LOCAL:
            try:
                self._back_up_originals(
                    operation, proposal,
                    db.proposal_edit_contents(self.conn, proposal_id))
            except db.BackupError as exc:
                db.set_operation_state(self.conn, operation_id, "failed", str(exc))
                db.record_audit(
                    self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                    action=policy.ACTION_WRITE, outcome="failed",
                    conversation_id=conversation_id,
                    approval_id=approval_id,
                    detail={"reason": str(exc), "proposal_id": proposal_id,
                            "stage": "backup"})
                # Accurate about what is left: no file changed, and this
                # authorisation is finished. In Ask and Partial mode that
                # means approving again; in Full mode, asking again.
                raise CodeError(
                    "backup_failed",
                    "The originals could not be backed up, so no file was "
                    f"changed. This attempt has ended — ask for the change "
                    f"again once there is room to store the originals. {exc}",
                    409) from exc

        db.set_operation_state(self.conn, operation_id, "applying")
        root = self._root(repo_id)
        by_path = {edit["path"]: edit
                   for edit in db.proposal_edit_contents(self.conn, proposal_id)}
        results, applied = [], 0
        for planned in operation["files"]:
            path = planned["path"]
            if planned["state"] == "applied":
                results.append({"path": path, "state": "applied"})
                applied += 1
                continue
            edit = by_path.get(path)
            if edit is None:
                detail = "The reviewed replacement is no longer stored."
                db.set_operation_file(self.conn, operation_id, path, "failed", detail)
                results.append({"path": path, "state": "failed", "detail": detail})
                continue
            if hashlib.sha256(edit["content"].encode("utf-8")).hexdigest() \
                    != planned["after_sha256"]:
                detail = "The stored replacement no longer matches the reviewed change."
                db.set_edit_result(self.conn, edit["edit_id"], "failed", detail)
                db.set_operation_file(self.conn, operation_id, path, "failed", detail)
                results.append({"path": path, "state": "failed", "detail": detail})
                continue

            # Recovery, and the reason the base and after digests are stored.
            #
            #   already at the AFTER hash -> a previous run wrote it; record it
            #                                and do NOT write again;
            #   still at the BASE hash    -> write it now;
            #   anything else             -> a third party changed the file, so
            #                                stop rather than overwrite content
            #                                nobody reviewed.
            current = self._current_digest(root, path)
            if current == planned["after_sha256"]:
                db.set_edit_result(self.conn, edit["edit_id"], "applied")
                db.set_operation_file(self.conn, operation_id, path, "applied",
                                      "already written before this run")
                results.append({"path": path, "state": "applied"})
                applied += 1
                continue
            if current is not None and current != planned["base_sha256"]:
                detail = ("That file changed since the proposal was reviewed, so "
                          "it was left alone.")
                db.set_edit_result(self.conn, edit["edit_id"], "rejected_stale", detail)
                db.set_operation_file(self.conn, operation_id, path,
                                      "rejected_stale", detail)
                db.record_audit(self.conn, workspace_id=self.workspace_id,
                                repo_id=repo_id, action=policy.ACTION_WRITE,
                                outcome="rejected_stale", approval_id=approval_id,
                                conversation_id=conversation_id,
                                detail={"path": path, "reason": detail})
                results.append({"path": path, "state": "rejected_stale",
                                "detail": detail})
                continue

            try:
                identity = repo.replace_text_file(
                    root, path, expected_sha256=planned["base_sha256"],
                    text=edit["content"])
            except repo.RepositoryError as exc:
                state = "rejected_stale" if exc.code == "stale" else "failed"
                db.set_edit_result(self.conn, edit["edit_id"], state, str(exc))
                db.set_operation_file(self.conn, operation_id, path, state, str(exc))
                db.record_audit(self.conn, workspace_id=self.workspace_id,
                                repo_id=repo_id, action=policy.ACTION_WRITE,
                                outcome=state, approval_id=approval_id,
                                conversation_id=conversation_id,
                                detail={"path": path, "reason": str(exc)})
                results.append({"path": path, "state": state, "detail": str(exc)})
                continue
            db.set_edit_result(self.conn, edit["edit_id"], "applied")
            db.set_operation_file(self.conn, operation_id, path, "applied")
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=policy.ACTION_WRITE, outcome="applied",
                            approval_id=approval_id,
                            conversation_id=conversation_id,
                            detail={"path": path, "after_sha256": identity.sha256,
                                    "allowed_by": allowed_by})
            results.append({"path": path, "state": "applied"})
            applied += 1

        total = len(operation["files"])
        state = ("applied" if applied == total
                 else "partially_applied" if applied else "failed")
        db.set_operation_state(self.conn, operation_id, state)
        db.set_proposal_state(self.conn, proposal_id, state)
        return {"proposal_id": proposal_id, "operation_id": operation_id,
                "state": state, "results": results, "applied": applied,
                "total": total,
                "atomicity": "Each file was replaced on its own. Refinix does not "
                             "claim the whole set changed together."}

    def _current_digest(self, root, relative: str) -> str | None:
        """What is on disk now, or None if the file is unreadable."""
        try:
            text, _identity = repo.read_text_file(root, relative)
        except repo.RepositoryError:
            return None
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def resume_writes(self) -> list[dict]:
        """Finish any authorised write that a restart interrupted.

        Exactly one terminal outcome per operation: a resumed run either
        completes it, reports it partially applied, or fails it. A file already
        at its after-hash is recorded rather than rewritten, so a restart in
        the middle of a multi-file change never writes anything twice.
        """
        resumed = []
        for operation in db.unfinished_operations(self.conn, self.workspace_id):
            try:
                resumed.append(self._run_operation(operation,
                                                   allowed_by="resumed_after_restart",
                                                   approval_id=operation["approval_id"]))
            except CodeError as exc:
                db.set_operation_state(self.conn, operation["operation_id"],
                                       "failed", str(exc))
                resumed.append({"operation_id": operation["operation_id"],
                                "state": "failed", "detail": str(exc)})
        return resumed

    # -- decisions and audit ----------------------------------------------

    def decide(self, approval_id: str, approved: bool,
               conversation_id: str | None = None) -> dict:
        if not isinstance(approved, bool):
            raise CodeError("bad_decision", "A decision must be yes or no.")
        pending = db.public_approval(
            self.conn, approval_id, self.workspace_id)
        if pending and pending.get("conversation_id"):
            if not conversation_id:
                # Compatibility for approvals created before named Code
                # conversations: those belong to the one workspace Code chat.
                legacy = db.code_chat(self.conn, self.workspace_id)
                if pending["conversation_id"] != legacy:
                    raise CodeError(
                        "missing_conversation",
                        "That Code approval must be decided in its conversation.", 409)
                conversation_id = legacy
            else:
                conversation_id = self.conversation(conversation_id)
            if pending["conversation_id"] != conversation_id:
                raise CodeError(
                    "mismatch", "That approval belongs to another conversation.", 409)
        try:
            record = db.decide_approval(self.conn, approval_id, self.workspace_id,
                                        approved=approved, actor_id=self.c.node_id)
        except db.ApprovalError as exc:
            raise CodeError(exc.code, str(exc), 409) from exc
        db.record_audit(self.conn, workspace_id=self.workspace_id,
                        repo_id=record["repo_id"], action=record["action"],
                        outcome="approved" if approved else "denied",
                        conversation_id=record.get("conversation_id"),
                        approval_id=approval_id, detail={"target": record["target"]})
        return record

    def state(self, repo_id: str | None = None,
              conversation_id: str | None = None) -> dict:
        """Everything the Code surface needs, with no absolute path in it.

        Scoped to one Code conversation when the surface names one, so a fresh
        conversation does not inherit the project's previous proposal.
        """
        repositories = self.repositories()
        conversation = None
        if conversation_id:
            conversation_id = self.conversation(conversation_id)
            conversation = db.code_conversation(
                self.conn, conversation_id, self.workspace_id)
            if repo_id is not None:
                self._repository(repo_id)
                active = repo_id
            else:
                active = (conversation["repo_id"]
                          if conversation and conversation["project_available"] else None)
        else:
            active = repo_id or (repositories[0]["repo_id"] if repositories else None)
        proposal = db.latest_proposal(self.conn, active, self.workspace_id,
                                      conversation_id) if active else None
        validation = (db.latest_validation(self.conn, proposal["proposal_id"],
                                           self.workspace_id) if proposal else None)
        # A local proposal has no sandbox result, and one is never invented for
        # it. The surface is told what is true so it can say so.
        #
        # A target this build does not recognise must not make the whole
        # surface unreadable: `state` only reports. The proposal is marked
        # unusable here and every path that could act on it still refuses.
        target_note = None
        try:
            target = stored_target(proposal) if proposal else None
        except CodeError as exc:
            target, target_note = None, str(exc)
        local_proposal = bool(proposal) and target == TARGET_LOCAL
        if local_proposal or target_note:
            validation = None
        return {
            "repositories": repositories,
            "active": active,
            "modes": policy.mode_options(),
            "unavailable": policy.unavailable_actions(),
            "conversation": conversation,
            "pending_approvals": db.pending_approvals(
                self.conn, self.workspace_id, active, conversation_id),
            "proposal": proposal,
            "validation": validation,
            # Said in the state, so the surface reports what is true rather
            # than deciding for itself what a missing validation means.
            "execution_target": target,
            "target_note": target_note,
            "validation_note": (target_note if target_note
                                else LOCAL_VALIDATION_NOTE if local_proposal
                                else None),
            "can_undo": local_proposal and bool(
                db.proposal_backups(self.conn, proposal["proposal_id"],
                                    self.workspace_id)),
            "audit": db.recent_audit(
                self.conn, self.workspace_id, active,
                conversation_id=conversation_id),
            "limits": {"max_files": repo.MAX_SELECTED_FILES,
                       "max_file_bytes": repo.MAX_FILE_BYTES,
                       "max_total_bytes": repo.MAX_TOTAL_BYTES},
            # One answer for the whole surface: without descriptor-relative
            # traversal nothing here is safe, reading included.
            "code_supported": repo.descriptor_traversal_supported(),
            "writes_supported": repo.descriptor_traversal_supported(),
            "platform_note": None if repo.descriptor_traversal_supported() else repo.PLATFORM_NOTE,
        }
