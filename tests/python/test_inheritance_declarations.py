import json
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest
from svtypes import Int

from svx import (
    SVXInheritanceError,
    inheritance_class,
    inheritance_method,
    inheritance_parameter,
    inheritance_type,
    manifest_from_declarations,
)
from svx.declarations import (
    SV_DECLARATION_SCHEMA_URI,
    SV_DECLARATION_SCHEMA_VERSION,
    manifest_dict,
)
from svx.cli import main
from svx.inheritance import parse_manifest


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
