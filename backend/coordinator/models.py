"""Which models Refinix supports, and what is actually true of each one here.

Until now the model list was whatever the local runtime happened to report.
That answers "what is installed" and nothing else, so the product could not
tell a person that a model it supports is *missing* — only that a name was
absent from a list — and it could not distinguish a model whose provenance
Refinix has recorded from one someone pulled by hand.

`docs/PROJECT.md` 5 and `docs/model-catalog.md` ask for four separable facts,
and this module is where they live:

* **installed** — the local runtime lists it now;
* **supported but absent** — Refinix records a manifest for it and it is not
  installed here;
* **unlisted** — installed here, with no recorded provenance. 12.4's rule is
  explicit: *installed runtime inventory does not automatically become a
  trusted supported catalogue entry*, so such a model is usable and is plainly
  labelled as unverified rather than quietly promoted;
* **unavailable** — the runtime did not answer, so nothing about any model is
  known. Never reported as "none installed".

Whether Refinix *vouches* for a model is a separate answer, carried by
`provenance`, so an installed model with no recorded source stays usable and
plainly labelled rather than being quietly promoted or silently refused.

**The catalogue is small on purpose.** It holds the one model whose source,
licence, manifest digest, layers and runtime floor were recorded from the
artifact itself. Everything else in `docs/model-catalog.md` is a research
candidate with unresolved provenance, and `model-catalog.md` says those are
not supported download offers — so they are not offered here. A short honest
catalogue is the requirement; a long speculative one would be the failure.

**Nothing in this module downloads, installs, removes or calls a model.** A
missing model produces the exact command the person can run themselves, the
same way the startup sequence already does. Removal is likewise the runtime's
own operation: what Refinix owns is telling the person what a removal would
break before they do it, and never deleting a chat because a model went away.

**A self-test belongs to the exact manifest that passed it.** A result is
stored with the digest it was observed against, so replacing a model's bytes
under the same tag invalidates it rather than inheriting a pass.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

# Workflow scopes a model can be selected for. The same strings `MODEL_DEFAULTS`
# uses, so a catalogue entry and a selection cannot drift apart.
CHAT = "chat"
CODE = "code"
DOCUMENTS_GENERATE = "documents.generate"
DOCUMENTS_OCR = "documents.ocr"

# What the interface may say about one model on this computer.
INSTALLED = "installed"
ABSENT = "absent"
UNLISTED = "unlisted"
UNAVAILABLE = "unavailable"

# Evidence strength, kept as separate words because `docs/model-catalog.md`
# requires measured, documentation-only and unverified to stay distinguishable.
VERIFIED = "verified"
UNVERIFIED = "unverified"
UNRESOLVED = "unresolved"
MISMATCH = "mismatch"
NOT_OBSERVED = "not_observed"


@dataclass(frozen=True)
class ModelFile:
    """One file of a managed-engine model, pinned by size and SHA-256.

    A model split across several GGUF files lists every part, in order, with
    its original name: the first is `weights`, the rest `weights-part`. The
    engine is given the first and finds the others beside it by name.
    """

    role: str            # "weights" | "weights-part" | "projector"
    name: str
    size: int
    sha256: str
    url: str

    def as_dict(self) -> dict:
        return {"role": self.role, "name": self.name, "size": self.size,
                "sha256": self.sha256, "url": self.url}


def manifest_digest(model_id: str, revision: str | None,
                    files: tuple[ModelFile, ...]) -> str:
    """The Refinix model-manifest identity: exact files, not a name.

    Canonical JSON (sorted keys, no whitespace) of the model id, its pinned
    source revision and every file's role, name, size and SHA-256. The GGUF
    hashes cover the embedded tokenizer and chat template; a template override
    would have to join this list.
    """
    body = {"model_id": model_id, "revision": revision,
            "files": [{"role": f.role, "name": f.name, "size": f.size,
                       "sha256": f.sha256} for f in files]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Entry:
    """One curated model, with the provenance that was actually recorded.

    Every field here was read from the artifact or its manifest and written
    down in `docs/model-catalog.md`. A field nobody observed is `None`; it is
    never filled in from a model's name, its family or its upstream project.
    """

    id: str
    role: str
    scopes: tuple[str, ...]
    source: str
    licence: str | None
    manifest_sha256: str | None
    format: str | None
    parameters: str | None
    storage_bytes: int | None
    minimum_runtime: str | None
    evidence: str
    evidence_state: str = VERIFIED
    setup_command: str = ""
    # Which engine can run these bytes. The developer baseline is an Ollama
    # registry artifact; the managed engine loads pinned upstream GGUF files.
    engine: str = "ollama"
    files: tuple[ModelFile, ...] = ()
    revision: str | None = None
    display_name: str | None = None
    sampling: tuple[tuple[str, float], ...] = ()
    # Library metadata, read from the publisher's repository; never inferred
    # from a model's name.
    publisher: str | None = None
    base_model: str | None = None
    quantizer: str | None = None
    repo: str | None = None
    architecture: str | None = None
    context_length: int | None = None
    # Task strengths the publisher's own model card states, with that card.
    # Routing may prefer them; they are published claims, not measurements.
    hints: tuple[str, ...] = ()
    hint_source: str | None = None
    gated: bool = False
    # An explicit, cited statement that the model does only these tasks (for
    # example document OCR). Never inferred: an entry without one is not
    # limited, whatever its strengths.
    limited_to: tuple[str, ...] = ()
    # Task tags the model's own repository publishes (Hugging Face `tags` and
    # `pipeline_tag`), recorded when a person resolved it in Browse. Weaker
    # evidence than a curated card citation; mapped by `TAG_STRENGTHS`.
    repo_tags: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "id": self.id, "role": self.role, "scopes": list(self.scopes),
            "source": self.source, "licence": self.licence,
            "manifest_sha256": self.manifest_sha256, "format": self.format,
            "parameters": self.parameters, "storage_bytes": self.storage_bytes,
            "minimum_runtime": self.minimum_runtime,
            "evidence": self.evidence, "evidence_state": self.evidence_state,
            "setup_command": self.setup_command or None,
            "engine": self.engine, "revision": self.revision,
            "display_name": self.display_name or self.id,
            "files": [f.as_dict() for f in self.files],
            "download_bytes": sum(f.size for f in self.files) or None,
            "publisher": self.publisher, "base_model": self.base_model,
            "quantizer": self.quantizer, "repo": self.repo,
            "architecture": self.architecture,
            "context_length": self.context_length,
            "hints": list(self.hints), "hint_source": self.hint_source,
            "gated": self.gated, "limited_to": list(self.limited_to),
            "repo_tags": list(self.repo_tags),
        }

    def weights_bytes(self) -> int | None:
        """The model's weight files, without a vision projector."""
        size = sum(f.size for f in self.files if f.role != "projector")
        return size or self.storage_bytes


