import json
from io import StringIO

import pytest

from svx import SVXInheritanceError
from svx import SVXRemoteError
from svx.cli import main
from svx.inheritance import (
    SCHEMA_URI,
    SCHEMA_VERSION,
    decode_result,
    dispatch_python_call,
    emit_python_mirrors,
    emit_sv_mirrors,
    encode_arguments,
    migrate_manifest,
    parse_manifest,
    register_contract,
)


INT = {"svtypes": "svtypes.Int()", "sv": "int", "sv_packer": "int_packer"}


def manifest_data() -> dict:
    return {
        "schema_uri": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
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
    assert "encode_arguments((address,), ('svtypes.Int()',))" in mirror_text

    sv_text = emit_sv_mirrors(manifest)
    assert "package svx_py_checks_pkg;" in sv_text
    assert "virtual class BaseMonitor implements svx_dispatchable;" in sv_text
    assert "virtual task sample();" in sv_text
    assert "class BaseDriver_python_proxy extends BaseDriver implements svx_dispatchable;" in sv_text


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
    invalid["classes"][0]["methods"][0]["parameters"][0]["direction"] = "output"
    with pytest.raises(SVXInheritanceError, match="only 'input' is supported in M8"):
        parse_manifest(invalid)

    invalid = manifest_data()
    invalid["classes"][0]["methods"][0]["return_type"] = INT
    with pytest.raises(SVXInheritanceError, match="task methods must have return_type 'void'"):
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


def test_inheritance_gen_cli_writes_mirrors(tmp_path):
    manifest_path = tmp_path / "inheritance.json"
    manifest_path.write_text(json.dumps(manifest_data()))
    python_out = tmp_path / "python"
    sv_out = tmp_path / "mirrors.sv"
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
        ],
        out=out,
    ) == 0

    assert (python_out / "svx_sv" / "tb_pkg.py").is_file()
    assert "BaseDriver" in (python_out / "svx_sv" / "tb_pkg.py").read_text()
    assert "package svx_py_checks_pkg;" in sv_out.read_text()
    assert "svx_sv/tb_pkg.py" in out.getvalue()


def test_svtypes_codec_transport_without_an_svx_scalar_envelope(monkeypatch):
    class Target:
        def echo(self, count, label):
            return f"{label}:{count}"

    register_contract(
        {
            "sv://codec/Target#echo": (
                ("svtypes.Int()", "svtypes.String()"),
                "svtypes.String()",
            )
        }
    )
    monkeypatch.setattr("svx._native.inheritance_get", lambda object_id: Target())
    payload = encode_arguments((37, "address"), ("svtypes.Int()", "svtypes.String()"))
    assert payload == (37).to_bytes(4, "little", signed=False) + b"\x07\x00\x00\x00address"
    response = dispatch_python_call(8, "sv://codec/Target#echo", payload)
    assert decode_result(response, "svtypes.String()") == "address:37"


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


def test_custom_svtypes_object_null_uses_svtypes_marker():
    expression = "tests.fixtures.object_types:Packet()"
    payload = encode_arguments((None,), (expression,))
    assert payload == b"\x00"
    assert decode_result(payload, expression) is None


def test_manifest_migration_upgrades_legacy_scalar_types():
    data = manifest_data()
    data["classes"][0]["methods"][0]["parameters"][0]["type"] = "int"
    migrated = migrate_manifest(data)
    assert migrated["classes"][0]["methods"][0]["parameters"][0]["type"] == INT
