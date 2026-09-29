import json
from io import StringIO
from pathlib import Path
import sys
from types import ModuleType

import pytest
from svtypes import Bit, Int, Object, Queue, RemoteRef, type_spec_identity

from svx import (
    Function,
    Inout,
    Input,
    Output,
    SVMirror,
    SVXInheritanceError,
    Task,
    inheritance_class,
    inheritance_method,
    inheritance_parameter,
    manifest_from_declarations,
    sv_class_handle,
    sv_mirror,
    virtual_interface_handle,
)
from svx.declarations import (
    SV_DECLARATION_SCHEMA_URI,
    SV_DECLARATION_SCHEMA_VERSION,
    manifest_dict,
)
from svx.cli import main
from svx.inheritance import parse_manifest
from svx.sv_scan import (
    scan_sv_sources,
    scan_sv_virtual_interfaces,
    validate_sv_declarations,
)


def int_type():
    return Int


def test_return_markers_select_inheritance_method_timing():
    module = ModuleType("checks.return_markers")

    @inheritance_method(return_type=int_type())
    def calculate(self) -> Function:
        return 3

    @inheritance_method()
    def drive(self) -> Task:
        return None

    calculate.__module__ = module.__name__
    drive.__module__ = module.__name__
    Driver = type(
        "Driver",
        (),
        {"__module__": module.__name__, "calculate": calculate, "drive": drive},
    )
    Driver = inheritance_class(canonical_id="py://checks/Driver")(Driver)
    module.Driver = Driver

    manifest = manifest_from_declarations(python_modules=(module,))
    timings = {method.name: method.timing for method in manifest.classes[0].methods}
    assert timings == {"calculate": "function", "drive": "task"}


def test_annotated_prototype_derives_parameters_return_and_timing():
    module = ModuleType("checks.compact_prototype")

    @inheritance_method
    def calculate(
        self,
        source: Bit[8],
        changed: Inout[Bit[8]],
        observed: Output[Queue[Bit[8]]],
    ) -> Function[Int]:
        changed.value = source
        observed.value = []
        return source

    calculate.__module__ = module.__name__
    Driver = type(
        "Driver",
        (),
        {"__module__": module.__name__, "calculate": calculate},
    )
    Driver = inheritance_class(canonical_id="py://checks/CompactDriver")(Driver)
    module.Driver = Driver

    manifest = manifest_from_declarations(python_modules=(module,))
    method = manifest.classes[0].methods[0]
    assert method.timing == "function"
    assert method.return_type is not None
    assert [parameter.name for parameter in method.parameters] == [
        "source",
        "changed",
        "observed",
    ]
    assert [parameter.direction for parameter in method.parameters] == [
        "input",
        "inout",
        "output",
    ]
    serialized = manifest_dict(manifest)
    parameter_types = serialized["classes"][0]["methods"][0]["parameters"]
    assert [item["type"]["svtypes"] for item in parameter_types] == [
        type_spec_identity(Bit[8]),
        type_spec_identity(Bit[8]),
        type_spec_identity(Queue[Bit[8]]),
    ]
    assert all("python" not in item["type"] for item in parameter_types)


def test_annotated_output_is_a_regular_python_parameter():
    @inheritance_method
    def calculate(self, observed: Output[Int]) -> Task:
        observed.value = 1
        return None

    Valid = type("Valid", (), {"calculate": calculate})
    inheritance_class()(Valid)


def test_explicit_input_marker_is_equivalent_to_an_unwrapped_binding():
    INT = int_type()

    @inheritance_method
    def drive(self, value: Input[INT]) -> Task:
        return None

    parameter = drive.__svx_inheritance_method__["parameters"][0]
    assert parameter["direction"] == "input"
    assert parameter["type"]["svtypes"] == {"kind": "scalar", "name": "Int"}


def test_return_marker_rejects_conflicting_or_unknown_timing():
    with pytest.raises(SVXInheritanceError, match="conflicts"):
        @inheritance_method(timing="task")
        def calculate(self) -> Function:
            return None

    with pytest.raises(SVXInheritanceError, match="svx.Task, svx.Function"):
        @inheritance_method()
        def invalid(self) -> int:
            return 3


def test_python_decorators_and_sv_sidecar_normalize_to_v2_manifest(tmp_path):
    module = ModuleType("checks.frontend")

    @inheritance_method(
        parameters=(
            inheritance_parameter("changed", int_type(), direction="inout"),
            inheritance_parameter("observed", int_type(), direction="output"),
        ),
        timing="task",
    )
    def exchange(self, changed, observed):
        changed.value += 1
        observed.value = changed.value
        return None

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


def test_python_decorator_requires_output_in_its_python_call_signature():
    @inheritance_method(
        parameters=(inheritance_parameter("result", int_type(), direction="output"),),
        timing="task",
    )
    def sample(self):
        return None

    sample.__module__ = "checks.invalid"
    Invalid = type("Invalid", (), {"__module__": "checks.invalid", "sample": sample})
    with pytest.raises(SVXInheritanceError, match="signature must be"):
        inheritance_class()(Invalid)


@pytest.mark.parametrize("direction", ["ref", "const ref"])
def test_python_declaration_rejects_ref_parameter(direction):
    with pytest.raises(ValueError, match="does not support ref"):
        inheritance_parameter("value", int_type(), direction=direction)