# The managed engine's first model: the same Qwen3.5-4B family as the baseline,
# as pinned upstream-format GGUF files. Upstream llama.cpp b11390 refuses the
# Ollama registry blob (`qwen35.rope.dimension_sections has wrong array length`,
# observed 2026-10-04), so the managed engine cannot reuse it. No official Qwen
# or ggml-org GGUF exists; these are the quantizer's files for the official
# Apache-2.0 weights, pinned by repository commit, size and SHA-256 read from
# the Hugging Face API on 2026-10-04.
MANAGED_MAIN_REVISION = "e87f176479d0855a907a41277aca2f8ee7a09523"
_MANAGED_MAIN_BASE = ("https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/"
                      + MANAGED_MAIN_REVISION + "/")
MANAGED_MAIN_FILES = (
    ModelFile("weights", "Qwen3.5-4B-Q4_K_M.gguf", 2_740_937_888,
              "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4",
              _MANAGED_MAIN_BASE + "Qwen3.5-4B-Q4_K_M.gguf"),
    ModelFile("projector", "mmproj-F16.gguf", 672_423_616,
              "cd88edcf8d031894960bb0c9c5b9b7e1fea6ebee02b9f7ce925a00d12891f864",
              _MANAGED_MAIN_BASE + "mmproj-F16.gguf"),
)
MANAGED_MAIN = "qwen3.5-4b-q4_k_m"

# The supported catalogue. One artifact per engine, each inspected.
CATALOGUE: tuple[Entry, ...] = (
    Entry(
        id="qwen3.5:4b-q4_K_M",
        role="Main engine",
        scopes=(CHAT, CODE, DOCUMENTS_GENERATE),
        source="registry.ollama.ai/library/qwen3.5, tag 4b-q4_K_M",
        licence="Apache-2.0 (licence layer present in the manifest)",
        manifest_sha256=
        "2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd",
        format="GGUF, Q4_K_M",
        parameters="4.7B reported by the image config",
        storage_bytes=3_389_971_840,
        minimum_runtime="Ollama >= 0.17.1",
        evidence=("Integrity verified from the manifest and blobs, with bounded "
                  "inference observed on the qualification devices. That is a "
                  "fixed-prompt smoke check, not a scored quality result."),
        evidence_state=VERIFIED,
        setup_command="ollama pull qwen3.5:4b-q4_K_M",
        # The same Qwen3.5-4B model the Refinix-engine entry below quantizes:
        # its publisher's card lists general multimodal use, and Ollama's
        # library page describes the family as multimodal (text and image
        # input), read 2026-10-07. Bound to this exact manifest digest.
        publisher="Qwen", base_model="Qwen/Qwen3.5-4B",
        hints=("general", "vision"),
        hint_source="https://huggingface.co/Qwen/Qwen3.5-4B",
    ),
    Entry(
        id=MANAGED_MAIN,
        display_name="Qwen3.5 4B (Q4_K_M)",
        role="Main engine",
        scopes=(CHAT, CODE, DOCUMENTS_GENERATE),
        source=("huggingface.co/unsloth/Qwen3.5-4B-GGUF at " + MANAGED_MAIN_REVISION
                + " — a quantization of Qwen/Qwen3.5-4B at "
                "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"),
        licence="Apache-2.0 (base model LICENSE; the quantization repository "
                "declares Apache-2.0)",
        manifest_sha256=manifest_digest(MANAGED_MAIN, MANAGED_MAIN_REVISION,
                                        MANAGED_MAIN_FILES),
        format="GGUF Q4_K_M weights with an F16 vision projector",
        parameters="4B (upstream model card)",
        storage_bytes=sum(f.size for f in MANAGED_MAIN_FILES),
        minimum_runtime="Refinix engine (llama.cpp b11390, pinned)",
        evidence=("Integrity verified: both files were downloaded from the pinned "
                  "revision on 2026-10-04 and re-hashed locally, matching the "
                  "published sizes and SHA-256. Every later download or import is "
                  "re-hashed the same way. Third-party quantization of the official "
                  "weights, because no official GGUF is published. Workflow "
                  "qualification is recorded separately per engine build and "
                  "hardware tier."),
        evidence_state=VERIFIED,
        engine="llama.cpp",
        files=MANAGED_MAIN_FILES,
        revision=MANAGED_MAIN_REVISION,
        # The sampling the baseline ran with (Ollama params layer for this
        # model), so engine parity compares the same decoding.
        sampling=(("temperature", 1.0), ("top_k", 20), ("top_p", 0.95),
                  ("presence_penalty", 1.5)),
        publisher="Qwen", base_model="Qwen/Qwen3.5-4B", quantizer="unsloth",
        repo="unsloth/Qwen3.5-4B-GGUF", architecture="qwen35",
        context_length=262144, hints=("general", "vision"),
        hint_source="https://huggingface.co/Qwen/Qwen3.5-4B",
    ),
)

# --------------------------------------------------------------------------
# The download library
# --------------------------------------------------------------------------
#
# Further Refinix-engine downloads, chosen across publishers and sizes so a
# person can pick beyond the first recommendation. Every revision, file name,
# size and SHA-256 below was read from the Hugging Face API
# (`/api/models/<repo>?blobs=true`) on 2026-10-06 and copied exactly; none was
# typed from memory. Listing one is not a claim that it was downloaded,
# loaded, measured or that it fits a given computer: those are separate facts
# the interface reports as they become known. Qwen, Gemma, GLM, DeepSeek and
# GPT-OSS are examples, not a closed list — Browse finds others.

LISTED = "listed"
LIBRARY_READ_ON = "2026-10-06"


def _hf(repo: str, revision: str, *files: tuple[str, str, int, str]) \
        -> tuple[ModelFile, ...]:
    base = f"https://huggingface.co/{repo}/resolve/{revision}/"
    return tuple(ModelFile(role, name, size, sha, base + name)
                 for role, name, size, sha in files)


