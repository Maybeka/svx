import json
import sys
from dataclasses import make_dataclass
from io import StringIO

import pytest
import svtypes
from svtypes import Int, String, encoding_descriptor, unified_type_name

from svx import SVXInheritanceError
from svx import SVXRemoteError
from svx import SVXReadonlyRefError, SVXStaleRefError
from svx.cli import main
from svx.inheritance import (
    SCHEMA_URI,
    SCHEMA_VERSION,
    dispatch_python_call,
    emit_python_mirrors,
    emit_sv_mirrors,
    encode_constructor,
    invoke_sv,
    migrate_manifest,
    parse_manifest,
    projection_plan,
    Ref,
    register_contract,
    register_constructor,
    register_python_subclass,
    response_type,
    create_python_instance,
)
from svx import runtime


@pytest.fixture(autouse=True)
def inheritance_codec_session():
    runtime._state = runtime.RuntimeState.READY
    runtime._codec_session = svtypes.CodecSession()
    yield
    runtime._state = runtime.RuntimeState.UNINITIALIZED
    runtime._codec_session = None


def type_ref(factory, *, sv: str, sv_packer: str, args=(), module="svtypes", symbol=None):
    codec = factory(*args)
    return {
        "unified_type_name": unified_type_name(codec),
        "python": {
            "module": module,
            "symbol": symbol or factory.__name__,
            "args": list(args),
            "kwargs": {},
        },
        "sv": sv,
        "sv_packer": sv_packer,
        "encoding_descriptor": encoding_descriptor(codec).to_dict(),
    }


INT = type_ref(Int, sv="int", sv_packer="int_packer")
STRING = type_ref(String, sv="string", sv_packer="string_packer")


def manifest_data() -> dict:
    return {
        "schema_uri": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "generator_abi_version": 2,
        "required_runtime_capabilities": [
            "svtypes.checked-encoding-descriptor.v1",
            "svtypes.codec-context.v1",
            "svtypes.record-schema.v1",
            "svtypes.remote-reference.v1",
        ],
        "classes": [
            {
                "canonical_id": "sv://tb_pkg/BaseDriver",
                "language": "sv",
                "symbol": "tb_pkg::BaseDriver",
                "methods": [
                    {
                        "canonical_id": "sv://tb_pkg/BaseDriver#drive",
                        "name": "drive",
                        "parameters": [{"name": "address", "type": INT}],
                        "return_type": "void",
                        "timing": "task",
                        "virtual": True,
                        "pure_virtual": False,
                    }
                ],
            },
            {
                "canonical_id": "py://checks/BaseMonitor",
                "language": "python",
                "symbol": "checks.BaseMonitor",
                "methods": [
                    {
                        "canonical_id": "py://checks/BaseMonitor#sample",
                        "name": "sample",
                        "parameters": [],
                        "return_type": "void",
                        "timing": "task",
                        "virtual": True,
                        "pure_virtual": True,
                    }
                ],
            },
        ],
    }


def test_manifest_emits_language_specific_mirrors():
    manifest = parse_manifest(manifest_data())

    python_files = emit_python_mirrors(manifest)
    assert {str(path) for path in python_files} == {
        "svx_py/__init__.py",
        "svx_py/checks.py",
        "svx_sv/__init__.py",
        "svx_sv/tb_pkg.py",
    }
    mirror_text = next(text for path, text in python_files.items() if str(path) == "svx_sv/tb_pkg.py")
    assert "class BaseDriver" in mirror_text
    assert "def drive(self, address):" in mirror_text
    assert "'unified_type_name': 'svtypes.Int'" in mirror_text
    assert "svtypes.Int()" not in mirror_text

    sv_text = emit_sv_mirrors(manifest)
    assert "package svx_projection_checks_pkg;" in sv_text
    assert "virtual class BaseMonitorProxy implements svx_dispatchable;" in sv_text
    assert "virtual task sample();" in sv_text
    assert "python_proxy" not in sv_text


