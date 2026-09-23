import json
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest
from svtypes import Int

from svx import (
    SVMirror,
    SVXInheritanceError,
    inheritance_class,
    inheritance_method,
    inheritance_parameter,
    inheritance_type,
    manifest_from_declarations,
    sv_mirror,
)
from svx.declarations import (
    SV_DECLARATION_SCHEMA_URI,
    SV_DECLARATION_SCHEMA_VERSION,
    manifest_dict,
)
from svx.cli import main
from svx.inheritance import parse_manifest
from svx.sv_scan import scan_sv_sources


def int_type():
    return inheritance_type(Int, sv="int", sv_packer="int_packer")


def test_python_decorators_and_sv_sidecar_normalize_to_v2_manifest(tmp_path):
    module = ModuleType("checks.frontend")

    @inheritance_method(
        parameters=(
            inheritance_parameter("changed", int_type(), direction="inout"),
            inheritance_parameter("observed", int_type(), direction="output"),
        ),
        timing="task",
    )
    def exchange(self, changed):
        return changed

    exchange.__module__ = module.__name__
    Driver = type("Driver", (), {"__module__": module.__name__, "exchange": exchange})
    Driver = inheritance_class(canonical_id="py://checks/Driver")(Driver)
    module.Driver = Driver

    sv_file = tmp_path / "sv-declarations.json"
    sv_file.write_text(
        json.dumps(
            {
                "schema_uri": SV_DECLARATION_SCHEMA_URI,
                "schema_version": SV_DECLARATION_SCHEMA_VERSION,
                "classes": [
                    {
                        "canonical_id": "sv://tb_pkg/Monitor",
                        "language": "sv",
                        "symbol": "tb_pkg::Monitor",
                        "methods": [],
                    }
                ],
            }
        )
    )

    manifest = manifest_from_declarations(
        python_modules=(module,), sv_declaration_files=(sv_file,)
    )
    assert [cls.canonical_id for cls in manifest.classes] == [
        "py://checks/Driver",
        "sv://tb_pkg/Monitor",
    ]
    method = manifest.classes[0].methods[0]
    assert [parameter.direction for parameter in method.parameters] == [
        "inout",
        "output",
    ]
    parse_manifest(manifest_dict(manifest))


def test_sv_mirror_declaration_contributes_complete_sv_base_lineage(tmp_path):
    module = ModuleType("checks.mirror")
    AMirror = type("AMirror", (SVMirror,), {"__module__": module.__name__})
    AMirror = sv_mirror("sv://tb_pkg/BaseDriver")(AMirror)
    module.AMirror = AMirror

    Child = type("Child", (AMirror,), {"__module__": module.__name__})
    Child = inheritance_class(canonical_id="py://checks/Child")(Child)
    module.Child = Child

    sv_file = tmp_path / "sv-declarations.json"
    sv_file.write_text(
        json.dumps(
            {
                "schema_uri": SV_DECLARATION_SCHEMA_URI,
                "schema_version": SV_DECLARATION_SCHEMA_VERSION,
                "classes": [
                    {
                        "canonical_id": "sv://tb_pkg/BaseDriver",
                        "language": "sv",
                        "symbol": "tb_pkg::BaseDriver",
                        "methods": [],
                    }
                ],
            }
        )
    )

    manifest = manifest_from_declarations(
        python_modules=(module,), sv_declaration_files=(sv_file,)
    )
    child = next(item for item in manifest.classes if item.canonical_id == "py://checks/Child")
    assert [item.canonical_id for item in child.base_lineage] == ["sv://tb_pkg/BaseDriver"]


def test_python_decorator_rejects_output_as_a_python_call_argument():
    @inheritance_method(
        parameters=(inheritance_parameter("result", int_type(), direction="output"),),
        timing="task",
    )
    def sample(self, result):
        return None

    sample.__module__ = "checks.invalid"
    Invalid = type("Invalid", (), {"__module__": "checks.invalid", "sample": sample})
    with pytest.raises(SVXInheritanceError, match="signature must be"):
        inheritance_class()(Invalid)