def _listed(model_id: str, display: str, repo: str, revision: str, *,
            files: tuple[ModelFile, ...], licence: str, publisher: str,
            base_model: str, quantizer: str | None, architecture: str,
            context_length: int, parameters: str, fmt: str,
            hints: tuple[str, ...], hint_source: str,
            scopes: tuple[str, ...] = (CHAT, CODE, DOCUMENTS_GENERATE)) -> Entry:
    converter = (f" — a {quantizer} quantization of {base_model}" if quantizer
                 else f" — {publisher}'s own GGUF of {base_model}")
    return Entry(
        id=model_id, display_name=display, role="Library model", scopes=scopes,
        source=f"huggingface.co/{repo} at {revision}{converter}",
        licence=licence, manifest_sha256=manifest_digest(model_id, revision, files),
        format=fmt, parameters=parameters,
        storage_bytes=sum(f.size for f in files), minimum_runtime=None,
        evidence=(f"Listed from the Hugging Face API at revision {revision}, read "
                  f"{LIBRARY_READ_ON}: file sizes and SHA-256 as published. Not "
                  "downloaded, loaded or measured by Refinix. A download is "
                  "re-hashed against these values before it is used."),
        evidence_state=LISTED, engine="llama.cpp", files=files, revision=revision,
        publisher=publisher, base_model=base_model, quantizer=quantizer,
        repo=repo, architecture=architecture, context_length=context_length,
        hints=hints, hint_source=hint_source)


LIBRARY: tuple[Entry, ...] = (
    _listed(
        "gemma-3-4b-it-q4_k_m", "Gemma 3 4B instruct (Q4_K_M)",
        "ggml-org/gemma-3-4b-it-GGUF", "d0976223747697cb51e056d85c532013931fe52e",
        files=_hf("ggml-org/gemma-3-4b-it-GGUF", "d0976223747697cb51e056d85c532013931fe52e",
                  ("weights", "gemma-3-4b-it-Q4_K_M.gguf", 2_489_757_856,
                   "882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863"),
                  ("projector", "mmproj-model-f16.gguf", 851_251_104,
                   "8c0fb064b019a6972856aaae2c7e4792858af3ca4561be2dbf649123ba6c40cb")),
        licence="Gemma Terms of Use (repository licence tag: gemma) — not an "
                "OSI open-source licence; read it before use",
        publisher="Google", base_model="google/gemma-3-4b-it", quantizer="ggml-org",
        architecture="gemma3", context_length=131072, parameters="3.9B (GGUF metadata)",
        fmt="GGUF Q4_K_M weights with an F16 vision projector",
        hints=("general", "vision"),
        hint_source="https://huggingface.co/google/gemma-3-4b-it"),
    _listed(
        "qwen2.5-coder-7b-instruct-q4_k_m", "Qwen2.5 Coder 7B instruct (Q4_K_M)",
        "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", "13fb94bfda8c8cf22497dc57b78f391a9acb426a",
        files=_hf("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
                  "13fb94bfda8c8cf22497dc57b78f391a9acb426a",
                  ("weights", "qwen2.5-coder-7b-instruct-q4_k_m.gguf", 4_683_073_536,
                   "509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c")),
        licence="Apache-2.0", publisher="Qwen",
        base_model="Qwen/Qwen2.5-Coder-7B-Instruct", quantizer=None,
        architecture="qwen2", context_length=131072, parameters="7.6B (GGUF metadata)",
        fmt="GGUF Q4_K_M", hints=("code",),
        hint_source="https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct"),
    _listed(
        "qwen3-1.7b-q8_0", "Qwen3 1.7B (Q8_0)",
        "Qwen/Qwen3-1.7B-GGUF", "90862c4b9d2787eaed51d12237eafdfe7c5f6077",
        files=_hf("Qwen/Qwen3-1.7B-GGUF", "90862c4b9d2787eaed51d12237eafdfe7c5f6077",
                  ("weights", "Qwen3-1.7B-Q8_0.gguf", 1_834_426_016,
                   "061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a")),
        licence="Apache-2.0", publisher="Qwen", base_model="Qwen/Qwen3-1.7B",
        quantizer=None, architecture="qwen3", context_length=40960,
        parameters="1.7B (GGUF metadata)", fmt="GGUF Q8_0",
        hints=("general", "reasoning"),
        hint_source="https://huggingface.co/Qwen/Qwen3-1.7B"),
    _listed(
        "glm-4-9b-0414-q4_k_m", "GLM-4 9B 0414 (Q4_K_M)",
        "unsloth/GLM-4-9B-0414-GGUF", "40a17a0c8f24664ddd851dafd03935553c25a57e",
        files=_hf("unsloth/GLM-4-9B-0414-GGUF", "40a17a0c8f24664ddd851dafd03935553c25a57e",
                  ("weights", "GLM-4-9B-0414-Q4_K_M.gguf", 6_166_574_944,
                   "8027e1089273e8817b2df0d91c9aa17c5ea467246dcdacac34989f8919fe6540")),
        licence="MIT", publisher="THUDM (Z.ai)", base_model="THUDM/GLM-4-9B-0414",
        quantizer="unsloth", architecture="glm4", context_length=32768,
        parameters="9.4B (GGUF metadata)", fmt="GGUF Q4_K_M",
        hints=("general",), hint_source="https://huggingface.co/THUDM/GLM-4-9B-0414"),
    _listed(
        "deepseek-r1-0528-qwen3-8b-q4_k_m", "DeepSeek R1 0528 Qwen3 8B (Q4_K_M)",
        "unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF",
        "eb48357c179d34dbf515983f798dfb8752a0f261",
        files=_hf("unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF",
                  "eb48357c179d34dbf515983f798dfb8752a0f261",
                  ("weights", "DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf", 5_027_785_216,
                   "a86349a4180c4e6bb43f874c29c404fa2be3f90b15509bd6d86f697dba724ec1")),
        licence="MIT", publisher="DeepSeek",
        base_model="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B", quantizer="unsloth",
        architecture="qwen3", context_length=131072,
        parameters="8.2B (GGUF metadata)", fmt="GGUF Q4_K_M",
        hints=("reasoning",),
        hint_source="https://huggingface.co/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"),
    _listed(
        "gpt-oss-20b-mxfp4", "gpt-oss 20B (MXFP4)",
        "ggml-org/gpt-oss-20b-GGUF", "ef9b12f2ff56c69cf32153a02784e7a3c88bf524",
        files=_hf("ggml-org/gpt-oss-20b-GGUF", "ef9b12f2ff56c69cf32153a02784e7a3c88bf524",
                  ("weights", "gpt-oss-20b-MXFP4.gguf", 12_109_566_624,
                   "27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901")),
        licence="Apache-2.0", publisher="OpenAI", base_model="openai/gpt-oss-20b",
        quantizer="ggml-org", architecture="gpt-oss", context_length=131072,
        parameters="20.9B (GGUF metadata)", fmt="GGUF MXFP4",
        hints=("reasoning", "general"),
        hint_source="https://huggingface.co/openai/gpt-oss-20b"),
    _listed(
        "gpt-oss-120b-mxfp4", "gpt-oss 120B (MXFP4)",
        "ggml-org/gpt-oss-120b-GGUF", "238abdd290bb874b90a5da1b4549881b7d05c091",
        files=_hf("ggml-org/gpt-oss-120b-GGUF", "238abdd290bb874b90a5da1b4549881b7d05c091",
                  ("weights", "gpt-oss-120b-MXFP4.gguf", 63_387_346_208,
                   "582bd40f6886200101f4c4ed9f25f3fe80cc14c86e9e2b37746cd8904a0c622d")),
        licence="Apache-2.0", publisher="OpenAI", base_model="openai/gpt-oss-120b",
        quantizer="ggml-org", architecture="gpt-oss", context_length=131072,
        parameters="116.8B (GGUF metadata)", fmt="GGUF MXFP4",
        hints=("reasoning",),
        hint_source="https://huggingface.co/openai/gpt-oss-120b"),
)

