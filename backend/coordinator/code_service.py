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
import threading
import time

from backend.coordinator import codeflow, db, policy, repo, runtime

# One proposal is one bounded local model call.
PROPOSAL_DEADLINE_SECONDS = 240
PROPOSAL_NUM_PREDICT = 2048


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


class CodeService:
    def __init__(self, coordinator):
        self.c = coordinator
        self._cancels: dict[str, threading.Event] = {}
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

    def _gate(self, repo_id: str, action: str, *, digest: str, target: str,
              approval_id: str | None, payload: dict, proposal_id: str | None = None):
        """The one place an access mode decides anything.

        Returns the audit outcome to record on success. Raises `CodeError` for
        a denial and `ApprovalNeeded` when the person has to decide first.
        """
        record = self._repository(repo_id)
        mode = record["mode"]
        decision = policy.decide(mode, action)
        if decision.denied:
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=action, outcome="denied", mode=mode,
                            detail={"reason": decision.reason, "target": target})
            raise CodeError("denied", decision.reason, 403)

        if decision.automatic:
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=action, outcome="allowed_automatically", mode=mode,
                            detail={"reason": decision.reason, "target": target,
                                    "digest": digest})
            return "allowed_automatically"

        if approval_id:
            try:
                claimed = db.claim_approval(self.conn, approval_id, self.workspace_id,
                                            action, digest, repo_id=repo_id,
                                            proposal_id=proposal_id)
            except db.ApprovalError as exc:
                outcome = {"expired": "expired", "denied": "denied"}.get(exc.code, "rejected_stale")
                db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                                action=action, outcome=outcome, mode=mode,
                                approval_id=approval_id,
                                detail={"reason": str(exc), "target": target})
                raise CodeError(exc.code, str(exc), 409) from exc
            if claimed.get("repo_id") != repo_id:
                raise CodeError("mismatch", "That approval was for another project.", 409)
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=action, outcome="approved", mode=mode,
                            approval_id=approval_id,
                            detail={"target": target, "digest": digest})
            return "approved"

        approval = db.request_approval(
            self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
            proposal_id=proposal_id, action=action, target=target,
            action_sha256=digest,
            payload={**payload, "repo_id": repo_id, "repo_name": record["name"],
                     "mode": mode})
        db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                        action=action, outcome="awaiting_approval", mode=mode,
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

    def forget(self, repo_id: str) -> dict:
        if not db.forget_repository(self.conn, repo_id, self.workspace_id):
            raise CodeError("unknown_repository",
                            "That project is not connected to this workspace.", 404)
        return {"disconnected": repo_id}

    # -- listing ----------------------------------------------------------

    def files(self, repo_id: str, approval_id: str | None = None) -> dict:
        self._require_platform(repo_id)
        digest = codeflow.read_digest(repo_id, ["<listing>"])
        self._gate(repo_id, policy.ACTION_LIST, digest=digest, target="file listing",
                   approval_id=approval_id,
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

    def propose(self, repo_id: str, request: str, paths: list[str],
                approval_id: str | None = None) -> dict:
        """Read the selection, ask the local model, validate, and store a diff.

        Nothing is written here. The result is a reviewable proposal.
        """
        self._require_platform(repo_id)
        if not isinstance(request, str) or not request.strip():
            raise CodeError("no_request", "Describe the change you want.")
        if not isinstance(paths, list) or not paths:
            # Refuse before the gate, so an empty request cannot leave a
            # pointless approval waiting for the person in Ask mode.
            raise CodeError("no_selection", "Select at least one file to change.")
        try:
            normalised = sorted({repo.normalise_relative(p) for p in paths})
        except repo.RepositoryError as exc:
            raise CodeError(exc.code, str(exc)) from exc
        digest = codeflow.read_digest(repo_id, normalised)

        # In Ask mode this one approval covers exactly this immutable batch of
        # reads plus sending them to the local model. A later added path
        # changes the digest and needs a new approval.
        # One gate for one action: reading the selection and sending it to the
        # local model. In Ask mode a single approval covers exactly this
        # immutable batch, and the audit below records that same authorisation
        # rather than calling the model call automatic afterwards.
        cancel = threading.Event()
        with self._lock:
            if repo_id in self._cancels:
                raise CodeError("busy", "Wait for this project's proposal to finish or stop it.", 409)
            self._cancels[repo_id] = cancel
        try:
            authorised = self._gate(
                repo_id, policy.ACTION_READ, digest=digest,
                target=f"{len(normalised)} file(s)", approval_id=approval_id,
                payload={"paths": normalised,
                         "summary": policy.ACTION_LABELS[policy.ACTION_READ].capitalize()})
            root = self._root(repo_id)
            selection = self._read_selection(root, normalised)
            reply, reasoning = self._ask_model(
                codeflow.build_messages(request, selection), cancel)
            try:
                parsed = codeflow.parse_proposal(reply, selection)
            except codeflow.ProposalError as first:
                # Exactly one bounded repair attempt, on the same context.
                if first.code not in ("not_json", "not_object", "unknown_fields"):
                    raise
                retry, _ = self._ask_model(
                    codeflow.repair_messages(
                        codeflow.build_messages(request, selection), reply), cancel)
                parsed = codeflow.parse_proposal(retry, selection)
        except codeflow.ProposalError as exc:
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=policy.ACTION_READ, outcome="failed",
                            approval_id=approval_id,
                            detail={"reason": str(exc), "code": exc.code})
            raise CodeError(exc.code, str(exc), 422) from exc
        except runtime.RuntimeUnavailable as exc:
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=policy.ACTION_READ, outcome="failed",
                            approval_id=approval_id, detail={"reason": str(exc)})
            raise CodeError("runtime", str(exc), 503) from exc
        finally:
            with self._lock:
                if self._cancels.get(repo_id) is cancel:
                    self._cancels.pop(repo_id)

        write_digest = codeflow.action_digest(repo_id, parsed["edits"])
        proposal = db.create_proposal(
            self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
            job_id=None, attempt_id=None, request=request,
            summary=parsed["summary"], digest=write_digest, edits=parsed["edits"])
        # `authorised` is what the gate actually decided — `approved` with the
        # approval id in Ask mode, `allowed_automatically` otherwise.
        db.record_audit(
            self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
            action="model.proposed", outcome=authorised, approval_id=approval_id,
            detail={"proposal_id": proposal["proposal_id"],
                    "authorised_by": policy.ACTION_READ,
                    "edits": len(parsed["edits"]),
                    "model": self.c.active_model(),
                    "reasoning_enabled": reasoning, "digest": write_digest})
        return proposal

    def _ask_model(self, messages, cancel: threading.Event) -> tuple[str, bool]:
        """One bounded local model call. Reasoning is not collected or stored."""
        model = self.c.active_model()
        reasoning = db.get_reasoning(self.conn, model)
        deadline = time.monotonic() + PROPOSAL_DEADLINE_SECONDS
        collected, metrics = [], {}
        for kind, payload in runtime.stream_chat(
                messages, model=model, think=reasoning,
                num_predict=PROPOSAL_NUM_PREDICT,
                should_cancel=lambda: cancel.is_set() or time.monotonic() > deadline
                or self.c.stopping.is_set()):
            if kind == "delta":
                collected.append(payload)
            elif kind == "cancelled":
                raise CodeError("cancelled", "That request was stopped.", 409)
            elif kind == "done":
                metrics = payload
        if metrics.get("done_reason") != "stop":
            raise runtime.RuntimeUnavailable(
                "the runtime did not finish the code proposal cleanly")
        return "".join(collected), reasoning

    # -- apply ------------------------------------------------------------

    def apply(self, repo_id: str, proposal_id: str,
              approval_id: str | None = None) -> dict:
        """Apply a stored proposal, one exact atomic file replacement at a time."""
        self._require_platform(repo_id)
        proposal = db.get_proposal(self.conn, proposal_id, self.workspace_id)
        if proposal is None or proposal["repo_id"] != repo_id:
            raise CodeError("unknown_proposal", "That proposal no longer exists.", 404)
        if proposal["state"] == "applied":
            raise CodeError("already_applied", "That change was already applied.", 409)
        if not proposal["edits"]:
            raise CodeError("no_edits", "That proposal contains no file changes.")
        paths = [e["path"] for e in proposal["edits"]]
        outcome = self._gate(
            repo_id, policy.ACTION_WRITE, digest=proposal["digest"],
            target=", ".join(paths), approval_id=approval_id,
            proposal_id=proposal_id,
            payload={"paths": paths, "summary": proposal["summary"],
                     "proposal_id": proposal_id})

        root = self._root(repo_id)
        contents = db.proposal_edit_contents(self.conn, proposal_id)
        results, applied = [], 0
        for edit in contents:
            if edit["state"] == "applied":
                results.append({"path": edit["path"], "state": "applied"})
                applied += 1
                continue
            if hashlib.sha256(edit["content"].encode("utf-8")).hexdigest() != edit["after_sha256"]:
                detail = "The stored replacement no longer matches the reviewed change."
                db.set_edit_result(self.conn, edit["edit_id"], "failed", detail)
                results.append({"path": edit["path"], "state": "failed",
                                "detail": detail})
                continue
            try:
                identity = repo.replace_text_file(
                    root, edit["path"], expected_sha256=edit["base_sha256"],
                    text=edit["content"])
            except repo.RepositoryError as exc:
                state = "rejected_stale" if exc.code == "stale" else "failed"
                db.set_edit_result(self.conn, edit["edit_id"], state, str(exc))
                db.record_audit(self.conn, workspace_id=self.workspace_id,
                                repo_id=repo_id, action=policy.ACTION_WRITE,
                                outcome=state, approval_id=approval_id,
                                detail={"path": edit["path"], "reason": str(exc)})
                results.append({"path": edit["path"], "state": state,
                                "detail": str(exc)})
                continue
            db.set_edit_result(self.conn, edit["edit_id"], "applied")
            db.record_audit(self.conn, workspace_id=self.workspace_id, repo_id=repo_id,
                            action=policy.ACTION_WRITE, outcome="applied",
                            approval_id=approval_id,
                            detail={"path": edit["path"],
                                    "after_sha256": identity.sha256,
                                    "allowed_by": outcome})
            results.append({"path": edit["path"], "state": "applied"})
            applied += 1

        # Per-file truth. The filesystem gives one atomic replacement per file,
        # not one atomic batch, so a mixed result is reported as a mixed result.
        state = ("applied" if applied == len(contents)
                 else "partially_applied" if applied else "failed")
        db.set_proposal_state(self.conn, proposal_id, state)
        return {"proposal_id": proposal_id, "state": state, "results": results,
                "applied": applied, "total": len(contents),
                "atomicity": "Each file was replaced on its own. Refinix does not "
                             "claim the whole set changed together."}

    # -- decisions and audit ----------------------------------------------

    def decide(self, approval_id: str, approved: bool) -> dict:
        if not isinstance(approved, bool):
            raise CodeError("bad_decision", "A decision must be yes or no.")
        try:
            record = db.decide_approval(self.conn, approval_id, self.workspace_id,
                                        approved=approved, actor_id=self.c.node_id)
        except db.ApprovalError as exc:
            raise CodeError(exc.code, str(exc), 409) from exc
        db.record_audit(self.conn, workspace_id=self.workspace_id,
                        repo_id=record["repo_id"], action=record["action"],
                        outcome="approved" if approved else "denied",
                        approval_id=approval_id, detail={"target": record["target"]})
        return record

    def state(self, repo_id: str | None = None) -> dict:
        """Everything the Code surface needs, with no absolute path in it."""
        repositories = self.repositories()
        active = repo_id or (repositories[0]["repo_id"] if repositories else None)
        proposal = db.latest_proposal(self.conn, active, self.workspace_id) if active else None
        return {
            "repositories": repositories,
            "active": active,
            "modes": policy.mode_options(),
            "unavailable": policy.unavailable_actions(),
            "pending_approvals": db.pending_approvals(self.conn, self.workspace_id, active),
            "proposal": proposal,
            "audit": db.recent_audit(self.conn, self.workspace_id, active),
            "limits": {"max_files": repo.MAX_SELECTED_FILES,
                       "max_file_bytes": repo.MAX_FILE_BYTES,
                       "max_total_bytes": repo.MAX_TOTAL_BYTES},
            # One answer for the whole surface: without descriptor-relative
            # traversal nothing here is safe, reading included.
            "code_supported": repo.descriptor_traversal_supported(),
            "writes_supported": repo.descriptor_traversal_supported(),
            "platform_note": None if repo.descriptor_traversal_supported() else repo.PLATFORM_NOTE,
        }