def test_manifest_accepts_expanded_lineage_without_generating_its_members():
    base = {
        "canonical_id": "sv://tb_pkg/BaseDriver",
        "language": "sv",
        "symbol": "tb_pkg::BaseDriver",
        "methods": [],
    }
    middle = {
        "canonical_id": "py://checks/PythonDriver",
        "language": "python",
        "symbol": "checks.PythonDriver",
        "methods": [],
    }
    target = {
        "canonical_id": "sv://tb_pkg/FinalDriver",
        "language": "sv",
        "symbol": "tb_pkg::FinalDriver",
        "methods": [],
        "base_lineage": [base, middle],
    }
    manifest = parse_manifest(
        {
            "schema_uri": "https://svx.dev/schema/inheritance-manifest/v2",
            "schema_version": "2.0.0",
            "generator_abi_version": 2,
            "required_runtime_capabilities": [
                "svtypes.checked-encoding-descriptor.v1",
                "svtypes.codec-context.v1",
                "svtypes.record-schema.v1",
                "svtypes.remote-reference.v1",
            ],
            "classes": [target],
        }
    )
    assert [item.canonical_id for item in manifest.classes[0].base_lineage] == [
        base["canonical_id"],
        middle["canonical_id"],
    ]
    assert [item.canonical_id for item in manifest.classes] == [target["canonical_id"]]
    assert manifest_dict(manifest)["classes"][0]["base_lineage"] == [base, middle]


def test_sv_sidecar_rejects_python_owned_class(tmp_path):
    path = Path(tmp_path) / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "schema_uri": SV_DECLARATION_SCHEMA_URI,
                "schema_version": SV_DECLARATION_SCHEMA_VERSION,
                "classes": [{"language": "python"}],
            }
        )
    )
    with pytest.raises(SVXInheritanceError, match="only SV-owned"):
        manifest_from_declarations(sv_declaration_files=(path,))


def test_pyslang_scans_and_validates_sv_inheritance_declarations(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "drivers.sv"
    source.write_text(
        "package tb_pkg;\n"
        "  virtual class BaseDriver;\n"
        "    virtual task drive(input int value); endtask\n"
        "  endclass\n"
        "  class FinalDriver extends BaseDriver; endclass\n"
        "endpackage\n"
    )
    facts = scan_sv_sources([source])
    assert facts["tb_pkg::FinalDriver"].direct_base == "BaseDriver"
    assert facts["tb_pkg::BaseDriver"].virtual_methods == {"drive"}

    sidecar = tmp_path / "sv-declarations.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_uri": SV_DECLARATION_SCHEMA_URI,
                "schema_version": SV_DECLARATION_SCHEMA_VERSION,
                "classes": [
                    {
                        "canonical_id": "sv://tb_pkg/BaseDriver",
                        "language": "sv",
                        "symbol": "tb_pkg::BaseDriver",
                        "methods": [
                            {
                                "canonical_id": "sv://tb_pkg/BaseDriver#drive",
                                "name": "drive",
                                "parameters": [],
                                "return_type": "void",
                                "timing": "task",
                                "virtual": True,
                                "pure_virtual": False,
                            }
                        ],
                    },
                    {
                        "canonical_id": "sv://tb_pkg/FinalDriver",
                        "language": "sv",
                        "symbol": "tb_pkg::FinalDriver",
                        "methods": [],
                        "base_lineage": [
                            {
                                "canonical_id": "sv://tb_pkg/BaseDriver",
                                "language": "sv",
                                "symbol": "tb_pkg::BaseDriver",
                                "methods": [
                                    {
                                        "canonical_id": "sv://tb_pkg/BaseDriver#drive",
                                        "name": "drive",
                                        "parameters": [],
                                        "return_type": "void",
                                        "timing": "task",
                                        "virtual": True,
                                        "pure_virtual": False,
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        )
    )
    manifest = manifest_from_declarations(
        sv_declaration_files=[sidecar], sv_source_files=[source]
    )
    assert [cls.name for cls in manifest.classes] == ["BaseDriver", "FinalDriver"]


def test_inheritance_manifest_cli_generates_and_checks(tmp_path, monkeypatch):
    module_path = tmp_path / "declared.py"
    module_path.write_text(
        "from svtypes import Int\n"
        "from svx import inheritance_class, inheritance_method, "
        "inheritance_parameter, inheritance_type\n"
        "INT = inheritance_type(Int, sv='int', sv_packer='int_packer')\n"
        "@inheritance_class(canonical_id='py://declared/Driver')\n"
        "class Driver:\n"
        "    @inheritance_method(parameters=(inheritance_parameter('value', INT),), "
        "return_type=INT, timing='function')\n"
        "    def run(self, value):\n"
        "        return value\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    target = tmp_path / "inheritance.json"
    arguments = [
        "inheritance-manifest",
        "--python-module",
        "declared",
        "--out",
        str(target),
    ]
    assert main(arguments, out=StringIO()) == 0
    assert parse_manifest(json.loads(target.read_text())).classes[0].name == "Driver"
    assert main([*arguments, "--check"], out=StringIO()) == 0