CATALOGUE = CATALOGUE + LIBRARY

# The defaults the managed engine starts with, per workflow scope.
MANAGED_DEFAULTS = {CHAT: MANAGED_MAIN, CODE: MANAGED_MAIN,
                    DOCUMENTS_GENERATE: MANAGED_MAIN, DOCUMENTS_OCR: MANAGED_MAIN}



# Models Refinix has looked at and deliberately does **not** offer. Used only
# to annotate one that is already installed, so the interface can say why it is
# not a supported entry instead of saying nothing. Offering these as downloads
# is what `docs/model-catalog.md` forbids.
NOTED: dict[str, str] = {
    "MedAIBase/PaddleOCR-VL:0.9b":
        "Installed candidate only. Who published this conversion, from what, "
        "and under which licence is unresolved, and the manifest carries no "
        "licence layer — so Refinix does not list it as a supported model. It "
        "was also observed to declare no image capability on the device that "
        "inspected it.",
}

BY_ID = {entry.id: entry for entry in CATALOGUE}


@dataclass(frozen=True)
class SelfTest:
    """The smallest representative check for one capability.

    Small on purpose. A self-test answers "can this model do the smallest real
    version of this job on this computer", which is the question setup has to
    pass before a capability is called ready. It is not a quality benchmark and
    must never be presented as one.
    """

    scope: str
    label: str
    needs_model: bool
    needs_vision: bool = False
    writes_artifact: bool = False
    caveat: str = ("A self-test shows the capability ran once here. It says "
                   "nothing about the quality of any answer.")


# The Chat self-test's premise, and the two numbers it turns on.
#
# Every fact it needs is in the prompt. That is the point: a model that fails
# this failed at holding a relation straight, not at knowing something, and a
# domain question would leave those two indistinguishable. It replaces "what is
# 2 + 2?", which a model passed by answering at all — the reply was only
# checked for being non-empty, so a model that writes fluently and reverses
# every comparison it is asked about passed Chat qualification.
CHAT_CHECK_SMALLER = "2.4"
CHAT_CHECK_LARGER = "3.1"
CHAT_CHECK_PROMPT = (
    "Use only the facts in this message.\n"
    f"Available capacity is {CHAT_CHECK_SMALLER}.\n"
    f"Required capacity is {CHAT_CHECK_LARGER}.\n"
    "The operation is unsafe when available capacity is below required "
    "capacity.\n"
    "Reply with one line and nothing else, in this form:\n"
    "<safe or unsafe>; smaller number: <the smaller of the two numbers>")

# The whole reply, on one line, or it is not an answer to this question.
#
# `fullmatch`, and no prose fallback. Found in review: searching for a verdict
# token and a number independently passed "not unsafe; smaller number: 2.4" —
# the negation sits outside both patterns — and passed a reply that gave the
# right answer and then contradicted itself. Every other capability's self-test
# already requires an exact shape from the decoder; accepting loose prose here
# bought tolerance for a model that rambles at the cost of the evidence the
# check exists to produce.
#
# Line boundaries are checked before whitespace is normalised. Found in a
# later review: collapsing every run of whitespace first let a reply spread
# over several lines pass as the one line it was asked for.
#
# A reply in the wrong shape and a reply with the comparison backwards are
# reported as different failures, because they are: one model did not follow
# a one-line format instruction, the other could not hold a relation. Only
# the second is described as reversing anything.
#
# The "smaller number:" label is optional (user decision D1, 2026-10-07):
# "unsafe; 2.4" states the verdict and the number exactly as asked, only
# without the label. The whole reply must still be that one line.
_STRICT_REPLY = re.compile(
    r"(unsafe|safe)\s*;\s*(?:smaller number\s*:\s*)?(\d+(?:\.\d+)?)\.?", re.I)

# Failure kinds. Formatting: the reply could not be read back as an answer.
# Wrong answer: it could, and the answer is wrong. Incomplete: the check's
# output limit was reached before an answer was finished (D9).
EMPTY, MULTI_LINE, EXTRA_TEXT = "empty", "multi_line", "extra_text"
WRONG_VERDICT, WRONG_NUMBER, INVALID_OUTPUT = "wrong_verdict", "wrong_number", "invalid_output"
INCOMPLETE = "incomplete"
FORMAT_FAILURES = frozenset({EMPTY, MULTI_LINE, EXTRA_TEXT})
EXCERPT_CHARS = 240


