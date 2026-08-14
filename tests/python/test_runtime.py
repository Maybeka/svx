from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

import pytest

from svx import SVXError
from svx import _registry
from svx import runtime


@dataclass
class Capabilities:
    package_major_version: int = 1
    schema_format_version: int = 1
    binary_format_version: int = 1
    object_envelope_version: int = 2
    generator_runtime_abi_version: int = 1
    provided: tuple[str, ...] = (
        "svtypes.checked-encoding-descriptor.v1",
        "svtypes.codec-context.v1",
        "svtypes.record-schema.v1",
        "svtypes.remote-reference.v1",
    )


class Session:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    import svtypes

    runtime._state = runtime.RuntimeState.UNINITIALIZED
    runtime._codec_session = None
    runtime._svtypes_capabilities = None
    monkeypatch.setattr(svtypes, "runtime_capabilities", lambda: Capabilities(), raising=False)
    monkeypatch.setattr(svtypes, "CodecSession", Session, raising=False)
    monkeypatch.delenv("SVX_ARTIFACT_MANIFEST", raising=False)
    _registry.clear()
    yield
    runtime._state = runtime.RuntimeState.UNINITIALIZED
    runtime._codec_session = None
    runtime._svtypes_capabilities = None
    _registry.clear()


def test_runtime_initializes_one_codec_session_and_shuts_down_idempotently():
    runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert runtime.state() is runtime.RuntimeState.INITIALIZING
    runtime._native_finish_initialize()
    session = runtime.codec_session()

    assert runtime.state() is runtime.RuntimeState.READY
    runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert runtime.codec_session() is session

    runtime._native_shutdown()
    assert session.closed
    assert runtime.state() is runtime.RuntimeState.STOPPED
    runtime._native_shutdown()
    assert runtime.state() is runtime.RuntimeState.STOPPED


def test_runtime_rejects_abi_and_missing_svtypes_capabilities(monkeypatch):
    with pytest.raises(SVXError, match="Python/native ABI mismatch"):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION + 1)

    import svtypes

    monkeypatch.setattr(
        svtypes,
        "runtime_capabilities",
        lambda: Capabilities(provided=("svtypes.checked-encoding-descriptor.v1",)),
        raising=False,
    )
    with pytest.raises(SVXError, match="missing required SVX capabilities"):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert runtime.state() is runtime.RuntimeState.UNINITIALIZED


@pytest.mark.parametrize(
    ("field", "expected", "message"),
    (
        ("package_major_version", 1, r"SvTypes major 1, got 2"),
        ("schema_format_version", 1, r"schema_format_version 1, got 2"),
        ("binary_format_version", 1, r"binary_format_version 1, got 2"),
        ("object_envelope_version", 2, r"object_envelope_version 2, got 3"),
        (
            "generator_runtime_abi_version",
            1,
            r"generator_runtime_abi_version 1, got 2",
        ),
    ),
)
def test_runtime_rejects_incompatible_svtypes_format_versions(
    monkeypatch, field, expected, message
):
    import svtypes

    received = expected + 1
    monkeypatch.setattr(
        svtypes,
        "runtime_capabilities",
        lambda: Capabilities(**{field: received}),
        raising=False,
    )
    with pytest.raises(SVXError, match=message):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert runtime.state() is runtime.RuntimeState.UNINITIALIZED


def test_runtime_rejects_native_product_version_mismatch():
    with pytest.raises(SVXError, match="product version mismatch"):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION, "9.9.9")
    assert runtime.state() is runtime.RuntimeState.UNINITIALIZED


def test_shutdown_clears_python_exports():
    _registry.register("runtime.test", lambda: None)
    runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    runtime._native_finish_initialize()
    runtime._native_shutdown()
    assert _registry.list_exports() == {}


def test_stopped_runtime_cannot_restart():
    runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    runtime._native_shutdown()
    with pytest.raises(SVXError, match="cannot initialize from state 'stopped'"):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)


def test_failed_initialization_rolls_back_codec_session():
    runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    session = runtime._codec_session
    runtime._native_abort_initialize()

    assert session.closed
    assert runtime.state() is runtime.RuntimeState.UNINITIALIZED
    assert runtime._codec_session is None


def test_generated_artifacts_are_checked_and_imported_before_ready(
    tmp_path, monkeypatch
):
    package = tmp_path / "generated"
    package.mkdir()
    source = package / "mirrors.py"
    source.write_text("VALUE = 17\n")
    manifest = tmp_path / "artifacts.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_uri": "https://svx.dev/schema/generated-artifacts/v1",
                "schema_version": "1.0.0",
                "generator_abi_version": runtime.SVX_GENERATOR_ABI_VERSION,
                "svx_runtime_abi_version": runtime.SVX_RUNTIME_ABI_VERSION,
                "svtypes": {"required_package_major": 1},
                "inheritance_manifest": {
                    "schema_uri": "https://svx.dev/schema/inheritance-manifest/v2",
                    "schema_version": "2.0.0",
                },
                "required_runtime_capabilities": ["svtypes.record-schema.v1"],
                "types": [],
                "callables": [],
                "constructors": [],
                "artifacts": [
                    {
                        "language": "python",
                        "path": "generated/mirrors.py",
                        "module": "generated.mirrors",
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("SVX_ARTIFACT_MANIFEST", str(manifest))

    runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert runtime.state() is runtime.RuntimeState.INITIALIZING

    source.write_text("VALUE = 18\n")
    runtime._native_abort_initialize()
    with pytest.raises(SVXError, match="hash mismatch"):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
