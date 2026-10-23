"""The managed engine boundary, the llama-server adapter and the backend.

Uses `fake_llama_server.py` started as a real process, so the ownership proof,
port handling, crash detection, Stop on a stalled stream and context overflow
are exercised over real loopback sockets. Nothing here loads a model.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.contracts import profiles as inference_profiles
from backend.contracts import v1
from backend.coordinator import engine, local_engine, runtime, runtime_llamacpp

FAKE = Path(__file__).with_name("fake_llama_server.py")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_root(base: Path, *, release="b11390") -> Path:
    root = base / "engine"
    root.mkdir()
    exe = root / "llama-server"
    shutil.copyfile(FAKE, exe)
    (root / "LICENSE").write_text("MIT", encoding="utf-8")
    manifest = {"manifest_version": 1, "kind": "llama.cpp", "component": "llama-server",
                "release": release, "commit": "test", "licence": "MIT", "source": "test",
                "lane": "macos-arm64", "backend": "metal", "archive_sha256": "0" * 64,
                "executable": "llama-server",
                "files": [{"path": "LICENSE", "size": 3, "sha256": _digest(root / "LICENSE")},
                          {"path": "llama-server", "size": exe.stat().st_size,
                           "sha256": _digest(exe)}]}
    (root / engine.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    return root


def python_spawn(config: Path):
    """Run the fake through the test interpreter on every OS."""
    def spawn(args, **kwargs):
        kwargs["env"] = dict(kwargs["env"], PYTHONDONTWRITEBYTECODE="1")
        return subprocess.Popen([sys.executable, args[0], *args[1:],
                                 "--fake-config", str(config)], **kwargs)
    return spawn


def profile_for(model_id="qwen-test", digest="a" * 64, runtime_version="b11390-metal",
                workflow=inference_profiles.CHAT, decoder=("text",)):
    values = {"model": {"model_id": model_id, "manifest_sha256": digest,
                        "runtime": "llama.cpp", "runtime_version": runtime_version},
              "target_profile_id": "test-tier", "workflow_mode": workflow,
              "qualified_context_tokens": 4096, "default_output_tokens": 256,
              "max_output_tokens": 256, "reasoning_modes": ["disabled", "enabled"],
              "default_reasoning": "disabled", "decoder_modes": list(decoder),
              "qualified_memory_bytes": None, "qualification_state": "qualified",
              "eligible": True, "evidence_kind": "measured", "evidence_ref": "test"}
    return v1.ExecutionProfile(profile_id=v1.execution_profile_id(values), **values)


class EngineBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.base = Path(self.dir.name)
        self.root = make_root(self.base)
        self.config = self.base / "fake-mode.json"
        self.set_mode("ok")
        self.weights = self.base / "model.gguf"
        self.weights.write_bytes(b"GGUF" + b"\0" * 64)
        self.selection = engine.select(environ={}, frozen=True, roots=[self.root])
        self.managed = engine.ManagedEngine(
            self.selection, self.base / "data", spawn=python_spawn(self.config),
            ports=range(39480, 39500))
        self.settings = engine.LaunchSettings(context_tokens=4096)

    def tearDown(self):
        self.managed.stop()
        self.dir.cleanup()

    def set_mode(self, mode, **extra):
        self.config.write_text(json.dumps({"mode": mode, **extra}), encoding="utf-8")

    def model(self):
        return engine.ModelFiles("qwen-test", self.weights)


class TestSelection(EngineBase):
    def test_an_intact_shipped_engine_is_selected_and_verified(self):
        self.assertEqual(self.selection.mode, engine.MANAGED)
        self.assertEqual(self.selection.problems, [])
        self.assertEqual(self.selection.runtime_version, "b11390-metal")

    def test_a_packaged_build_without_an_engine_never_falls_back_to_ollama(self):
        selection = engine.select(environ={}, frozen=True, roots=[])
        self.assertEqual((selection.mode, selection.kind), (engine.MANAGED, engine.LLAMA_CPP))
        self.assertFalse(selection.usable)

    def test_the_ollama_override_is_ignored_in_a_packaged_build(self):
        selection = engine.select(environ={"REFINIX_ENGINE": "ollama"}, frozen=True,
                                  roots=[self.root])
        self.assertEqual(selection.mode, engine.MANAGED)

    def test_a_source_checkout_may_choose_the_developer_engine_explicitly(self):
        selection = engine.select(environ={"REFINIX_ENGINE": "ollama"}, frozen=False,
                                  roots=[self.root])
        self.assertEqual(selection.mode, engine.DEVELOPER)

    def test_an_engine_on_path_is_never_used(self):
        decoy = self.base / "path"
        decoy.mkdir()
        shutil.copyfile(FAKE, decoy / "llama-server")
        with patch.dict(os.environ, {"PATH": str(decoy)}):
            selection = engine.select(environ=os.environ, frozen=True, roots=[])
        self.assertIsNone(selection.root)
        self.assertFalse(selection.usable)

    def test_a_modified_engine_file_is_reported_and_never_started(self):
        with open(self.root / "llama-server", "a", encoding="utf-8") as handle:
            handle.write("# tampered\n")
        selection = engine.select(environ={}, frozen=True, roots=[self.root])
        self.assertTrue(selection.problems)
        spawned = []
        managed = engine.ManagedEngine(selection, self.base / "data",
                                       spawn=lambda *a, **k: spawned.append(a))
        with self.assertRaises(engine.EngineError) as caught:
            managed.ensure(self.model(), self.settings)
        self.assertEqual(caught.exception.code, "engine_unverified")
        self.assertEqual(spawned, [])

    def test_a_file_modified_after_startup_is_caught_before_the_next_launch(self):
        self.managed.ensure(self.model(), self.settings)
        self.managed.stop()
        with open(self.root / "LICENSE", "a", encoding="utf-8") as handle:
            handle.write("!")
        with self.assertRaises(engine.EngineError) as caught:
            self.managed.ensure(self.model(), self.settings)
        self.assertEqual(caught.exception.code, "engine_unverified")


class TestLaneChoice(EngineBase):
    def _cpu_root(self):
        (self.base / "cpu-lane").mkdir()
        cpu = make_root(self.base / "cpu-lane")
        manifest = json.loads((cpu / engine.MANIFEST_NAME).read_text())
        manifest.update(backend="cpu", lane="linux-x64-cpu")
        (cpu / engine.MANIFEST_NAME).write_text(json.dumps(manifest))
        return cpu

    def _gpu_root(self):
        (self.base / "gpu-lane").mkdir()
        gpu = make_root(self.base / "gpu-lane")
        manifest = json.loads((gpu / engine.MANIFEST_NAME).read_text())
        manifest.update(backend="vulkan", lane="linux-x64-vulkan")
        (gpu / engine.MANIFEST_NAME).write_text(json.dumps(manifest))
        return gpu

    def test_the_gpu_build_is_used_when_its_device_is_present(self):
        gpu, cpu = self._gpu_root(), self._cpu_root()
        chosen = engine.select(environ={}, frozen=True, roots=[gpu, cpu],
                               devices=lambda s: [{"id": "Vulkan0", "memory_mib": 4096}])
        self.assertEqual(chosen.manifest["backend"], "vulkan")

    def test_without_a_gpu_device_the_cpu_build_is_used(self):
        gpu, cpu = self._gpu_root(), self._cpu_root()
        chosen = engine.select(environ={}, frozen=True, roots=[gpu, cpu],
                               devices=lambda s: [])
        self.assertEqual(chosen.manifest["backend"], "cpu")

    def test_a_modified_gpu_build_is_reported_not_swapped_for_the_cpu_build(self):
        gpu, cpu = self._gpu_root(), self._cpu_root()
        with open(gpu / "LICENSE", "a", encoding="utf-8") as handle:
            handle.write("changed")
        chosen = engine.select(environ={}, frozen=True, roots=[gpu, cpu],
                               devices=lambda s: [])
        self.assertEqual(chosen.manifest["backend"], "vulkan")
        self.assertTrue(chosen.problems)


class TestLaunch(EngineBase):
    def test_the_engine_starts_proves_ownership_and_stops(self):
        endpoint = self.managed.ensure(self.model(), self.settings)
        self.assertEqual(endpoint.host, "127.0.0.1")
        self.assertIn(endpoint.port, range(39480, 39500))
        self.assertTrue(self.managed.running)
        self.assertTrue(self.managed.record_path.exists())
        # The same model and settings reuse the running process.
        self.assertIs(self.managed.ensure(self.model(), self.settings), endpoint)
        self.assertTrue(self.managed.stop())
        self.assertFalse(self.managed.running)
        self.assertFalse(self.managed.record_path.exists())

    def test_every_qualified_setting_is_explicit_and_fitting_is_off(self):
        args = engine.LaunchSettings(context_tokens=8192, slots=2).arguments()
        self.assertIn("--fit", args)
        self.assertEqual(args[args.index("--fit") + 1], "off")
        self.assertEqual(args[args.index("-c") + 1], "16384")
        for flag in ("-np", "-ngl", "-ctk", "-ctv", "-fa", "--reasoning-format"):
            self.assertIn(flag, args)

    def test_a_listener_that_accepts_anyone_is_not_adopted(self):
        self.set_mode("anonymous")
        with self.assertRaises(engine.EngineError) as caught:
            self.managed.ensure(self.model(), self.settings)
        self.assertEqual(caught.exception.code, "engine_foreign")
        self.assertFalse(self.managed.running)

    def test_a_different_build_is_refused(self):
        self.set_mode("wrong_build")
        with self.assertRaises(engine.EngineError) as caught:
            self.managed.ensure(self.model(), self.settings)
        self.assertEqual(caught.exception.code, "engine_unverified")

    def test_an_engine_that_dies_while_loading_is_reported(self):
        self.set_mode("die")
        with self.assertRaises(engine.EngineError) as caught:
            self.managed.ensure(self.model(), self.settings)
        self.assertEqual(caught.exception.code, "engine_failed")
        self.assertIn("exit code 3", str(caught.exception))

    def test_a_missing_model_file_is_refused_before_launch(self):
        with self.assertRaises(engine.EngineError) as caught:
            self.managed.ensure(engine.ModelFiles("x", self.base / "absent.gguf"),
                                self.settings)
        self.assertEqual(caught.exception.code, "model_missing")

    def test_an_occupied_port_is_skipped_not_shared(self):
        first = engine._free_port(range(39440, 39470))
        self.managed._ports = range(first, first + 10)
        with socket.socket() as squatter:
            squatter.bind(("127.0.0.1", first))
            squatter.listen(1)
            endpoint = self.managed.ensure(self.model(), self.settings)
        self.assertNotEqual(endpoint.port, first)

    def test_inherited_engine_settings_never_reach_the_process(self):
        with patch.dict(os.environ, {"LLAMA_ARG_CTX_SIZE": "999999",
                                     "OLLAMA_HOST": "0.0.0.0"}):
            env = engine.minimal_environment(self.root, self.base)
        self.assertNotIn("LLAMA_ARG_CTX_SIZE", env)
        self.assertNotIn("OLLAMA_HOST", env)

    def test_cancelling_a_slow_start_stops_the_process(self):
        self.set_mode("never_ready")
        cancel = threading.Event()
        threading.Timer(0.6, cancel.set).start()
        with self.assertRaises(engine.EngineError) as caught:
            self.managed.ensure(self.model(), self.settings, cancelled=cancel.is_set)
        self.assertEqual(caught.exception.code, "engine_cancelled")
        self.assertFalse(self.managed.running)


class TestOrphans(EngineBase):
    def _orphan(self):
        port = engine._free_port(range(39470, 39480))
        return subprocess.Popen([sys.executable, str(self.root / "llama-server"),
                                 "--port", str(port), "--api-key", "k",
                                 "--fake-config", str(self.config)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_a_provably_owned_orphan_is_stopped(self):
        import psutil
        orphan = self._orphan()
        try:
            self.managed.home.mkdir(parents=True)
            self.managed.record_path.write_text(json.dumps({
                "pid": orphan.pid,
                "create_time": psutil.Process(orphan.pid).create_time(),
                "executable": psutil.Process(orphan.pid).exe()}), encoding="utf-8")
            self.assertTrue(self.managed.reap_orphan())
            orphan.wait(timeout=5)
        finally:
            if orphan.poll() is None:
                orphan.kill()

    def test_a_recycled_pid_is_never_signalled(self):
        orphan = self._orphan()
        try:
            self.managed.home.mkdir(parents=True)
            self.managed.record_path.write_text(json.dumps({
                "pid": orphan.pid, "create_time": 1.0,
                "executable": "/somewhere/else"}), encoding="utf-8")
            self.assertFalse(self.managed.reap_orphan())
            time.sleep(0.2)
            self.assertIsNone(orphan.poll(), "an unrelated process was stopped")
        finally:
            orphan.kill()
            orphan.wait(timeout=5)


class _StubProcess:
    """A child that may ignore terminate, kill, or both."""

    def __init__(self, *, dies_on=("terminate",), terminate_error=None):
        self.pid = 999_999
        self.returncode = None
        self.dies_on = dies_on
        self.terminate_error = terminate_error
        self.calls = []

    def poll(self):
        return self.returncode

    def _signal(self, name):
        self.calls.append(name)
        if name in self.dies_on:
            self.returncode = -9

    def terminate(self):
        self._signal("terminate")
        if self.terminate_error:
            raise self.terminate_error

    def kill(self):
        self._signal("kill")

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("engine", timeout)
        return self.returncode


class TestStop(EngineBase):
    """A process is forgotten only once it is known to have exited."""

    def _owned(self, process):
        self.managed.home.mkdir(parents=True, exist_ok=True)
        self.managed.process = process
        self.managed.record_path.write_text(json.dumps(
            {"pid": process.pid, "create_time": 1.0, "executable": "x"}), encoding="utf-8")

    def test_a_process_that_ignores_terminate_is_killed_and_confirmed(self):
        stub = _StubProcess(dies_on=("kill",))
        self._owned(stub)
        with patch.object(engine, "STOP_SECONDS", 0.01):
            self.assertTrue(self.managed.stop())
        self.assertEqual(stub.calls, ["terminate", "kill"])
        self.assertIsNone(self.managed.process)
        self.assertFalse(self.managed.record_path.exists())

    def test_a_failed_terminate_still_waits_for_the_exit(self):
        stub = _StubProcess(dies_on=("kill",), terminate_error=PermissionError("denied"))
        self._owned(stub)
        with patch.object(engine, "STOP_SECONDS", 0.01):
            self.assertTrue(self.managed.stop())
        self.assertFalse(self.managed.record_path.exists())

    def test_a_survivor_keeps_its_record_and_blocks_a_replacement(self):
        stub = _StubProcess(dies_on=())
        self._owned(stub)
        spawned = []
        self.managed._spawn = lambda *a, **k: spawned.append(a)
        with patch.object(engine, "STOP_SECONDS", 0.01):
            with self.assertRaises(engine.EngineError) as caught:
                self.managed.stop()
            self.assertEqual(caught.exception.code, "engine_stop_blocked")
            self.assertIs(self.managed.process, stub)
            self.assertTrue(self.managed.record_path.exists())
            self.assertEqual(self.managed.describe()["error_code"], "engine_stop_blocked")
            with self.assertRaises(engine.EngineError) as again:
                self.managed.ensure(self.model(), self.settings)
            self.assertEqual(again.exception.code, "engine_stop_blocked")
        self.assertEqual(spawned, [], "a second engine was started beside a survivor")
        stub.returncode = 0           # let tearDown finish


class _PsProcess:
    """psutil.Process stand-in with controllable identity and exit."""

    def __init__(self, *, created=100.0, exe="/engine/llama-server", exits=True,
                 identity_error=None, exe_error=None):
        self.created, self._exe, self.exits = created, exe, exits
        self.identity_error, self.exe_error = identity_error, exe_error
        self.signals = []

    def create_time(self):
        if self.identity_error:
            raise self.identity_error
        return self.created

    def exe(self):
        if self.exe_error:
            raise self.exe_error
        return self._exe

    def terminate(self):
        self.signals.append("terminate")

    def kill(self):
        self.signals.append("kill")

    def wait(self, timeout=None):
        import psutil
        if not self.exits:
            raise psutil.TimeoutExpired(timeout)
        return 0


class TestOrphanEvidence(EngineBase):
    """Uncertain survivors keep their record; certain absence clears it."""

    def _record(self, create_time=100.0, executable="/engine/llama-server"):
        self.managed.home.mkdir(parents=True, exist_ok=True)
        self.managed.record_path.write_text(json.dumps(
            {"pid": 4242, "create_time": create_time, "executable": executable}),
            encoding="utf-8")

    def _reap(self, fake):
        import psutil
        factory = (lambda pid: (_ for _ in ()).throw(fake)) \
            if isinstance(fake, BaseException) else (lambda pid: fake)
        with patch.object(psutil, "Process", side_effect=factory), \
                patch.object(engine, "STOP_SECONDS", 0.01):
            return self.managed.reap_orphan()

    def assertBlocked(self, fake):
        with self.assertRaises(engine.EngineError) as caught:
            self._reap(fake)
        self.assertEqual(caught.exception.code, "engine_stop_blocked")
        self.assertTrue(self.managed.record_path.exists(), "evidence was discarded")

    def test_an_owned_orphan_that_never_exits_is_blocked_not_forgotten(self):
        self._record()
        fake = _PsProcess(exits=False)
        self.assertBlocked(fake)
        self.assertEqual(fake.signals, ["terminate", "kill"])

    def test_an_identity_that_cannot_be_read_is_blocked_and_never_signalled(self):
        import psutil
        self._record()
        fake = _PsProcess(identity_error=psutil.AccessDenied(4242))
        self.assertBlocked(fake)
        self.assertEqual(fake.signals, [])

    def test_an_executable_that_cannot_be_read_is_blocked(self):
        import psutil
        self._record()
        fake = _PsProcess(exe_error=psutil.AccessDenied(4242))
        self.assertBlocked(fake)
        self.assertEqual(fake.signals, [])

    def test_a_record_without_a_start_time_cannot_prove_the_same_engine(self):
        self._record(create_time=None)
        fake = _PsProcess()
        self.assertBlocked(fake)
        self.assertEqual(fake.signals, [])

    def test_a_recycled_pid_clears_the_record_without_a_signal(self):
        self._record(create_time=100.0)
        fake = _PsProcess(created=555.0)
        self.assertFalse(self._reap(fake))
        self.assertEqual(fake.signals, [])
        self.assertFalse(self.managed.record_path.exists())

    def test_a_process_that_is_gone_clears_the_record(self):
        import psutil
        self._record()
        self.assertFalse(self._reap(psutil.NoSuchProcess(4242)))
        self.assertFalse(self.managed.record_path.exists())

    def test_an_unreadable_record_is_kept_aside_not_deleted(self):
        self.managed.home.mkdir(parents=True, exist_ok=True)
        self.managed.record_path.write_text("{not json", encoding="utf-8")
        self.assertFalse(self.managed.reap_orphan())
        kept = list(self.managed.home.glob("engine-process.unreadable-*.json"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_text(encoding="utf-8"), "{not json")

    def test_a_blocked_orphan_prevents_a_new_launch(self):
        self._record()
        spawned = []
        self.managed._spawn = lambda *a, **k: spawned.append(a)
        import psutil
        with patch.object(psutil, "Process", return_value=_PsProcess(exits=False)), \
                patch.object(engine, "STOP_SECONDS", 0.01):
            with self.assertRaises(engine.EngineError) as caught:
                self.managed.ensure(self.model(), self.settings)
        self.assertEqual(caught.exception.code, "engine_stop_blocked")
        self.assertEqual(spawned, [])


class _Registry:
    def __init__(self, records):
        self.records = records

    def __call__(self):
        return self.records


class AdapterBase(EngineBase):
    """Helpers for driving the managed backend through `runtime.stream_chat`."""

    def components(self, projector=None):
        files = [("weights", self.weights)] + ([("projector", projector)] if projector else [])
        return tuple(local_engine.ModelComponent(role, path, path.stat().st_size,
                                                 _digest(path)) for role, path in files)

    def backend(self, *, digest="a" * 64, settings=True, projector=None, components=None):
        record = local_engine.InstalledModel(
            "qwen-test", digest, self.weights, projector,
            components=self.components(projector) if components is None else components)
        return local_engine.LocalEngine(
            self.selection, self.base / "data", registry=_Registry({"qwen-test": record}),
            settings_for=lambda _m: self.settings if settings else None,
            managed=self.managed)

    def run_stream(self, backend, *, reasoning="disabled", response_format=None,
                   should_cancel=None, images=None, profile=None):
        profile = profile or profile_for(
            decoder=("json_schema",) if response_format else ("text",))
        decoder = "json_schema" if response_format else "text"
        inference = inference_profiles.request(
            profile, reasoning=reasoning, decoder=decoder,
            decoder_schema_sha256=(inference_profiles.schema_sha256(response_format)
                                   if response_format else None))
        runtime.configure_managed(backend)
        try:
            return list(runtime.stream_chat([{"role": "user", "content": "hi"}],
                                            profile=profile, inference=inference,
                                            should_cancel=should_cancel, images=images,
                                            response_format=response_format))
        finally:
            runtime.configure_managed(None)


class TestAdapter(AdapterBase):
    def test_reasoning_is_progress_and_metrics_keep_their_names(self):
        records = self.run_stream(self.backend(), reasoning="enabled")
        kinds = [kind for kind, _ in records]
        self.assertEqual(kinds[0], "thinking")
        self.assertEqual("".join(p for k, p in records if k == "delta"), "Hello there.")
        done = records[-1][1]
        self.assertEqual(records[-1][0], "done")
        self.assertEqual((done["done_reason"], done["prompt_tokens"], done["output_tokens"],
                          done["tokens_per_s"], done["cached_prompt_tokens"]),
                         ("stop", 40, 3, 100.0, 8))
        self.assertEqual(done["reasoning"], "enabled")

    def test_cached_prompt_tokens_still_count_toward_the_context(self):
        final = {"choices": [{"finish_reason": "length"}],
                 "timings": {"prompt_n": 100, "cache_n": 3900, "predicted_n": 192}}
        profile = profile_for()
        inference = inference_profiles.request(profile, reasoning="disabled",
                                               decoder="text")
        done = runtime_llamacpp.metrics(final, inference=inference, profile=profile)
        self.assertEqual(done["prompt_tokens"], 4000)
        self.assertEqual(done["limit_reason"], "context")

    def test_reasoning_off_is_sent_as_the_template_switch(self):
        record = self.base / "request.json"
        self.set_mode("ok", record=str(record))
        records = self.run_stream(self.backend())
        self.assertNotIn("thinking", [k for k, _ in records])
        sent = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(sent["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(sent["max_tokens"], 256)

    def test_a_length_stop_names_the_output_limit(self):
        self.set_mode("length")
        done = self.run_stream(self.backend())[-1][1]
        self.assertEqual(done["done_reason"], "length")
        self.assertEqual(done["limit_reason"], "unknown")

    def test_structured_output_is_sent_as_a_json_schema(self):
        record = self.base / "request.json"
        self.set_mode("ok", record=str(record))
        schema = {"type": "object", "properties": {"a": {"type": "string"}},
                  "required": ["a"]}
        self.run_stream(self.backend(), response_format=schema)
        sent = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(sent["response_format"]["json_schema"]["schema"], schema)

    def test_an_image_rides_on_the_last_user_message(self):
        record = self.base / "request.json"
        self.set_mode("ok", record=str(record))
        self.run_stream(self.backend(), images=[b"\x89PNG..."])
        sent = json.loads(record.read_text(encoding="utf-8"))
        parts = sent["messages"][-1]["content"]
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_context_overflow_is_refused_not_trimmed(self):
        self.set_mode("overflow")
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(self.backend())
        self.assertIn("Context window exceeded", str(caught.exception))

    def test_a_malformed_stream_is_an_error_not_an_answer(self):
        self.set_mode("malformed")
        with self.assertRaises(runtime.RuntimeUnavailable):
            self.run_stream(self.backend())

    def test_stop_ends_a_stalled_stream_promptly(self):
        self.set_mode("stall")
        cancel = threading.Event()
        started = time.monotonic()
        threading.Timer(1.0, cancel.set).start()
        records = self.run_stream(self.backend(), should_cancel=cancel.is_set)
        self.assertEqual(records[-1][0], "cancelled")
        self.assertLess(time.monotonic() - started, 8.0)

    def test_a_profile_for_other_bytes_is_refused(self):
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(self.backend(digest="b" * 64))
        self.assertIn("different model bytes", str(caught.exception))

    def test_a_profile_for_another_engine_build_is_refused(self):
        with self.assertRaises(runtime.RuntimeUnavailable):
            self.run_stream(self.backend(),
                            profile=profile_for(runtime_version="b10000-metal"))

    def test_no_reviewed_preset_means_no_launch(self):
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(self.backend(settings=False))
        self.assertIn("no engine settings", str(caught.exception))
        self.assertFalse(self.managed.running)

    def test_probe_reports_installed_records_and_the_engine_identity(self):
        backend = self.backend(projector=None)
        runtime.configure_managed(backend)
        try:
            state = runtime.probe()
            self.assertEqual(state["runtime"], "llama.cpp")
            self.assertEqual(state["server_version"], "b11390-metal")
            self.assertEqual(state["models"], ["qwen-test"])
            self.assertEqual(state["digests"], {"qwen-test": "a" * 64})
            self.assertEqual(runtime.model_capabilities("qwen-test"), ["completion"])
            self.assertIsNone(runtime.model_capabilities("absent"))
        finally:
            runtime.configure_managed(None)


class TestAdmission(AdapterBase):
    """The preset's floors are checked when a model is about to load."""

    def floored(self, memory, disk=None):
        self.settings = engine.LaunchSettings(
            context_tokens=4096, min_available_memory_bytes=2 * 1024 ** 3,
            min_free_disk_bytes=1024 ** 3)
        backend = self.backend()
        backend.resources = lambda: (memory, disk)
        return backend

    def test_too_little_free_memory_refuses_before_the_engine_starts(self):
        spawned = []
        self.managed._spawn = lambda *a, **k: spawned.append(a)
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(self.floored(1024 ** 3))
        self.assertIn("1.0 GB is free and 2.0 GB is needed", str(caught.exception))
        self.assertEqual(spawned, [])

    def test_too_little_disk_refuses(self):
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(self.floored(8 * 1024 ** 3, disk=100 * 1024 ** 2))
        self.assertIn("free disk space", str(caught.exception))

    def test_a_loaded_model_is_not_refused_for_the_memory_it_already_holds(self):
        backend = self.floored(8 * 1024 ** 3, disk=8 * 1024 ** 3)
        self.run_stream(backend)
        backend.resources = lambda: (512 * 1024 ** 2, 8 * 1024 ** 3)
        records = self.run_stream(backend)
        self.assertEqual(records[-1][0], "done")

    def test_an_unknown_reading_is_not_a_refusal(self):
        records = self.run_stream(self.floored(None, None))
        self.assertEqual(records[-1][0], "done")