def test_python_initiated_sv_base_without_cross_language_lineage_has_no_sv_proxy():
    data = manifest_data()
    data["classes"][0]["constructor"] = {
        "initiator": "python",
        "parameters": [{"name": "seed", "type": INT}],
    }
    manifest = parse_manifest(data)

    python_text = emit_python_mirrors(manifest)[next(
        path for path in emit_python_mirrors(manifest) if str(path) == "svx_sv/tb_pkg.py"
    )]
    assert "def __init__(self, seed):" in python_text
    assert "_native.inheritance_create_sv('sv://tb_pkg/BaseDriver'" in python_text
    assert "encode_constructor('sv://tb_pkg/BaseDriver', {'seed': seed})" in python_text

    sv_text = emit_sv_mirrors(manifest)
    assert "BaseDriver_python_proxy" not in sv_text
    assert "svx_pyproxy_" not in sv_text


def test_manifest_rejects_cross_language_contract_errors():
    invalid = manifest_data()
    invalid["classes"][0]["unknown"] = True
    with pytest.raises(SVXInheritanceError, match="contains unsupported fields: unknown"):
        parse_manifest(invalid)

    invalid = manifest_data()
    invalid["classes"][0]["methods"][0]["canonical_id"] = "sv://tb_pkg/BaseDriver#wrong"
    with pytest.raises(SVXInheritanceError, match="must be 'sv://tb_pkg/BaseDriver#drive'"):
        parse_manifest(invalid)

    invalid = manifest_data()
    invalid["classes"][0]["methods"][0]["parameters"][0]["direction"] = "const"
    with pytest.raises(SVXInheritanceError, match="must be input, output, inout, or ref"):
        parse_manifest(invalid)

    valid = manifest_data()
    valid["classes"][0]["methods"][0]["parameters"][0]["direction"] = "output"
    parse_manifest(valid)

    invalid = manifest_data()
    invalid["classes"][0]["methods"][0]["return_type"] = INT
    with pytest.raises(SVXInheritanceError, match="task methods must have return_type 'void'"):
        parse_manifest(invalid)

    invalid = manifest_data()
    method = invalid["classes"][0]["methods"][0]
    method["timing"] = "function"
    method["return_type"] = INT
    method["parameters"][0]["name"] = "result"
    method["parameters"][0]["direction"] = "output"
    with pytest.raises(SVXInheritanceError, match="reserved"):
        parse_manifest(invalid)

    invalid = manifest_data()
    invalid["classes"][0]["constructor"] = {"initiator": "host", "parameters": []}
    with pytest.raises(SVXInheritanceError, match="must be 'python' or 'sv'"):
        parse_manifest(invalid)

    invalid = manifest_data()
    invalid["classes"][0]["constructor"] = {
        "initiator": "python",
        "parameters": [
            {"name": "name", "type": INT},
            {"name": "name", "type": INT},
        ],
    }
    with pytest.raises(SVXInheritanceError, match="duplicate parameter names"):
        parse_manifest(invalid)


def test_sv_generation_implements_completion_time_copy_out():
    data = manifest_data()
    method = data["classes"][0]["methods"][0]
    method["parameters"] = [
        {"name": "source", "type": INT, "direction": "input"},
        {"name": "changed", "type": INT, "direction": "inout"},
        {"name": "observed", "type": INT, "direction": "output"},
    ]
    data["classes"].append(
        {
            "canonical_id": "py://checks/PythonDriver",
            "language": "python",
            "symbol": "checks.PythonDriver",
            "methods": [],
            "base_lineage": [data["classes"][0]],
        }
    )
    manifest = parse_manifest(data)
    text = emit_sv_mirrors(manifest)

    assert "input int source, inout int changed, output int observed" in text
    assert "package svx_call_records_pkg;" in text
    outbound = text.split("virtual task drive", 1)[1].split("endtask", 1)[0]
    assert "request_value.source = source;" in outbound
    assert "request_value.changed = changed;" in outbound
    assert "request_value.observed" not in outbound
    assert outbound.count("request_value.pack(bytes);") == 1
    assert "changed = response_value.changed;" in outbound
    assert "observed = response_value.observed;" in outbound

    python_text = emit_python_mirrors(manifest)[
        next(
            path
            for path in emit_python_mirrors(manifest)
            if str(path) == "svx_mirrors/tb_pkg.py"
        )
    ]
    assert "def drive(self, source, changed):" in python_text
    compile(python_text, "generated/tb_pkg.py", "exec")


def test_manifest_rejects_generated_sv_name_collision():
    data = manifest_data()
    data["classes"].append(
        {
            "canonical_id": "py://other/BaseMonitor",
            "language": "python",
            "symbol": "checks.BaseMonitor",
            "methods": [],
        }
    )
    with pytest.raises(SVXInheritanceError, match="generated SystemVerilog name"):
        parse_manifest(data)


