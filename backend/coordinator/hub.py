"""Finding more models on Hugging Face, only when a person asks.

Browse in Settings → Models searches the Hugging Face API for GGUF
repositories, lists a repository's files, and resolves one choice into a
pinned library entry: the exact commit, every file's size and SHA-256 as the
Hub publishes them, the repository's licence tag, its base model and the
publisher/quantizer. The download itself then goes through the same verified
provisioner as every other model, and every byte is re-hashed against these
values before it is used.

What a Hub hash proves: that the bytes match what the Hub serves for that
file at that commit. It does not prove the publisher's identity, a model's
quality, that it fits this computer, or that its licence suits the person's
use; the interface labels it accordingly.

Boundaries:

* nothing here runs at startup, in the background or during offline work;
* no token is sent and none is read, so gated or private repositories are
  explained, not fetched;
* no telemetry: a plain request with a fixed user agent and nothing about the
  person, their prompts or their documents;
* only https://huggingface.co is contacted; a redirect elsewhere is refused.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote, urlencode, urlsplit

from backend.coordinator import models

API = "https://huggingface.co/api"
HOST = "huggingface.co"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_RESULTS = 30
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_SPLIT = re.compile(r"^(?P<stem>.+)-(?P<part>\d{5})-of-(?P<count>\d{5})\.gguf$", re.I)
# A weight file's quantization suffix, and a projector's precision suffix:
# what is left is the model a file belongs to.
_QUANT_TAIL = re.compile(
    r"[-_.](?:ud[-_])?(?:i?q\d\w*|f16|bf16|f32|fp16|fp32|mxfp4\w*)$", re.I)
_PRECISION_TAIL = re.compile(r"[-_.]?(?:f16|bf16|f32|fp16|fp32|q8_0)$", re.I)
_GENERIC_PROJECTOR = {"", "model"}
_REVISION = re.compile(r"^[0-9a-f]{40}$")


class HubError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _get(url: str, *, pool=None) -> dict | list:
    """One GET to the Hub API, refusing redirects off the Hub and huge replies."""
    from backend.coordinator import provisioning
    pool = pool or provisioning._pool()
    for _ in range(4):
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != HOST:
            raise HubError("unsafe_source", "Only https://huggingface.co is used.")
        response = pool.request("GET", url, redirect=False, preload_content=False,
                                headers={"User-Agent": "refinix-model-browse",
                                         "Accept": "application/json"})
        try:
            if response.status in (301, 302, 307, 308):
                location = response.headers.get("Location") or ""
                url = location if location.startswith("https://") else \
                    f"https://{HOST}{location}"
                continue
            if response.status == 401 or response.status == 403:
                raise HubError("gated", "That repository needs a Hugging Face account "
                                        "to open, which Refinix does not use.")
            if response.status == 404:
                raise HubError("not_found", "That repository or revision was not found.")
            if response.status != 200:
                raise HubError("bad_response", f"Hugging Face answered {response.status}.")
            body = response.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
        finally:
            response.release_conn()
        if len(body) > MAX_RESPONSE_BYTES:
            raise HubError("too_large", "Hugging Face's answer was unexpectedly large.")
        try:
            return json.loads(body)
        except ValueError as exc:
            raise HubError("bad_response", "Hugging Face's answer was not JSON.") from exc
    raise HubError("bad_response", "Too many redirects.")


def search(query: str, *, pool=None, limit: int = 20) -> list[dict]:
    """GGUF repositories matching `query`, most downloaded first."""
    query = (query or "").strip()
    if not query or len(query) > 100:
        raise HubError("bad_query", "Type up to 100 characters to search.")
    params = urlencode({"search": query, "filter": "gguf", "sort": "downloads",
                        "direction": "-1", "limit": max(1, min(limit, MAX_RESULTS))})
    listed = _get(f"{API}/models?{params}", pool=pool)
    results = []
    for item in listed if isinstance(listed, list) else []:
        repo = item.get("id") or item.get("modelId")
        if not isinstance(repo, str) or not _REPO.match(repo):
            continue
        results.append({"repo": repo, "downloads": item.get("downloads"),
                        "likes": item.get("likes"),
                        "gated": bool(item.get("gated")),
                        "private": bool(item.get("private")),
                        "pipeline_tag": item.get("pipeline_tag")})
    return results


def _info(repo: str, revision: str | None, *, pool=None) -> dict:
    if not _REPO.match(repo or ""):
        raise HubError("bad_repo", "That is not a Hugging Face repository name.")
    path = f"{API}/models/{quote(repo, safe='/')}"
    if revision:
        if not _REVISION.match(revision):
            raise HubError("bad_revision", "A revision must be a full commit hash.")
        path += f"/revision/{revision}"
    info = _get(path + "?blobs=true", pool=pool)
    if not isinstance(info, dict):
        raise HubError("bad_response", "Hugging Face did not describe that repository.")
    if info.get("private"):
        raise HubError("private", "That repository is private.")
    if info.get("gated"):
        raise HubError("gated", "That repository asks people to accept its terms with a "
                                "Hugging Face account first. Refinix does not use "
                                "accounts or tokens; look for an ungated official "
                                "conversion instead.")
    if not _REVISION.match(str(info.get("sha") or "")):
        raise HubError("bad_response", "Hugging Face did not give an exact revision.")
    return info


def _gguf_files(info: dict) -> list[dict]:
    files = []
    for item in info.get("siblings") or []:
        name = item.get("rfilename") or ""
        lfs = item.get("lfs") or {}
        sha = (lfs.get("sha256") or "").lower()
        size = item.get("size") if isinstance(item.get("size"), int) else lfs.get("size")
        if not name.lower().endswith(".gguf") or "/" in name or "\\" in name:
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", sha) or not isinstance(size, int) or size <= 0:
            continue
        files.append({"name": name, "size": size, "sha256": sha})
    return files


def _is_projector(name: str) -> bool:
    return "mmproj" in name.lower()


def _model_stem(name: str) -> str:
    """The model a weight file belongs to, without its quantization."""
    match = _SPLIT.match(name)
    base = match["stem"] if match else name[:-len(".gguf")]
    return _QUANT_TAIL.sub("", base).lower()


def _projector_stem(name: str) -> str:
    """The model a projector names, or "" for one named for no model."""
    base = name[:-len(".gguf")].lower().replace("mmproj", "").strip("-_. ")
    base = _PRECISION_TAIL.sub("", base).strip("-_. ")
    return "" if base in _GENERIC_PROJECTOR else base


def _related(stem: str, other: str) -> bool:
    """One name extends the other (`model-a` and `model-a-v2`): maybe the same
    model, maybe a variant. Never enough to pair on its own."""
    return stem != other and any(stem.startswith(other + sep) or other.startswith(stem + sep)
                                 for sep in "-_.")


def _pair(choices: list[dict], projectors: list[dict]) -> None:
    """Give each weight choice the projectors that belong to its model.

    A projector named for exactly a file's model is `named`. One named for no
    model is `repository` when the repository holds a single model. Anything
    else that might fit — a projector named for a related model (`model-a`
    beside `model-a-v2`), or an unnamed one beside several models — is
    `ambiguous`: listed, never paired without the person choosing it, and
    refused by `resolve` unless that choice is confirmed. Text only is always
    possible. Nothing pairs a file with a projector by position.
    """
    stems = {choice["file"]: _model_stem(choice["file"]) for choice in choices}
    models_here = set(stems.values())
    named = {p["name"]: _projector_stem(p["name"]) for p in projectors}
    generic = [p for p in projectors if not named[p["name"]]]
    for choice in choices:
        stem = stems[choice["file"]]
        exact = [p for p in projectors if named[p["name"]] == stem]
        related = [p for p in projectors
                   if named[p["name"]] and _related(stem, named[p["name"]])]
        if exact:
            pairing, found = "named", exact
        elif generic and len(models_here) == 1 and not related:
            pairing, found = "repository", generic
        elif related or generic:
            pairing, found = "ambiguous", related + generic
        else:
            pairing, found = "none", []
        choice["pairing"] = pairing
        choice["projectors"] = [{"file": p["name"], "size": p["size"]} for p in found]


def _choices(files: list[dict]) -> list[dict]:
    projectors = [f for f in files if _is_projector(f["name"])]
    weights = [f for f in files if f not in projectors]
    groups: dict[str, list[dict]] = {}
    singles = []
    for item in weights:
        match = _SPLIT.match(item["name"])
        if match:
            groups.setdefault(match["stem"], []).append(item)
        else:
            singles.append(item)
    choices = [{"file": f["name"], "parts": [f["name"]], "size": f["size"]}
               for f in singles]
    for stem, parts in groups.items():
        parts.sort(key=lambda f: f["name"])
        count = int(_SPLIT.match(parts[0]["name"])["count"])
        if len(parts) == count:
            choices.append({"file": parts[0]["name"], "parts": [p["name"] for p in parts],
                            "size": sum(p["size"] for p in parts)})
    choices.sort(key=lambda c: c["size"])
    _pair(choices, projectors)
    return choices


def repository(repo: str, *, pool=None) -> dict:
    """The downloadable choices in one repository, at its current commit."""
    info = _info(repo, None, pool=pool)
    files = _gguf_files(info)
    projectors = [f for f in files if _is_projector(f["name"])]
    choices = _choices(files)
    card = info.get("cardData") or {}
    gguf = info.get("gguf") or {}
    return {"repo": repo, "revision": info["sha"], "licence": card.get("license"),
            "base_model": card.get("base_model"),
            "architecture": gguf.get("architecture"),
            "context_length": gguf.get("context_length"),
            "parameters": gguf.get("total"), "choices": choices,
            "projectors": [{"file": p["name"], "size": p["size"]} for p in projectors]}


def resolve(repo: str, file: str, revision: str, *, projector: str | None = None,
            projector_confirmed: bool = False,
            taken: set[str] = frozenset(), pool=None) -> models.Entry:
    """One pinned library entry from a repository's file (and projector).

    An `ambiguous` projector is accepted only with `projector_confirmed`: the
    person chose it knowing nothing here ties it to this file's model.
    """
    info = _info(repo, revision, pool=pool)
    files = {f["name"]: f for f in _gguf_files(info)}
    if file not in files:
        raise HubError("not_found", f"{file} is not a GGUF file at that revision.")
    if _is_projector(file):
        raise HubError("not_weights", f"{file} is an image projector, not model weights.")
    match = _SPLIT.match(file)
    if match:
        count = int(match["count"])
        names = [f"{match['stem']}-{index:05d}-of-{count:05d}.gguf"
                 for index in range(1, count + 1)]
        missing = [name for name in names if name not in files]
        if missing:
            raise HubError("incomplete", "That model's parts are not all published: "
                                         + ", ".join(missing[:3]))
    else:
        names = [file]
    if projector is not None and projector not in files:
        raise HubError("not_found", f"{projector} is not a file at that revision.")
    if projector is not None:
        choice = next((c for c in _choices(list(files.values())) if c["file"] == file), None)
        if choice is None or projector not in [p["file"] for p in choice["projectors"]]:
            raise HubError("projector_mismatch",
                           f"{projector} is not published for {file}'s model, so it "
                           "was not paired with it. Choose a projector listed for "
                           "that file, or text only.")
        if choice["pairing"] == "ambiguous" and not projector_confirmed:
            raise HubError("projector_unconfirmed",
                           f"Nothing in this repository ties {projector} to {file}'s "
                           "model, so it is added only when you choose it yourself. "
                           "Choose it in Browse, or use text only.")
    base = f"https://{HOST}/{repo}/resolve/{info['sha']}/"
    pinned = tuple(
        models.ModelFile("weights" if index == 0 else "weights-part", name,
                         files[name]["size"], files[name]["sha256"],
                         base + quote(name))
        for index, name in enumerate(names))
    if projector:
        pinned += (models.ModelFile("projector", projector, files[projector]["size"],
                                    files[projector]["sha256"], base + quote(projector)),)
    card = info.get("cardData") or {}
    gguf = info.get("gguf") or {}
    tags = {str(t).lower() for t in info.get("tags") or []}
    base_model = card.get("base_model")
    if isinstance(base_model, list):
        base_model = base_model[0] if base_model else None
    owner = repo.split("/", 1)[0]
    base_owner = base_model.split("/", 1)[0] if isinstance(base_model, str) and "/" in base_model else None
    quantizer = owner if base_owner and base_owner.lower() != owner.lower() else None
    hints = tuple(h for h, present in (("general", True), ("vision", bool(projector)),
                                      ("code", "code" in tags),
                                      ("reasoning", "reasoning" in tags)) if present)
    model_id = models.managed_id_for(repo, file, info["sha"], set(taken))
    licence = card.get("license")
    revision = info["sha"]
    converter = (f" — a {quantizer} conversion of {base_model}" if quantizer
                 else (f" — of {base_model}" if base_model else ""))
    return models.Entry(
        id=model_id, display_name=f"{repo.split('/', 1)[1]} — {file}",
        role="Library model",
        scopes=(models.CHAT, models.CODE, models.DOCUMENTS_GENERATE),
        source=f"huggingface.co/{repo} at {revision}{converter}",
        licence=(f"repository licence tag: {licence}" if licence else
                 "not stated by the repository — check before use"),
        manifest_sha256=models.manifest_digest(model_id, revision, pinned),
        format=f"GGUF ({len(names)} file{'s' if len(names) > 1 else ''})"
               + (" with a vision projector" if projector else ""),
        parameters=(f"{gguf['total'] / 1e9:.1f}B (GGUF metadata)"
                    if isinstance(gguf.get("total"), int) else None),
        storage_bytes=sum(f.size for f in pinned), minimum_runtime=None,
        evidence=(f"Resolved from the Hugging Face API at revision {revision} when you "
                  "chose it: sizes and SHA-256 as the Hub publishes them. Not "
                  "measured by Refinix; whether it loads and fits is shown when used."),
        evidence_state=models.LISTED, engine="llama.cpp", files=pinned,
        revision=revision, publisher=base_owner or owner,
        base_model=base_model if isinstance(base_model, str) else None,
        quantizer=quantizer, repo=repo,
        architecture=gguf.get("architecture") if isinstance(gguf.get("architecture"), str) else None,
        context_length=gguf.get("context_length") if isinstance(gguf.get("context_length"), int) else None,
        hints=hints, hint_source=f"https://huggingface.co/{repo}")