class TestModelBytes(AdapterBase):
    """The installed bytes are re-read, not remembered from the install record."""

    def _same_size_replacement(self, path: Path):
        data = bytearray(path.read_bytes())
        data[-1] ^= 0xFF
        replacement = path.with_name(path.name + ".new")
        replacement.write_bytes(bytes(data))
        os.replace(replacement, path)
        self.assertEqual(len(data), path.stat().st_size)

    def _counting(self, backend):
        calls = []
        original = local_engine._sha256

        def counted(path, cancelled=None):
            calls.append(Path(path).name)
            return original(path, cancelled)
        backend.checks = local_engine.FileChecks(hasher=counted)
        return calls

    def test_status_reads_do_not_hash_and_a_load_hashes_once_per_launch(self):
        backend = self.backend()
        calls = self._counting(backend)
        runtime.configure_managed(backend)
        try:
            for _ in range(3):
                state = runtime.probe()
            self.assertEqual(calls, [])
            self.assertEqual(state["file_checks"]["qwen-test"]["state"], "pending")
            self.assertEqual(state["digests"], {"qwen-test": "a" * 64})
        finally:
            runtime.configure_managed(None)
        self.run_stream(backend)
        self.run_stream(backend)
        self.assertEqual(calls, ["model.gguf"])
        runtime.configure_managed(backend)
        try:
            self.assertEqual(runtime.probe()["file_checks"]["qwen-test"]["state"],
                             "verified")
        finally:
            runtime.configure_managed(None)

    def test_changed_weights_are_refused_before_the_engine_starts(self):
        backend = self.backend()          # recorded from the installed bytes
        self._same_size_replacement(self.weights)
        spawned = []
        self.managed._spawn = lambda *a, **k: spawned.append(a)
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(backend)
        self.assertIn("not the verified file", str(caught.exception))
        self.assertEqual(spawned, [])

    def test_a_same_size_replacement_after_a_verified_load_unloads_the_model(self):
        backend = self.backend()
        self.run_stream(backend)
        self.assertTrue(self.managed.running)
        self._same_size_replacement(self.weights)
        runtime.configure_managed(backend)
        try:
            # Changed identity: no longer vouched for, though not yet re-read.
            self.assertEqual(runtime.probe()["file_checks"]["qwen-test"]["state"],
                             "pending")
        finally:
            runtime.configure_managed(None)
        with self.assertRaises(runtime.RuntimeUnavailable):
            self.run_stream(backend)
        self.assertFalse(self.managed.running, "the changed model stayed loaded")
        runtime.configure_managed(backend)
        try:
            state = runtime.probe()
            self.assertEqual(state["file_checks"]["qwen-test"]["state"], "mismatch")
            self.assertEqual(state["models"], ["qwen-test"])
            self.assertEqual(state["digests"], {}, "a changed model kept its digest")
        finally:
            runtime.configure_managed(None)

    def test_a_changed_projector_is_refused(self):
        projector = self.base / "mmproj.gguf"
        projector.write_bytes(b"GGUF" + b"\1" * 32)
        backend = self.backend(projector=projector)
        self._same_size_replacement(projector)
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(backend)
        self.assertIn("mmproj.gguf", str(caught.exception))

    def test_a_size_change_is_seen_by_a_status_read_without_hashing(self):
        backend = self.backend()
        calls = self._counting(backend)
        with open(self.weights, "ab") as handle:
            handle.write(b"x")
        runtime.configure_managed(backend)
        try:
            state = runtime.probe()
            self.assertEqual(state["file_checks"]["qwen-test"]["state"], "mismatch")
            self.assertIsNone(runtime.model_capabilities("qwen-test"))
        finally:
            runtime.configure_managed(None)
        self.assertEqual(calls, [])

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symbolic links")
    def test_a_link_in_place_of_the_file_is_refused(self):
        copy = self.base / "copy.gguf"
        shutil.copyfile(self.weights, copy)
        components = self.components()
        self.weights.unlink()
        self.weights.symlink_to(copy)
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(self.backend(components=components))
        self.assertIn("not a regular file", str(caught.exception))

    def test_a_record_without_file_identities_is_never_loaded(self):
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            self.run_stream(self.backend(components=()))
        self.assertIn("no file identities", str(caught.exception))
        self.assertFalse(self.managed.running)