def test_alternating_lineage_generates_only_required_mirror_and_proxy():
    """A -> B -> C generates AMirror/BProxy, never an unrequested C helper."""

    data = {
        "schema_uri": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "generator_abi_version": 2,
        "required_runtime_capabilities": [
            "svtypes.checked-encoding-descriptor.v1",
            "svtypes.codec-context.v1",
            "svtypes.record-schema.v1",
            "svtypes.remote-reference.v1",
            "svtypes.external-field-storage.v1",
        ],
        "classes": [
            {
                "canonical_id": "sv://drivers/A",
                "language": "sv",
                "symbol": "drivers::A",
                "methods": [
                    {
                        "canonical_id": "sv://drivers/A#check",
                        "name": "check",
                        "parameters": [],
                        "return_type": "void",
                        "timing": "task",
                        "virtual": True,
                        "pure_virtual": False,
                    }
                ],
            },
            {
                "canonical_id": "py://checks/B",
                "language": "python",
                "symbol": "checks.B",
                "fields": [{"name": "retry", "type": INT}],
                "methods": [
                    {
                        "canonical_id": "py://checks/B#check",
                        "name": "check",
                        "parameters": [],
                        "return_type": "void",
                        "timing": "task",
                        "virtual": True,
                        "pure_virtual": False,
                    }
                ],
            },
            {
                "canonical_id": "sv://drivers/C",
                "language": "sv",
                "symbol": "drivers::C",
                "methods": [],
                "base_lineage": [
                    {
                        "canonical_id": "sv://drivers/A",
                        "language": "sv",
                        "symbol": "drivers::A",
                        "methods": [
                            {
                                "canonical_id": "sv://drivers/A#check",
                                "name": "check",
                                "parameters": [],
                                "return_type": "void",
                                "timing": "task",
                                "virtual": True,
                                "pure_virtual": False,
                            }
                        ],
                    },
                    {
                        "canonical_id": "py://checks/B",
                        "language": "python",
                        "symbol": "checks.B",
                        "fields": [{"name": "retry", "type": INT}],
                        "methods": [
                            {
                                "canonical_id": "py://checks/B#check",
                                "name": "check",
                                "parameters": [],
                                "return_type": "void",
                                "timing": "task",
                                "virtual": True,
                                "pure_virtual": False,
                            }
                        ],
                    },
                ],
            },
        ],
    }
    manifest = parse_manifest(data)
    plan = projection_plan(manifest.classes[-1])
    assert [(step.kind, step.generated_name) for step in plan.steps] == [
        ("sv_mirror", "AMirror"),
        ("sv_proxy", "BProxy"),
    ]

    text = emit_sv_mirrors(manifest)
    assert "class AMirror extends A implements svx_dispatchable;" in text
    assert "class BProxy extends AMirror implements svx_dispatchable;" in text
    assert "int retry;" in text
    assert '"py://checks/B.retry@svx_field_read"' in text
    # BProxy delegates A's explicit base gateway to AMirror instead of calling
    # the AMirror virtual override and re-entering B.check().
    bproxy = text.split("class BProxy", 1)[1].split("endclass : BProxy", 1)[0]
    assert "default: super.svx_invoke(method_id, request, ok, response, error);" in bproxy
    assert "class CMirror" not in text
    assert "A_python_proxy" not in text
    assert "virtual class B implements" not in text
    python_files = emit_python_mirrors(manifest)
    mirror_path = next(path for path in python_files if str(path) == "svx_mirrors/drivers.py")
    python_mirror = python_files[mirror_path]
    assert "class AMirror(SVMirror):" in python_mirror
    assert "register_python_subclass('sv://drivers/A', cls)" in python_mirror
    assert "inheritance_create_sv('sv://drivers/A'" in python_mirror
    compile(python_mirror, "generated/svx_mirrors/drivers.py", "exec")


def test_ref_enforces_readonly_and_borrowed_lifetime():
    value = Ref(3)
    assert value.value == 3
    value.value = 4
    assert value.value == 4

    readonly = Ref(1)

    class Endpoint:
        def read(self):
            return 1

        def write(self, value):
            raise AssertionError("must not write through const ref")

    readonly._bind(Endpoint(), readonly=True)
    with pytest.raises(SVXReadonlyRefError):
        readonly.value = 2

    borrowed = Ref()
    borrowed._bind(Endpoint(), borrowed=True)
    borrowed._close(retain_value=False)
    with pytest.raises(SVXStaleRefError):
        _ = borrowed.value