def test_inheritance_declaration_discovers_direct_svtypes_fields(monkeypatch):
    module = ModuleType("checks.projected_fields")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    Driver = type(
        "Driver",
        (),
        {
            "__module__": module.__name__,
            "count": Int(),
            "history": Queue[Int](),
            "child": Object["Child"](),
        },
    )
    Driver = inheritance_class(canonical_id="py://checks/ProjectedDriver")(Driver)
    module.Driver = Driver

    manifest = manifest_from_declarations(python_modules=(module,))
    fields = {field.name: field.type_binding for field in manifest.classes[0].fields}
    assert fields["count"].unified_type_name == "svtypes.Int"
    assert fields["count"].sv == "int"
    assert fields["count"].sv_packer == "svtypes_pkg::int_packer"
    assert fields["history"].unified_type_name == "svtypes.Queue[elem=svtypes.Int]"
    assert fields["history"].sv == "int [$]"
    assert fields["child"].sv == "Child"


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
        "    static function int static_value(); return 1; endfunction\n"
        "  endclass\n"
        "  class FinalDriver extends BaseDriver; endclass\n"
        "endpackage\n"
    )
    facts = scan_sv_sources([source])
    assert facts["tb_pkg::FinalDriver"].direct_base == "BaseDriver"
    assert facts["tb_pkg::BaseDriver"].virtual_methods == {"drive"}
    assert facts["tb_pkg::BaseDriver"].static_methods == {"static_value"}

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

    with pytest.raises(SVXInheritanceError, match="static in the manifest"):
        validate_sv_declarations(
            [
                {
                    "canonical_id": "sv://tb_pkg/BaseDriver",
                    "language": "sv",
                    "symbol": "tb_pkg::BaseDriver",
                    "methods": [
                        {"name": "drive", "virtual": False, "static": True}
                    ],
                }
            ],
            [source],
        )


def test_pyslang_scans_virtual_interface_modports(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "bus_if.sv"
    source.write_text(
        "interface bus_if;\n"
        "  logic valid;\n"
        "  task write(input logic value); valid = value; endtask\n"
        "  modport master(output valid, import write);\n"
        "  modport monitor(input valid);\n"
        "endinterface\n"
    )

    facts = scan_sv_virtual_interfaces([source])
    assert facts["bus_if"].modports == {"master", "monitor"}
    master = facts["bus_if"].visible_members("master")
    assert [(member.name, member.kind) for member in master] == [
        ("valid", "signal"),
        ("write", "task"),
    ]
    write = next(member for member in master if member.name == "write")
    assert write.parameters[0].sv_type == "logic"
    assert write.parameters[0].direction == "input"
    directions = dict(
        (item.name, item.direction)
        for name, items in facts["bus_if"].modport_members
        if name == "master"
        for item in items
    )
    assert directions == {"valid": "output", "write": "import"}


def test_declaration_handles_generate_vif_operations(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "bus_if.sv"
    source.write_text(
        "interface bus_if;\n"
        "  logic [7:0] data;\n"
        "  task write(input logic [7:0] value); data = value; endtask\n"
        "  function logic [7:0] read(); return data; endfunction\n"
        "  modport master(output data, import write, read);\n"
        "endinterface\n"
    )
    module = ModuleType("checks.handle_portal")
    packet_ref = RemoteRef["sv://packet_pkg/Packet"]
    vif_ref = RemoteRef["sv-vif://bus_if/master"]

    def round_trip(self, packet, vif):
        return vif

    round_trip.__module__ = module.__name__
    round_trip = inheritance_method(
        parameters=[
            inheritance_parameter(
                "packet",
                packet_ref,
                handle=sv_class_handle("sv://packet_pkg/Packet", "packet_pkg::Packet"),
            ),
            inheritance_parameter(
                "vif",
                vif_ref,
                handle=virtual_interface_handle(
                    "sv-vif://bus_if/master", "virtual bus_if.master"
                ),
            ),
        ],
        return_type=vif_ref,
        return_handle=virtual_interface_handle(
            "sv-vif://bus_if/master", "virtual bus_if.master"
        ),
        timing="function",
    )(round_trip)
    portal = type(
        "HandlePortal",
        (),
        {"__module__": module.__name__, "round_trip": round_trip},
    )
    portal = inheritance_class(canonical_id="py://checks/HandlePortal")(portal)
    setattr(module, "HandlePortal", portal)

    manifest = manifest_from_declarations(
        python_modules=[module], sv_source_files=[source]
    )
    method = manifest.classes[0].methods[0]
    assert method.parameters[0].handle is not None
    assert method.parameters[0].handle.kind == "sv_class"
    assert method.parameters[1].handle is not None
    assert sorted(operation.method.name for operation in method.parameters[1].handle.operations) == [
        "read",
        "write",
        "write_data",
    ]
    assert method.return_handle is not None
    assert sorted(operation.method.name for operation in method.return_handle.operations) == [
        "read",
        "write",
        "write_data",
    ]


def test_inheritance_manifest_cli_generates_and_checks(tmp_path, monkeypatch):
    module_path = tmp_path / "declared.py"
    module_path.write_text(
        "from svtypes import Int\n"
        "from svx import Function, inheritance_class, inheritance_method\n"
        "@inheritance_class(canonical_id='py://declared/Driver')\n"
        "class Driver:\n"
        "    @inheritance_method\n"
        "    def run(self, value: Int) -> Function[Int]:\n"
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