class TestCoordinatorRecords(EngineBase):
    """Install records carry file identities into the engine boundary and status."""

    def setUp(self):
        super().setUp()
        from backend.coordinator import db, models, server
        self.db, self.models = db, models
        self.coordinator = server.Coordinator(self.base / "state" / "coordinator.sqlite3")
        self.coordinator.preflight = lambda relationship=None: None
        root = db.models_root(self.coordinator.state_path)
        root.mkdir(parents=True)
        self.installed = root / "main.gguf"
        shutil.copyfile(self.weights, self.installed)
        self.entry = models.BY_ID[models.MANAGED_MAIN]

    def tearDown(self):
        runtime.configure_managed(None)
        self.coordinator.conn.close()
        super().tearDown()

    def _record(self, path="main.gguf", **changes):
        item = {"role": "weights", "name": "main.gguf", "path": path,
                "size": self.installed.stat().st_size, "sha256": _digest(self.installed),
                **changes}
        self.db.record_model_install(
            self.coordinator.conn, model_id=self.entry.id,
            manifest_sha256=self.entry.manifest_sha256, engine="llama.cpp",
            files=[item], source="test")

    def _configure(self):
        backend = local_engine.LocalEngine(
            self.selection, self.base / "data", registry=self.coordinator.installed_models,
            settings_for=lambda _m: None, managed=self.managed)
        runtime.configure_managed(backend)
        return backend

    def test_the_recorded_size_and_hash_reach_the_engine_boundary(self):
        self._record()
        record = self.coordinator.installed_models()[self.entry.id]
        (component,) = record.components
        self.assertEqual((component.path, component.size, component.sha256),
                         (self.installed, self.installed.stat().st_size,
                          _digest(self.installed)))

    def test_a_record_whose_path_leaves_the_models_folder_is_ignored(self):
        self._record(path="../outside.gguf")
        self.assertEqual(self.coordinator.installed_models(), {})

    def test_verified_files_without_a_measured_preset_run_with_upstream_fitting(self):
        """No team measurement for this computer is not a refusal: the model
        runs under an honest candidate profile with upstream fitting at a fixed
        window, and nothing about it is labelled measured."""
        self._record()
        self._configure()
        ready = self.coordinator.chat_readiness()
        self.assertEqual(ready["code"], "ready")
        profile = self.coordinator.local_profile(
            workflow=inference_profiles.CHAT, model_id=self.entry.id,
            reasoning="disabled", decoder="text")
        self.assertEqual(profile.qualification_state, "candidate")
        self.assertFalse(profile.eligible)
        settings = self.coordinator.engine_settings_for(self.entry.id, profile)
        self.assertEqual((settings.fit, settings.gpu_layers, settings.measured),
                         ("on", "auto", False))
        self.assertEqual(settings.context_tokens, profile.qualified_context_tokens)
        self.assertIn("-c", settings.arguments())
        self.assertIn("--fit-target", settings.arguments())

    def test_changed_files_are_reported_as_changed_not_absent(self):
        self._record()
        self._configure()
        with open(self.installed, "ab") as handle:
            handle.write(b"x")
        row = next(r for r in self.coordinator.model_inventory()
                   if r["id"] == self.entry.id)
        self.assertEqual(row["integrity"]["local"]["state"], "mismatch")
        self.assertEqual(row["eligible_scopes"], [])
        ready = self.coordinator.chat_readiness()
        self.assertEqual(ready["code"], "model_integrity_mismatch")
        self.assertIn("main.gguf", ready["detail"])

    def test_a_selected_model_switched_off_is_not_ready(self):
        self._record()
        self._configure()
        self.db.set_model_enabled(self.coordinator.conn, self.entry.id, False)
        self.assertEqual(self.coordinator.chat_readiness()["code"], "model_disabled")

    def test_a_matching_tier_with_its_reviewed_preset_is_ready(self):
        self._record()
        self._configure()
        self.coordinator.tier_ids = [inference_profiles.MAC_TIER]
        self.assertEqual(self.coordinator.chat_readiness()["code"], "ready")
        settings = self.coordinator.engine_settings_for(self.entry.id)
        self.assertEqual((settings.context_tokens, settings.slots, settings.gpu_layers),
                         (8192, 1, "all"))

    def test_another_tier_has_no_preset_and_still_runs(self):
        self._record()
        self._configure()
        self.coordinator.tier_ids = ["linux-x64-cpu-16g"]
        # No measured preset to apply as-is...
        self.assertIsNone(self.coordinator.engine_settings_for(self.entry.id))
        # ...yet the model still runs, with upstream fitting, not refused.
        self.assertEqual(self.coordinator.chat_readiness()["code"], "ready")

    def test_status_and_startup_share_one_readiness_answer(self):
        self._record()
        self._configure()
        self.assertEqual(self.coordinator.status()["readiness"],
                         self.coordinator.chat_readiness())