def test_inheritance_gen_cli_writes_mirrors(tmp_path):
    manifest_path = tmp_path / "inheritance.json"
    manifest_path.write_text(json.dumps(manifest_data()))
    python_out = tmp_path / "python"
    sv_out = tmp_path / "mirrors.sv"
    artifacts_out = tmp_path / "artifacts.json"
    out = StringIO()

    assert main(
        [
            "inheritance-gen",
            "--manifest",
            str(manifest_path),
            "--python-out",
            str(python_out),
            "--sv-out",
            str(sv_out),
            "--artifact-manifest",
            str(artifacts_out),
        ],
        out=out,
    ) == 0

    assert (python_out / "svx_sv" / "tb_pkg.py").is_file()
    assert "BaseDriver" in (python_out / "svx_sv" / "tb_pkg.py").read_text()
    assert "package svx_projection_checks_pkg;" in sv_out.read_text()
    artifacts = json.loads(artifacts_out.read_text())
    assert artifacts["generator_abi_version"] == 2
    assert artifacts["svx_runtime_abi_version"] == 1
    assert artifacts["svtypes"]["required_package_major"] == 1
    drive = next(
        call
        for call in artifacts["callables"]
        if call["canonical_id"] == "sv://tb_pkg/BaseDriver#drive"
    )
    assert drive["request_fields"][0]["name"] == "address"
    assert drive["request_record"]["unified_type_name"].startswith("svx.call.")
    assert drive["request_record"]["unified_type_name"].endswith(".request")
    assert drive["request_record"]["encoding_descriptor"]["encoding_fingerprint"]
    assert drive["request_record"]["sv_class"].endswith("_Request")
    assert drive["response_record"] is None
    assert artifacts["constructors"] == []
    assert artifacts["types"][0]["encoding_descriptor"]["encoding_fingerprint"]
    assert artifacts["inheritance_manifest"]["schema_version"] == "2.0.0"
    assert {entry["language"] for entry in artifacts["artifacts"]} == {
        "python",
        "systemverilog",
    }
    assert all(len(entry["sha256"]) == 64 for entry in artifacts["artifacts"])
    assert "svx_sv/tb_pkg.py" in out.getvalue()

    (python_out / "checks.py").write_text("class BaseMonitor:\n    pass\n")
    runtime._load_artifact_manifest(
        artifacts_out,
        runtime.SvTypesCapabilities(
            package_major_version=1,
            schema_format_version=1,
            binary_format_version=1,
            object_envelope_version=1,
            generator_runtime_abi_version=1,
            provided=frozenset(
                {
                    "svtypes.checked-encoding-descriptor.v1",
                    "svtypes.codec-context.v1",
                    "svtypes.record-schema.v1",
                    "svtypes.remote-reference.v1",
                }
            ),
        ),
    )

    assert main(
        [
            "inheritance-gen",
            "--manifest",
            str(manifest_path),
            "--python-out",
            str(python_out),
            "--sv-out",
            str(sv_out),
            "--artifact-manifest",
            str(artifacts_out),
            "--check",
        ],
        out=StringIO(),
    ) == 0

    sv_out.write_text(sv_out.read_text() + "// stale\n")
    with pytest.raises(SystemExit, match="artifacts are stale"):
        main(
            [
                "inheritance-gen",
                "--manifest",
                str(manifest_path),
                "--python-out",
                str(python_out),
                "--sv-out",
                str(sv_out),
                "--artifact-manifest",
                str(artifacts_out),
                "--check",
            ],
            out=StringIO(),
        )


def test_remote_error_preserves_dispatch_identity(monkeypatch):
    from svx.inheritance import call_sv

    def fail(*_args):
        raise RuntimeError("SVX1|unknown_object|41|sv://pkg/Base#run|unknown object")

    monkeypatch.setattr("svx._native.inheritance_call_sv", fail)
    with pytest.raises(SVXRemoteError) as raised:
        call_sv(41, "sv://pkg/Base#run")
    assert raised.value.object_id == 41
    assert raised.value.method_id == "sv://pkg/Base#run"
    assert raised.value.remote_message == "unknown object"
    assert raised.value.code == "unknown_object"