def chat_reply_failure(reply: str) -> tuple[str, str] | None:
    """`(kind, sentence)` for why a reply to `CHAT_CHECK_PROMPT` fails, or None.

    The sentence is what a person reads in the self-test result, so it says
    what the model actually did rather than that a check failed.
    """
    stripped = (reply or "").strip()
    if not stripped:
        return EMPTY, "answered with nothing visible"
    if "\n" in stripped or "\r" in stripped:
        return MULTI_LINE, ("answered on more than one line instead of the single "
                            "line it was asked for")
    text = " ".join(stripped.split())
    answer = _STRICT_REPLY.fullmatch(text)
    if answer is None:
        return EXTRA_TEXT, ("did not answer in the exact one-line form it was asked "
                            "for, so what it concluded could not be read back "
                            "without guessing")
    verdict, smaller = answer.group(1).casefold(), answer.group(2)
    if verdict == "safe":
        return WRONG_VERDICT, (f"called the operation safe although the available "
                               f"capacity ({CHAT_CHECK_SMALLER}) is below the required "
                               f"capacity ({CHAT_CHECK_LARGER})")
    if smaller != CHAT_CHECK_SMALLER:
        return WRONG_NUMBER, (f"named {smaller} as the smaller number when "
                              f"{CHAT_CHECK_SMALLER} is")
    return None


def reply_excerpt(reply) -> str | None:
    """A short, inert excerpt of a self-test reply, kept for diagnosis.

    Only ever called with a model's reply to a synthetic self-test prompt,
    never with a person's conversation. Line breaks stay visible as ⏎ because
    they can be the reason a reply failed; other control characters go.
    """
    if not isinstance(reply, str) or not reply:
        return None
    text = reply.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ⏎ ")
    text = "".join(ch for ch in text if ch == " " or ch.isprintable())
    return text[:EXCERPT_CHARS] + ("…" if len(text) > EXCERPT_CHARS else "")


SELFTESTS: dict[str, SelfTest] = {
    CHAT: SelfTest(CHAT, "Apply one supplied rule to two numbers",
                   needs_model=True),
    CODE: SelfTest(CODE, "Propose one small change", needs_model=True),
    DOCUMENTS_GENERATE: SelfTest(
        DOCUMENTS_GENERATE, "Write and reopen a Word document",
        needs_model=True, writes_artifact=True),
    DOCUMENTS_OCR: SelfTest(
        DOCUMENTS_OCR, "Read one rendered page", needs_model=True,
        needs_vision=True),
}

PASSED = "passed"
FAILED = "failed"
NOT_RUN = "not_run"

class SelfTestError(RuntimeError):
    """A self-test could not run. Never recorded as a failure of the model."""


class IncompleteReply(Exception):
    """The model was still writing when the check's output limit was reached.

    Raised only for that runtime-reported stop reason. A crash, a cancel, a
    runtime that stopped answering or any other stop is a `SelfTestError`.
    """

    def __init__(self, text: str, limit: int | None):
        super().__init__("the reply reached the check's output limit")
        self.text, self.limit = text or "", limit


def entry_for(model: str) -> Entry | None:
    return BY_ID.get(model)


def entry_for_origin(model_id: str, origin: str | None) -> Entry | None:
    """The catalogue entry for these bytes only when it names the same runtime.

    The Ollama tag `qwen3.5:4b-q4_K_M` and the Refinix engine's
    `qwen3.5-4b-q4_k_m` are different artifacts; an entry never describes a
    model from another runtime because the names look alike.
    """
    entry = BY_ID.get(model_id)
    if entry is None or (origin is not None and entry.engine != origin):
        return None
    return entry


# --------------------------------------------------------------------------
# Identity across runtimes
# --------------------------------------------------------------------------

AUTO = "auto"


def legacy_origins(model_id: str, *, install_engines: dict[str, str],
                   observed: dict[str, dict]) -> set[str]:
    """Which runtimes a bare stored model name could mean.

    Selections and preferences saved before identities carried their origin
    hold only a name. Its origin comes from what was recorded — an install
    record's engine, a catalogue entry's engine — and from which runtime
    actually reports that name now. One answer resolves it; none means the
    model is gone; two means the name is ambiguous and the person chooses
    again. Catalogue membership alone never decides it: the catalogue holds
    entries for both runtimes.
    """
    origins = set()
    if model_id in install_engines:
        origins.add(install_engines[model_id])
    entry = BY_ID.get(model_id)
    if entry is not None:
        origins.add(entry.engine)
    origins.update(item["origin"] for item in observed.values()
                   if item.get("model_id") == model_id)
    return origins


_SLUG = re.compile(r"[^a-z0-9._-]+")


def managed_id_for(repo: str, filename: str, revision: str,
                   taken: set[str] | frozenset = frozenset()) -> str:
    """A collision-safe id for a model resolved from a repository.

    Lower-case letters, digits, dot, dash and underscore only, so it can never
    contain Ollama's tag separator or the origin separator. Checked against
    every recorded id; a clash gains a counter rather than replacing a model.
    """
    stem = filename[:-5] if filename.lower().endswith(".gguf") else filename
    stem = re.sub(r"-0*1-of-0*\d+$", "", stem)
    owner = repo.split("/", 1)[0]
    base = _SLUG.sub("-", f"hf-{owner}-{stem}-{revision[:7]}".lower()).strip("-")[:110]
    candidate, counter = base, 2
    while candidate in taken or candidate in BY_ID:
        candidate, counter = f"{base}-{counter}", counter + 1
    return candidate


def entry_from_record(record: dict) -> Entry | None:
    """The library entry a resolved download recorded with its install.

    Only Refinix-engine installs carry one. Older rows hold a plain-text
    source and stay readable; they simply have no resolved metadata.
    """
    if record is None:
        return None
    catalogued = BY_ID.get(record.get("model_id"))
    if catalogued is not None:
        return catalogued
    try:
        meta = json.loads(record.get("source") or "")
    except (TypeError, ValueError):
        return None
    if not isinstance(meta, dict) or meta.get("kind") != "resolved":
        return None
    try:
        files = tuple(ModelFile(str(f["role"]), str(f["name"]), int(f["size"]),
                                str(f["sha256"]), str(f.get("url") or ""))
                      for f in meta.get("files") or ())
        return Entry(
            id=record["model_id"], display_name=meta.get("display_name"),
            role="Library model", scopes=(CHAT, CODE, DOCUMENTS_GENERATE),
            source=str(meta.get("source") or ""), licence=meta.get("licence"),
            manifest_sha256=record.get("manifest_sha256"), format=meta.get("format"),
            parameters=meta.get("parameters"),
            storage_bytes=sum(f.size for f in files) or None, minimum_runtime=None,
            evidence=str(meta.get("evidence") or ""), evidence_state=LISTED,
            engine="llama.cpp", files=files, revision=meta.get("revision"),
            publisher=meta.get("publisher"), base_model=meta.get("base_model"),
            quantizer=meta.get("quantizer"), repo=meta.get("repo"),
            architecture=meta.get("architecture"),
            context_length=meta.get("context_length"),
            hints=(), hint_source=meta.get("hint_source"),
            repo_tags=_recorded_tags(meta))
    except (KeyError, TypeError, ValueError):
        return None