class TestHardwareTiers(unittest.TestCase):
    """A Linux version number only counts within its own distribution."""

    def facts(self, distribution, version, *, devices=None):
        return {"os_family": "linux", "os_distribution": distribution,
                "os_version_tuple": list(version), "architecture": "x86_64",
                "cpu_brand": "Some CPU", "memory_total_bytes": 16 * 1024 ** 3,
                "engine_devices": devices}

    def tiers(self, facts):
        return [t.tier_id for t in inference_profiles.matching_tiers(facts)]

    def test_ubuntu_24_04_matches_the_ubuntu_tier(self):
        self.assertEqual(self.tiers(self.facts("ubuntu", (24, 4))), ["linux-x64-cpu-16g"])

    def test_another_distribution_with_a_larger_version_does_not_match(self):
        for distribution, version in (("fedora", (41,)), ("debian", (25,)),
                                      ("linuxmint", (24, 4)), (None, (24, 4))):
            with self.subTest(distribution=distribution):
                self.assertEqual(self.tiers(self.facts(distribution, version)), [])

    def test_ubuntu_releases_outside_the_reviewed_range_do_not_match(self):
        for version in ((22, 4), (24, 10), (26, 4)):
            with self.subTest(version=version):
                self.assertEqual(self.tiers(self.facts("ubuntu", version)), [])

    def test_the_gpu_tier_still_needs_a_matching_device(self):
        device = [{"id": "Vulkan0", "memory_mib": 4096}]
        self.assertEqual(self.tiers(self.facts("ubuntu", (24, 4), devices=device)),
                         ["linux-x64-vulkan-4g-16g", "linux-x64-cpu-16g"])

    def test_the_distribution_is_kept_as_a_structured_fact(self):
        from backend.coordinator import device
        with patch.object(device.sys, "platform", "linux"), \
                patch.object(device._platform, "freedesktop_os_release",
                             return_value={"ID": "Ubuntu", "VERSION_ID": "24.04",
                                           "ID_LIKE": "debian"}, create=True):
            self.assertEqual(device.os_distribution(), "ubuntu")
        with patch.object(device.sys, "platform", "linux"), \
                patch.object(device._platform, "freedesktop_os_release",
                             side_effect=OSError, create=True):
            self.assertIsNone(device.os_distribution())
        self.assertIn("os_distribution", device.hardware())