def test_custom_svtypes_object_null_uses_generated_record():
    from tests.fixtures.object_types import Packet

    packet = type_ref(
        Packet,
        module="tests.fixtures.object_types",
        symbol="Packet",
        sv="Packet",
        sv_packer="svtypes_pkg::object_packer#(Packet)",
    )
    class_id = "sv://codec/NullablePacketConstructor"
    register_constructor(class_id, (("packet", packet),))
    payload = encode_constructor(class_id, {"packet": None})
    assert payload.startswith(b"\x01")


def test_manifest_migration_upgrades_legacy_scalar_types():
    data = manifest_data()
    parameter = data["classes"][0]["methods"][0]["parameters"][0]
    parameter["type"] = "bit"
    migrated = migrate_manifest(data)
    migrated_parameter = migrated["classes"][0]["methods"][0]["parameters"][0]
    assert migrated_parameter["type"]["python"] == {
        "module": "svtypes",
        "symbol": "Bit",
        "args": [1],
        "kwargs": {},
    }
    assert migrated["schema_version"] == "2.0.0"


def test_remote_ref_is_resolved_and_type_checked_by_svx(monkeypatch):
    from svtypes import RemoteRef, RemoteRefValue

    reference = type_ref(
        RemoteRef,
        args=("sv://tb_pkg/BaseDriver",),
        sv="svtypes_pkg::remote_ref_value",
        sv_packer="svtypes_pkg::remote_ref_packer",
    )

    class Driver:
        __svx_foreign_class_ids__ = ("sv://tb_pkg/BaseDriver",)

    monkeypatch.setattr(
        "svx._native.inheritance_get",
        lambda object_id: Driver() if object_id == 17 else None,
    )
    class_id = "sv://codec/RemoteRefConstructor"
    register_constructor(class_id, (("reference", reference),))
    payload = encode_constructor(
        class_id,
        {"reference": RemoteRefValue("sv://tb_pkg/BaseDriver", 17)},
    )
    assert payload.startswith(b"\x01")

    with pytest.raises(SVXInheritanceError, match="unknown or stale"):
        encode_constructor(
            class_id,
            {"reference": RemoteRefValue("sv://tb_pkg/BaseDriver", 18)},
        )


def test_nested_remote_ref_is_resolved_from_public_schema(monkeypatch):
    from svtypes import RemoteRef, RemoteRefValue, SvObject

    class RefEnvelope(SvObject):
        reference = RemoteRef("sv://tb_pkg/BaseDriver")

    monkeypatch.setattr(sys.modules[__name__], "RefEnvelope", RefEnvelope, raising=False)

    envelope_type = type_ref(
        RefEnvelope,
        module=__name__,
        symbol="RefEnvelope",
        sv="RefEnvelope",
        sv_packer="svtypes_pkg::object_packer#(RefEnvelope)",
    )

    class Driver:
        __svx_foreign_class_ids__ = ("sv://tb_pkg/BaseDriver",)

    monkeypatch.setattr(
        "svx._native.inheritance_get",
        lambda object_id: Driver() if object_id == 27 else None,
    )
    class_id = "sv://codec/NestedRemoteRefConstructor"
    register_constructor(class_id, (("envelope", envelope_type),))
    envelope = RefEnvelope(session=runtime.codec_session())
    envelope.reference.value = RemoteRefValue("sv://tb_pkg/BaseDriver", 27)
    assert encode_constructor(class_id, {"envelope": envelope}).startswith(b"\x01")

    envelope.reference.value = RemoteRefValue("sv://tb_pkg/BaseDriver", 28)
    with pytest.raises(SVXInheritanceError, match="unknown or stale"):
        encode_constructor(class_id, {"envelope": envelope})


class _FakeRecordSchema:
    def __init__(self, *, unified_type_name, fields):
        self.unified_type_name = unified_type_name
        self.fields = fields
        self.value_type = make_dataclass(
            unified_type_name.rsplit(".", 1)[-1].title() + "Value",
            [(name, object) for name, _ in fields],
            frozen=True,
        )

    def pack(self, value, _context=None):
        return b"".join(codec.pack(getattr(value, name)) for name, codec in self.fields)

    def unpack(self, payload, _context=None):
        values = {}
        offset = 0
        for name, codec in self.fields:
            value, consumed = codec.unpack(payload[offset:])
            values[name] = value
            offset += consumed
        return self.value_type(**values), offset