def _recorded_tags(meta: dict) -> tuple[str, ...]:
    """The repository task tags a resolved install recorded.

    Version 1 records kept a `hints` list in which `general` was added to
    every download and `vision` meant only that a projector was chosen —
    neither is evidence of a task strength, so both are dropped here; `code`
    and `reasoning` did come from the repository's own tags and are kept.
    Version 2 records the vocabulary-filtered tags themselves.
    """
    if meta.get("version", 1) >= 2:
        tags = meta.get("repo_tags") or ()
    else:
        tags = [hint for hint in meta.get("hints") or () if hint in ("code", "reasoning")]
    return tuple(str(tag) for tag in tags if isinstance(tag, str))[:16]


def record_source(entry: Entry, how: str) -> str:
    """The `model_installs.source` text for a resolved entry: versioned JSON."""
    if entry.id in BY_ID:
        return f"{how} {entry.source}"
    return json.dumps({
        "kind": "resolved", "version": 2, "how": how,
        "display_name": entry.display_name, "source": entry.source,
        "licence": entry.licence, "format": entry.format,
        "parameters": entry.parameters, "evidence": entry.evidence,
        "revision": entry.revision, "publisher": entry.publisher,
        "base_model": entry.base_model, "quantizer": entry.quantizer,
        "repo": entry.repo, "architecture": entry.architecture,
        "context_length": entry.context_length,
        "repo_tags": list(entry.repo_tags), "hint_source": entry.hint_source,
        "files": [f.as_dict() for f in entry.files]}, sort_keys=True)


# --------------------------------------------------------------------------
# Task evidence: what a model is documented to be good at, or limited to
# --------------------------------------------------------------------------
#
# One resolver for both runtimes, so Ollama and the Refinix engine describe a
# model the same way. Three sources, most credible first, and the most
# credible one present is used on its own rather than merged with weaker ones:
#
#   3  a curated catalogue entry citing the publisher's model card;
#   2  task tags the model's own repository publishes, recorded at Browse;
#   1  task tags the runtime reports from the model file's metadata.
#
# A model's name, family, architecture or base model never assigns a
# strength or a limitation: a fine-tune can differ from what it was built on.

# Tags that name a task strength, per tag and never per model.
TAG_STRENGTHS = {
    "conversational": "general", "chat": "general", "instruct": "general",
    "code": "code", "coding": "code",
    "reasoning": "reasoning", "math": "reasoning",
    "ocr": "ocr",
    "image-text-to-text": "vision", "vision": "vision", "multimodal": "vision",
}
EVIDENCE_CARD, EVIDENCE_REPOSITORY, EVIDENCE_RUNTIME, EVIDENCE_NONE = 3, 2, 1, 0


def strengths_from_tags(tags) -> tuple[str, ...]:
    found = []
    for tag in tags or ():
        strength = TAG_STRENGTHS.get(str(tag).strip().lower())
        if strength and strength not in found:
            found.append(strength)
    return tuple(found)


def task_evidence(entry: Entry | None, runtime_tags=()) -> dict:
    """`{strengths, limited_to, level, source}` for one model, from evidence only."""
    if entry is not None and entry.id in BY_ID and (entry.hints or entry.limited_to):
        return {"strengths": tuple(entry.hints), "limited_to": tuple(entry.limited_to),
                "level": EVIDENCE_CARD, "source": entry.hint_source}
    if entry is not None and entry.repo_tags:
        strengths = strengths_from_tags(entry.repo_tags)
        if strengths:
            return {"strengths": strengths, "limited_to": (),
                    "level": EVIDENCE_REPOSITORY,
                    "source": (f"https://huggingface.co/{entry.repo}" if entry.repo
                               else entry.hint_source)}
    strengths = strengths_from_tags(runtime_tags)
    if strengths:
        return {"strengths": strengths, "limited_to": (), "level": EVIDENCE_RUNTIME,
                "source": "the model file's metadata, as its runtime reports it"}
    return {"strengths": (), "limited_to": (), "level": EVIDENCE_NONE, "source": None}


def provenance(model: str, *, origin: str | None = None,
               entry: Entry | None = None) -> dict:
    """What Refinix records about one model id, whatever its state.

    Three answers, and they are different claims: a recorded manifest, a
    recorded refusal to vouch for it, or nothing recorded at all. With an
    `origin`, a catalogue entry for another runtime's artifact does not count.
    """
    entry = entry or (entry_for_origin(model, origin) if origin else BY_ID.get(model))
    if entry is not None:
        return {"known": True, **entry.as_dict()}
    if model in NOTED:
        return {"known": False, "id": model, "evidence_state": UNRESOLVED,
                "note": NOTED[model]}
    return {"known": False, "id": model, "evidence_state": UNVERIFIED,
            "note": ("Refinix has no recorded source, licence or manifest for "
                     "this model. It is available because the local engine "
                     "reports it, not because Refinix verified it.")}


def integrity(model: str, digest: str | None) -> dict:
    """Compare observed bytes with the catalogue without trusting the tag."""
    entry = BY_ID.get(model)
    expected = entry.manifest_sha256 if entry else None
    if expected is None:
        return {"state": UNVERIFIED, "expected": None, "observed": digest,
                "eligible": bool(digest)}
    if not digest:
        return {"state": NOT_OBSERVED, "expected": expected, "observed": None,
                "eligible": False}
    matched = digest == expected
    return {"state": VERIFIED if matched else MISMATCH,
            "expected": expected, "observed": digest, "eligible": matched}