class TestRegisteredPresets(unittest.TestCase):
    """Every shipped preset and managed profile is tied to its evidence file."""

    REPO = Path(__file__).resolve().parents[2]

    def test_each_preset_names_a_tier_and_the_catalogued_model_bytes(self):
        from backend.coordinator import models
        entry = models.BY_ID[models.MANAGED_MAIN]
        self.assertEqual(inference_profiles.MANAGED_MODEL_ID, entry.id)
        self.assertEqual(inference_profiles.MANAGED_MODEL_DIGEST, entry.manifest_sha256)
        pins = json.loads((self.REPO / "desktop" / "engine" / "engine-pins.json")
                          .read_text(encoding="utf-8"))
        for preset in inference_profiles.PRESETS:
            self.assertIn(preset.tier_id, inference_profiles.TIERS_BY_ID)
            self.assertEqual(preset.manifest_sha256, entry.manifest_sha256)
            self.assertTrue(preset.runtime_version.startswith(pins["release"] + "-"))
            for ref in preset.evidence_ref.split("; "):
                self.assertTrue((self.REPO / ref).is_file(), ref)

    def test_each_preset_has_the_profiles_it_was_measured_with(self):
        for preset in inference_profiles.PRESETS:
            mine = [p for p in inference_profiles.PROFILES
                    if p.target_profile_id == preset.tier_id]
            self.assertEqual({p.workflow_mode for p in mine},
                             {inference_profiles.CHAT, inference_profiles.CODE,
                              inference_profiles.DOCUMENTS})
            for profile in mine:
                self.assertEqual((profile.model.model_id, profile.model.manifest_sha256,
                                  profile.model.runtime, profile.model.runtime_version,
                                  profile.qualified_context_tokens),
                                 (preset.model_id, preset.manifest_sha256, "llama.cpp",
                                  preset.runtime_version, preset.context_tokens))

    def test_registered_managed_profiles_match_their_qualification_artifact(self):
        from backend.contracts import qualification
        managed = [p for p in inference_profiles.PROFILES if p.model.runtime == "llama.cpp"]
        self.assertTrue(managed)
        for profile in managed:
            artifact = qualification.read(self.REPO / profile.evidence_ref)
            self.assertEqual(artifact.result, "passed")
            self.assertFalse(artifact.release_accepted)
            self.assertEqual(artifact.observed_model, profile.model)
            measured = next(w.profile for w in artifact.workflows
                            if w.profile.workflow_mode == profile.workflow_mode)
            for field in ("target_profile_id", "qualified_context_tokens",
                          "default_output_tokens", "max_output_tokens",
                          "reasoning_modes", "default_reasoning", "decoder_modes"):
                self.assertEqual(getattr(measured, field), getattr(profile, field), field)

    def test_documents_is_not_offered_with_reasoning_on_for_the_managed_model(self):
        documents = [p for p in inference_profiles.PROFILES
                     if p.model.runtime == "llama.cpp"
                     and p.workflow_mode == inference_profiles.DOCUMENTS]
        self.assertTrue(documents)
        for profile in documents:
            self.assertEqual(profile.reasoning_modes, ["disabled"])

    def test_no_preset_exists_without_measured_evidence(self):
        for preset in inference_profiles.PRESETS:
            self.assertEqual(preset.evidence_kind, "measured_refinix")
            self.assertIsNotNone(preset.measured_peak_rss_bytes)


class TestListDevices(unittest.TestCase):
    def test_the_engine_device_listing_is_parsed(self):
        selection = engine.Selection(engine.MANAGED, engine.LLAMA_CPP, "t", Path("/x"),
                                     {"executable": "llama-server", "release": "b1",
                                      "backend": "metal"}, [])
        output = ("Available devices:\n  MTL0: Apple M5 (12124 MiB, 12123 MiB free)\n"
                  "  BLAS: Accelerate (0 MiB, 0 MiB free)\n")
        result = subprocess.CompletedProcess([], 0, output, "")
        devices = engine.list_devices(selection, run=lambda *a, **k: result)
        self.assertEqual(devices[0], {"id": "MTL0", "name": "Apple M5",
                                      "memory_mib": 12124, "free_mib": 12123})

    def test_an_unverified_engine_is_not_asked(self):
        selection = engine.Selection(engine.MANAGED, engine.LLAMA_CPP, "t", None, None,
                                     ["missing"])
        self.assertIsNone(engine.list_devices(selection))


if __name__ == "__main__":
    unittest.main(verbosity=2)