def test_generated_call_records_cover_result_and_copyout(monkeypatch):
    monkeypatch.setattr(svtypes, "RecordSchema", _FakeRecordSchema, raising=False)
    result_method = "sv://codec/Target#add_one"
    copyout_method = "sv://codec/Target#exchange"
    register_contract(
        {
            result_method: {
                "request": (("value", INT),),
                "response": (("result", INT),),
            },
            copyout_method: {
                "request": (("changed", INT),),
                "response": (("changed", INT), ("observed", INT)),
            },
        }
    )

    def remote_call(_object_id, method_id, payload):
        if method_id == result_method:
            value = int.from_bytes(payload, "little")
            return (value + 1).to_bytes(4, "little")
        assert payload == (7).to_bytes(4, "little")
        return (8).to_bytes(4, "little") + (19).to_bytes(4, "little")

    monkeypatch.setattr("svx._native.inheritance_call_sv", remote_call)
    assert invoke_sv(4, result_method, {"value": 9}) == 10
    copyout = invoke_sv(4, copyout_method, {"changed": 7})
    assert isinstance(copyout, response_type(copyout_method))
    assert (copyout.changed, copyout.observed) == (8, 19)


def test_python_callback_requires_generated_copyout_response(monkeypatch):
    monkeypatch.setattr(svtypes, "RecordSchema", _FakeRecordSchema, raising=False)
    method_id = "sv://codec/Target#exchange_callback"
    register_contract(
        {
            method_id: {
                "request": (("changed", INT),),
                "response": (("changed", INT), ("observed", INT)),
            }
        }
    )
    result_type = response_type(method_id)

    class Target:
        def exchange_callback(self, changed):
            return result_type(changed=changed + 1, observed=23)

    monkeypatch.setattr("svx._native.inheritance_get", lambda _object_id: Target())
    payload = (4).to_bytes(4, "little")
    assert dispatch_python_call(2, method_id, payload) == (
        (5).to_bytes(4, "little") + (23).to_bytes(4, "little")
    )


def test_real_svtypes_record_schema_round_trip(monkeypatch):
    method_id = "sv://codec/Target#real_record_add"
    register_contract(
        {
            method_id: {
                "request": (("value", INT),),
                "response": (("result", INT),),
            }
        }
    )

    class Target:
        def real_record_add(self, value):
            return value + 3

    monkeypatch.setattr("svx._native.inheritance_get", lambda _object_id: Target())
    monkeypatch.setattr(
        "svx._native.inheritance_call_sv",
        lambda object_id, incoming_method_id, payload: dispatch_python_call(
            object_id, incoming_method_id, payload
        ),
    )
    assert invoke_sv(7, method_id, {"value": 11}) == 14


def test_real_svtypes_copyout_record_round_trip(monkeypatch):
    method_id = "sv://codec/Target#real_record_exchange"
    register_contract(
        {
            method_id: {
                "request": (("changed", INT),),
                "response": (("changed", INT), ("observed", INT)),
            }
        }
    )
    generated_response = response_type(method_id)

    class Target:
        def real_record_exchange(self, changed):
            result = generated_response(session=runtime.codec_session())
            result.changed.value = changed + 1
            result.observed.value = 31
            return result

    monkeypatch.setattr("svx._native.inheritance_get", lambda _object_id: Target())
    monkeypatch.setattr(
        "svx._native.inheritance_call_sv",
        lambda object_id, incoming_method_id, payload: dispatch_python_call(
            object_id, incoming_method_id, payload
        ),
    )
    response = invoke_sv(9, method_id, {"changed": 4})
    assert response.changed.value == 5
    assert response.observed.value == 31
    assert runtime.codec_session().get(response.svtypes_object_number) is None


def test_real_svtypes_constructor_record_round_trip():
    class_id = "sv://codec/Constructed"
    register_constructor(class_id, (("seed", INT), ("name", STRING)))
    observed = []

    class Constructed:
        @classmethod
        def __svx_create_from_sv__(cls, object_id, seed, name):
            observed.append((object_id, seed, name))

    register_python_subclass(class_id, Constructed)
    payload = encode_constructor(class_id, {"seed": 13, "name": "counter"})
    create_python_instance(class_id, 22, payload)
    assert observed == [(22, 13, "counter")]