def digest_eligible(model: str, digest: str | None) -> bool:
    """Known models must match their recorded manifest; unlisted models do not.

    Strict, for a paired worker's advertised model. Local models use
    `local_integrity`, which treats a person's own Ollama copy differently.
    """
    return integrity(model, digest)["eligible"]


DIFFERS = "differs"


def local_integrity(model_id: str, digest: str | None, origin: str) -> dict:
    """Integrity of a model on this computer, by who owns its files.

    Refinix-engine files are Refinix's: a mismatch means they changed and the
    model is not used (the engine re-hashes them before every load). Ollama's
    store is the person's: if their copy of a catalogued tag has other bytes
    than Refinix recorded, it is still their model, usable and labelled as
    differing — not refused as though it were tampered Refinix property.
    """
    entry = entry_for_origin(model_id, origin)
    if origin != OLLAMA_ORIGIN or entry is None or entry.manifest_sha256 is None:
        if origin == OLLAMA_ORIGIN:
            return {"state": UNVERIFIED, "expected": None, "observed": digest,
                    "eligible": bool(digest)}
        return integrity(model_id, digest) if entry is not None else \
            {"state": UNVERIFIED, "expected": None, "observed": digest,
             "eligible": bool(digest)}
    if not digest:
        return {"state": NOT_OBSERVED, "expected": entry.manifest_sha256,
                "observed": None, "eligible": False}
    if digest == entry.manifest_sha256:
        return {"state": VERIFIED, "expected": entry.manifest_sha256,
                "observed": digest, "eligible": True}
    return {"state": DIFFERS, "expected": entry.manifest_sha256, "observed": digest,
            "eligible": True,
            "detail": ("Ollama holds different bytes under this name than the copy "
                       "Refinix recorded, so it is treated as your own model rather "
                       "than the recorded one.")}


OLLAMA_ORIGIN = "ollama"
MANAGED_ORIGIN = "llama.cpp"


def lifecycle_state(model: str, *, installed_here: bool, installed_elsewhere: bool,
                    runtime_reachable: bool) -> str:
    """Which of the four states one model is in, from observations only.

    The state answers "is it here", and `provenance` separately answers "does
    Refinix vouch for it". Keeping them apart is what lets a model that is
    installed but unverified stay usable and plainly labelled, and a model
    that is simply not installed say so whether or not Refinix records a
    manifest for it.
    """
    if installed_here or installed_elsewhere:
        return INSTALLED if model in BY_ID else UNLISTED
    if not runtime_reachable:
        # The engine did not answer, so "not installed" is not a thing anyone
        # observed. Absence is unknown, not established.
        return UNAVAILABLE
    return ABSENT


def setup_action(model: str) -> dict | None:
    """What a person can do themselves to install a supported model.

    A command to run, never a download Refinix starts. `docs/PROJECT.md` 21.1
    forbids a runtime model download, and this is the honest alternative: the
    exact step, in the open, performed by the person.
    """
    entry = BY_ID.get(model)
    if entry is not None and entry.files:
        # Refinix's own engine: downloaded by Refinix only when the person
        # confirms, after seeing what, from where and how much; or imported
        # from files they already have.
        size = sum(f.size for f in entry.files)
        return {"kind": "download", "label": "Download",
                "model": entry.id, "download_bytes": size,
                "detail": (f"About {size / 1024 ** 3:.1f} GB from {entry.source}, "
                           "checked against its pinned SHA-256. Or import the same "
                           "files from this computer.")}
    if entry is None or not entry.setup_command:
        return None
    return {"kind": "command", "label": "Install it yourself",
            "command": entry.setup_command,
            "detail": (f"Downloads about "
                       f"{entry.storage_bytes // (1024 ** 3)} GB from "
                       f"{entry.source}. Refinix does not start downloads on "
                       "its own.")}


def removal_impact(model: str, *, selections: dict, enabled: dict) -> dict:
    """What would stop working if this model were no longer available.

    Shown before a removal rather than discovered after one. Refinix never
    deletes anything itself here: chats, artifacts and history belong to the
    workspace and survive any model change, which is the fact this report
    states explicitly so nobody has to guess.
    """
    affected = sorted(scope for scope, chosen in selections.items()
                      if chosen == model)
    return {
        "model": model,
        "selected_for": affected,
        "blocked_capabilities": affected,
        "preserved": ["conversations", "saved messages", "generated artifacts",
                      "approvals", "job history"],
        "detail": (
            ("Removing it would leave "
             + ", ".join(affected)
             + " with no selected model until another is chosen. ")
            if affected else
            "No workflow is currently set to use it. ")
        + "Nothing you have written or generated is deleted by removing a "
          "model; conversations, artifacts and history are kept.",
        # The runtime owns the model store, so removal is its operation and is
        # named rather than performed. The same rule as installation.
        "command": f"ollama rm {model}" if model else None,
        "enabled": bool(enabled.get(model, True)),
    }


