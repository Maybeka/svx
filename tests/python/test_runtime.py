from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys

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


@pytest.mark.parametrize('name', [
    'is_materializable_type', 'materialize_type_spec',
    'type_spec_identity', 'type_spec_from_identity',
])
@pytest.mark.parametrize('replacement', ['missing', 'noncallable'])
def test_missing_public_type_spec_api_rejects_before_runtime_or_user_type_error(monkeypatch, name, replacement):
    import svtypes
    from svx.declarations import _svtypes_binding
    from svx.inheritance import _codec_from_spec
    from svx.errors import SVXInheritanceError

    if replacement == 'missing':
        monkeypatch.delattr(svtypes, name)
    else:
        monkeypatch.setattr(svtypes, name, None)
    monkeypatch.setattr(svtypes, 'CodecSession', lambda: pytest.fail('created incompatible session'))
    with pytest.raises(SVXError, match='requires SvTypes >= 1.4.2') as error:
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert name in str(error.value)
    assert runtime.state() is runtime.RuntimeState.UNINITIALIZED
    assert runtime._codec_session is None
    with pytest.raises(SVXError, match='requires SvTypes >= 1.4.2'):
        _svtypes_binding(svtypes.Int, where='method parameter')
    with pytest.raises(SVXInheritanceError, match='requires SvTypes >= 1.4.2'):
        _codec_from_spec({'svtypes': {}})


@pytest.mark.parametrize('replacement', ['missing', 'noncallable'])
def test_missing_public_codec_template_rejects_before_session_creation(monkeypatch, replacement):
    import svtypes

    if replacement == 'missing':
        monkeypatch.delattr(svtypes.SvObject, 'codec_template')
    else:
        monkeypatch.setattr(svtypes.SvObject, 'codec_template', None)
    monkeypatch.setattr(svtypes, 'CodecSession', lambda: pytest.fail('created incompatible session'))
    with pytest.raises(SVXError, match=r'SvObject\.codec_template\(\)'):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert runtime.state() is runtime.RuntimeState.UNINITIALIZED
    assert runtime._codec_session is None


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


def test_real_codec_session_shutdown_boundary_in_fresh_process():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / 'tests/integration/runtime_session_shutdown_probe.py')],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'REAL_CODEC_SESSION_SHUTDOWN_PYTHON_BOUNDARY_PASS' in result.stdout


def test_stopped_runtime_cannot_restart():
    runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    runtime._native_shutdown()
    with pytest.raises(SVXError, match="cannot initialize from state 'stopped'"):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)


@pytest.mark.parametrize("old_abi", [1, 2])
def test_previous_runtime_and_generated_artifacts_are_rejected(tmp_path, monkeypatch, old_abi):
    with pytest.raises(SVXError, match=f"native reports {old_abi}"):
        runtime._native_initialize(old_abi)
    manifest = tmp_path / "old-artifacts.json"
    manifest.write_text(json.dumps({
        "schema_uri": "https://svx.dev/schema/generated-artifacts/v1",
        "schema_version": "1.0.0",
        "generator_abi_version": runtime.SVX_GENERATOR_ABI_VERSION,
        "svx_runtime_abi_version": old_abi,
    }))
    monkeypatch.setenv("SVX_ARTIFACT_MANIFEST", str(manifest))
    with pytest.raises(SVXError, match=f"runtime expects 3, artifact reports {old_abi}"):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert runtime.state() is runtime.RuntimeState.UNINITIALIZED


def test_native_sv_and_python_runtime_abi_versions_match():
    root = Path(__file__).resolve().parents[2]
    version = runtime.SVX_RUNTIME_ABI_VERSION
    header = (root / "svx_runtime/include/svx/python_runtime.hpp").read_text()
    sv = (root / "sv/svx_init.sv").read_text()
    assert f"SVX_RUNTIME_ABI_VERSION = {version};" in header
    assert f"SVX_SV_RUNTIME_ABI_VERSION = {version};" in header
    assert f"SVX_SV_RUNTIME_ABI_VERSION = {version};" in sv


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
    data = json.loads(manifest.read_text())
    data['types'] = [{'unified_type_name': 'unresolved'}]
    manifest.write_text(json.dumps(data))
    from svx import inheritance

    calls = []
    def forbidden_factory(spec):
        calls.append(spec)
        raise AssertionError('corrupt artifacts must fail before codec factories run')

    monkeypatch.setattr(inheritance, '_codec_from_spec', forbidden_factory)
    with pytest.raises(SVXError, match="hash mismatch"):
        runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    assert calls == []