def run_selftest(scope: str, model: str, *, generate=None, artifact=None,
                 capabilities=None, vision_capability: str = "vision") -> dict:
    """Run one capability's smallest representative check.

    The callables are supplied by the caller that owns the runtime and the
    document writer, so this stays testable without either. A check that could
    not run at all is `unavailable` with its reason — never `failed`, which
    would blame the model for a missing prerequisite.
    """
    check = SELFTESTS.get(scope)
    if check is None:
        raise SelfTestError(f"there is no self-test for {scope}")
    if check.needs_vision:
        if capabilities is None:
            raise SelfTestError(
                f"The engine did not report what {model} can do, so Refinix "
                "cannot check that it accepts page images.")
        if vision_capability not in capabilities:
            return {"scope": scope, "model": model, "state": FAILED,
                    "failure_kind": "no_vision", "reply_excerpt": None,
                    "detail": (f"{model} does not accept page images on this "
                               "computer, so it cannot read a scan.")}
    if generate is None:
        raise SelfTestError("the local engine was not available to ask.")
    reply = None

    def failed(detail: str, kind: str = INVALID_OUTPUT) -> dict:
        return {"scope": scope, "model": model, "state": FAILED, "detail": detail,
                "failure_kind": kind, "reply_excerpt": reply_excerpt(reply)}

    try:
        if scope == CHAT:
            reply = generate(
                model, [{"role": "user", "content": CHAT_CHECK_PROMPT}],
                scope=scope, num_predict=128)
            wrong = chat_reply_failure(reply)
            if wrong:
                kind, sentence = wrong
                if kind in FORMAT_FAILURES:
                    return failed(f"{model} {sentence}. This is a formatting "
                                  "failure: the check could not read an answer "
                                  "back, which says nothing about whether the "
                                  "model would have got it right.", kind)
                return failed(f"{model} {sentence}. A model that reverses a "
                              "supplied relation can write a fluent technical "
                              "answer that is backwards, so Chat is not "
                              "self-tested on this computer.", kind)
        elif scope == CODE:
            from backend.coordinator import codeflow
            before = "before\n"
            selected = [{"path": "selftest.txt", "text": before,
                         "sha256": hashlib.sha256(before.encode()).hexdigest()}]
            reply = generate(
                model,
                codeflow.build_messages(
                    "Replace the entire file text with the single line: after",
                    selected),
                scope=scope,
                response_format=codeflow.PROPOSAL_SCHEMA, num_predict=512)
            try:
                proposal = codeflow.parse_proposal(reply, selected)
            except codeflow.ProposalError as exc:
                return failed(f"The model did not produce a valid Code proposal: {exc}")
            if not proposal["edits"]:
                return failed("The model produced no edit for the selected test file.")
        elif scope == DOCUMENTS_GENERATE:
            from backend.coordinator import docflow
            reply = generate(
                model,
                docflow.general_document_messages(
                    "Write a one-section document with one short paragraph about Refinix.",
                    []),
                scope=scope,
                response_format=docflow.GENERAL_DOCUMENT_FORMAT,
                num_predict=512)
            try:
                document = docflow.parse_general_document(reply)
            except docflow.WorkflowError as exc:
                return failed(f"The model did not produce a valid document: {exc}")
            if artifact is None:
                raise SelfTestError("no document writer was available to check.")
            written = artifact(title=document["title"],
                               blocks=docflow.general_blocks(document, []))
            if not written.get("valid"):
                return failed(written.get("detail") or
                              "A Word document could not be written and reopened here.")
        elif scope == DOCUMENTS_OCR:
            from backend.coordinator import ocr
            reply = generate(model, ocr.page_messages("image/png"),
                             scope=scope,
                             images=[ocr.selftest_image()],
                             response_format=ocr.PAGE_SCHEMA,
                             num_predict=ocr.PAGE_NUM_PREDICT)
            try:
                reading = ocr.parse_page_reply(reply)
            except ocr.OcrError as exc:
                return failed(f"The model did not produce a valid page reading: {exc}")
            if "refinix" not in reading.lower():
                return failed("The model did not read REFINIX from the test page image.")
    except IncompleteReply as exc:
        reply = exc.text
        limit = f"{exc.limit}-token " if exc.limit else ""
        return failed(f"{model} was still writing when this check's {limit}output "
                      "limit was reached, so it did not finish the answer. This "
                      "describes the check's bounded settings on this computer, not "
                      "every use of the model; Auto does not choose it for this task "
                      "while this result matches the model, runtime and settings. "
                      "Passing the check again restores it.", INCOMPLETE)
    except SelfTestError:
        raise
    except Exception as exc:                                # noqa: BLE001
        raise SelfTestError(str(exc)) from exc
    return {"scope": scope, "model": model, "state": PASSED,
            "detail": f"{check.label} succeeded on this computer. {check.caveat}",
            "failure_kind": None, "reply_excerpt": None}


def selftest_view(records: list[dict], *, model: str,
                  digest: str | None, fingerprints: dict | None = None,
                  legacy: str | None = None) -> dict:
    """One model's stored self-test results, against what is installed now.

    Three outcomes, kept apart because they are three different claims:

    * **current** — the result was observed against exactly the bytes that are
      installed now. Only this may make a capability look ready.
    * **superseded** — both digests are known and they differ, so the result
      describes a model that is no longer here.
    * **neither** — `digest` could not be observed at all, because the engine
      did not answer or the model is no longer installed. A pass then proves
      nothing about the present, and calling it current would be the exact
      fabrication the rest of this module avoids: it is reported as a pass
      that cannot be confirmed here.

    The record itself is always kept. Deleting it would lose the fact that a
    check was once run, which is true regardless of what is installed today.

    `fingerprints` maps each scope to the settings fingerprint a check would
    run with now (`admission.check_fingerprint`). When given, a pass is
    current only if it ran with exactly those settings; a result recorded
    without a fingerprint, or with other settings, is history. `legacy` is a
    bare model name whose older rows (saved before identities carried their
    runtime) belong to this model; they never carry a fingerprint.
    """
    shown = {}
    for record in records:
        if record["model"] != model and (legacy is None or record["model"] != legacy):
            continue
        if record["model"] != model and record["scope"] in shown:
            continue
        recorded = record.get("digest")
        matches = bool(digest and recorded and recorded == digest)
        expected = (fingerprints or {}).get(record["scope"]) if fingerprints is not None else None
        settings_match = (fingerprints is None
                          or (expected is not None
                              and record.get("check_fingerprint") == expected))
        shown[record["scope"]] = {
            "scope": record["scope"],
            "state": record["state"],
            "detail": record["detail"],
            "ran_at": record["ran_at"],
            "runtime_version": record.get("runtime_version"),
            "superseded": bool(digest and recorded and recorded != digest),
            "settings_changed": bool(fingerprints is not None and matches
                                     and not settings_match),
            # Whether this result — pass or failure — was observed against the
            # bytes installed now, with the settings a check would use now.
            # Computed on every read, never stored: replacing the model or
            # changing the check makes an old result history at once. An
            # unobservable digest or an unrecorded setting is not a match.
            "matches_now": matches and settings_match,
            # A pass that matches now: the only result that makes a
            # capability look checked.
            "current": record["state"] == PASSED and matches and settings_match,
            # Why a check failed, when the record says. Older rows predate it.
            "failure_kind": record.get("failure_kind"),
            "reply_excerpt": record.get("reply_excerpt"),
        }
    for scope, check in SELFTESTS.items():
        shown.setdefault(scope, {
            "scope": scope, "state": NOT_RUN,
            "detail": f"{check.label} has not been run on this computer yet.",
            "ran_at": None, "runtime_version": None,
            "superseded": False, "matches_now": False, "current": False,
            "failure_kind": None, "reply_excerpt": None})
    return shown
