import inspect
import json
from io import StringIO
from pathlib import Path
import sys
from types import ModuleType

import pytest
from svtypes import Array, AssocArray, Bit, DynArray, Int, Logic, LongInt, Object, Queue, RealTime, RemoteRef, ShortReal, Signed, String, Unsigned, type_spec_identity

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
from svx.inheritance import emit_python_mirrors, emit_sv_mirrors, load_manifest, parse_manifest
from svx.sv_scan import (
    scan_sv_sources,
    scan_sv_virtual_interfaces,
    validate_sv_declarations,
)


def int_type():
    return Int


def test_constructor_annotations_discover_svtypes_parameters_without_mutation():
    module = ModuleType("checks.constructor_annotations")

    def initialize(self, seed: Int, mask: Input[Bit[8]] = 3):
        self.seed = seed
        self.mask = mask

    original_signature = inspect.signature(initialize)
    Driver = type("Driver", (), {"__module__": module.__name__, "__init__": initialize})
    module.Driver = inheritance_class()(Driver)
    manifest = manifest_dict(manifest_from_declarations(python_modules=(module,)))
    parameters = manifest["classes"][0]["constructor"]["parameters"]
    assert [parameter["name"] for parameter in parameters] == ["seed", "mask"]
    assert [parameter["direction"] for parameter in parameters] == ["input", "input"]
    assert [parameter["type"]["svtypes"] for parameter in parameters] == [
        type_spec_identity(Int), type_spec_identity(Bit[8]),
    ]
    assert Driver.__init__ is initialize
    assert inspect.signature(Driver.__init__) == original_signature


def test_constructor_discovery_does_not_copy_inherited_initializer():
    class Parent:
        def __init__(self, seed: Int):
            self.seed = seed

    Child = inheritance_class()(type("Child", (Parent,), {}))
    assert Child.__svx_inheritance_class__["constructor"]["parameters"] == []


def test_constructor_explicit_empty_and_legacy_unannotated_remain_supported():
    def initialize(self, seed: Int):
        pass

    Explicit = inheritance_class(constructor_parameters=())(
        type("Explicit", (), {"__init__": initialize})
    )
    assert Explicit.__svx_inheritance_class__["constructor"]["parameters"] == []

    def legacy(self, seed):
        pass

    Legacy = inheritance_class()(type("Legacy", (), {"__init__": legacy}))
    assert Legacy.__svx_inheritance_class__["constructor"]["parameters"] == []


@pytest.mark.parametrize("annotated_first", [True, False])
def test_constructor_partial_annotations_are_rejected(annotated_first):
    def initialize(self, seed, mask):
        pass

    initialize.__annotations__ = {"seed" if annotated_first else "mask": Int}
    with pytest.raises(SVXInheritanceError, match="annotate every non-self parameter"):
        inheritance_class()(type("Partial", (), {"__init__": initialize}))


@pytest.mark.parametrize("direction", [Output, Inout])
def test_constructor_non_input_annotation_is_rejected(direction):
    def initialize(self, seed):
        pass

    initialize.__annotations__ = {"seed": direction[Int]}
    with pytest.raises(SVXInheritanceError, match="seed must be input"):
        inheritance_class()(type("NonInput", (), {"__init__": initialize}))


def test_constructor_keyword_only_discovery_reports_unsupported_shape():
    def initialize(self, *, seed: Int):
        pass

    with pytest.raises(SVXInheritanceError, match="seed:.*fixed positional"):
        inheritance_class()(type("KeywordOnly", (), {"__init__": initialize}))


def test_sv_source_constructor_facts_are_separate_from_methods(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "constructor_facts.sv"
    source.write_text(
        "package constructor_facts_pkg;\n"
        "class Explicit;\n"
        "  function new(input int seed, count, input string name = \"default\");\n"
        "  endfunction\n"
        "  function int read(); return 0; endfunction\n"
        "endclass\n"
        "class Implicit; endclass\n"
        "endpackage\n"
    )
    facts = scan_sv_sources([source])
    constructor = facts["constructor_facts_pkg::Explicit"].constructor
    assert constructor is not None
    assert constructor.name == "new"
    assert [(parameter.name, parameter.direction, parameter.sv_type)
            for parameter in constructor.parameters] == [
        ("seed", "input", "int"), ("count", "input", "int"),
        ("name", "input", "string"),
    ]
    assert [method.name for method in facts["constructor_facts_pkg::Explicit"].methods] == ["read"]
    assert facts["constructor_facts_pkg::Implicit"].constructor is None


def test_empty_mirror_discovers_sv_ancestors_without_extra_targets(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "source_discovery.sv"
    source.write_text(
        "package source_discovery_pkg;\n"
        "typedef int count_t;\n"
        "class Root;\n"
        "  count_t count; local int secret;\n"
        "  function new(input count_t seed); count = seed; endfunction\n"
        "  virtual function count_t check(input count_t value); return count + value; endfunction\n"
        "endclass\n"
        "class Base extends Root;\n"
        "  function new(input int seed); super.new(seed); endfunction\n"
        "  function int check(input int value); return super.check(value); endfunction\n"
        "endclass\n"
        "endpackage\n"
    )
    Stub = sv_mirror("sv://source_discovery_pkg/Base")(type("Stub", (SVMirror,), {}))
    module = ModuleType("checks.source_discovery")
    Child = type("Child", (Stub,), {"__module__": module.__name__})
    module.Child = inheritance_class()(Child)
    manifest = manifest_from_declarations(python_modules=(module,), sv_source_files=(source,))
    assert [target.name for target in manifest.classes] == ["Child"]
    data = manifest_dict(manifest)["classes"][0]
    lineage = data["base_lineage"]
    assert [base["symbol"] for base in lineage] == [
        "source_discovery_pkg::Root", "source_discovery_pkg::Base",
    ]
    assert [field["name"] for field in lineage[0]["fields"]] == ["count"]
    assert lineage[1]["methods"][0]["virtual"] is True
    assert [parameter["name"] for parameter in lineage[1]["constructor"]["parameters"]] == ["seed"]
    assert "base_lineage" not in lineage[0]
    assert Child.__svx_inheritance_class__["base_lineage"] == []
    generated_python = emit_python_mirrors(manifest)
    assert any("class Base" in text for text in generated_python.values())
    assert "source_discovery_pkg::Base" in emit_sv_mirrors(manifest)


@pytest.mark.parametrize("spelling, annotation", [
    ("byte", Bit[8, Signed]), ("byte unsigned", Bit[8]),
    ("shortint", Bit[16, Signed]), ("shortint unsigned", Bit[16]),
    ("int", Int), ("int unsigned", Bit[32]),
    ("longint", LongInt), ("longint unsigned", Bit[64]),
    ("integer", Logic[32, Signed]), ("integer unsigned", Logic[32]),
    ("time", Logic[64]), ("time signed", Logic[64, Signed]),
    ("bit signed", Bit[1, Signed]), ("logic signed", Logic[1, Signed]),
    ("shortreal", ShortReal), ("realtime", RealTime),
])
def test_source_discovery_preserves_scalar_states_and_signedness(tmp_path, spelling, annotation):
    pytest.importorskip("pyslang")
    source = tmp_path / "scalars.sv"
    source.write_text(
        "package scalar_discovery_pkg; class Base;\n"
        f"{spelling} value;\n"
        f"function new(input {spelling} seed); value = seed; endfunction\n"
        f"virtual function {spelling} echo(input {spelling} argument); return argument; endfunction\n"
        "endclass endpackage\n"
    )
    Stub = sv_mirror("sv://scalar_discovery_pkg/Base")(type("Stub", (SVMirror,), {}))
    module = ModuleType("scalar_discovery_checks")
    module.Child = inheritance_class()(type("Child", (Stub,), {"__module__": module.__name__}))
    data = manifest_dict(manifest_from_declarations(python_modules=(module,), sv_source_files=(source,)))
    base = data["classes"][0]["base_lineage"][0]
    expected = type_spec_identity(annotation)
    for binding in (base["fields"][0]["type"], base["constructor"]["parameters"][0]["type"],
                    base["methods"][0]["parameters"][0]["type"], base["methods"][0]["return_type"]):
        assert binding["svtypes"] == expected
        assert binding["sv"] == spelling
    assert emit_sv_mirrors(parse_manifest(data))


def test_source_discovery_preserves_collection_and_packed_type_shapes(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "collections.sv"
    source.write_text(
        "package source_collections_pkg; class Base;\n"
        "int queues[$][$]; int dynamic_values[]; int fixed_values[2][3];\n"
        "int keyed_values[string]; logic signed [1:0][7:0] flags;\n"
        "endclass endpackage\n"
    )
    Stub = sv_mirror("sv://source_collections_pkg/Base")(type("CollectionStub", (SVMirror,), {}))
    module = ModuleType("checks.source_collections")
    module.Child = inheritance_class()(type("Child", (Stub,), {"__module__": module.__name__}))
    manifest = manifest_from_declarations(python_modules=(module,), sv_source_files=(source,))
    base = manifest_dict(manifest)["classes"][0]["base_lineage"][0]
    assert {field["name"]: field["type"]["svtypes"] for field in base["fields"]} == {
        "queues": type_spec_identity(Queue[Queue[Int]]),
        "dynamic_values": type_spec_identity(DynArray[Int]),
        "fixed_values": type_spec_identity(Array[Array[Int, 3], 2]),
        "keyed_values": type_spec_identity(AssocArray[String, Int]),
        "flags": type_spec_identity(Logic[(2, 8), Signed]),
    }


@pytest.mark.parametrize("declaration,annotation,dimension", [
    ("int values_t[$]", Queue[Int], "[$]"),
    ("int values_t[]", DynArray[Int], "[]"),
    ("int values_t[2]", Array[Int, 2], "[2]"),
    ("int values_t[string]", AssocArray[String, Int], "[string]"),
])
def test_source_discovery_preserves_collection_methods(tmp_path, declaration, annotation, dimension):
    pytest.importorskip("pyslang")
    source = tmp_path / "collection_methods.sv"
    source.write_text("package source_formals_pkg; typedef " + declaration + "; class Base; "
                      "function values_t inspect(input values_t values); return values; endfunction"
                      " endclass endpackage\n")
    Stub = sv_mirror("sv://source_formals_pkg/Base")(type("FormalStub", (SVMirror,), {}))
    module = ModuleType("checks.source_formals")
    module.Child = inheritance_class()(type("Child", (Stub,), {"__module__": module.__name__}))
    manifest = manifest_from_declarations(python_modules=(module,), sv_source_files=(source,))
    method = manifest.classes[0].base_lineage[0].methods[0]
    for binding in (method.parameters[0].type_binding, method.return_type):
        assert binding is not None
        assert json.loads(binding.svtypes_identity_json) == type_spec_identity(annotation)
        assert binding.sv == "source_formals_pkg::values_t"
    emitted = emit_sv_mirrors(manifest)
    expected = dimension + (" = '{default: 32'd0};" if dimension == "[2]" else ";")
    assert expected in emitted
    assert "source_formals_pkg::values_t values;" in emitted
    assert "source_formals_pkg::values_t result;" in emitted


@pytest.mark.parametrize("declaration, annotation", [
    ("byte values_t[$]", Queue[Bit[8, Signed]]),
    ("shortint unsigned values_t[]", DynArray[Bit[16]]),
    ("integer values_t[2]", Array[Logic[32, Signed], 2]),
    ("time values_t[string]", AssocArray[String, Logic[64]]),
])
def test_source_discovery_preserves_native_collection_aliases(tmp_path, declaration, annotation):
    pytest.importorskip("pyslang")
    source = tmp_path / "native_collections.sv"
    source.write_text(
        f"package native_collections_pkg; typedef {declaration}; class Base;\n"
        "values_t field;\n"
        "function new(input values_t seed); field = seed; endfunction\n"
        "virtual function values_t echo(input values_t value); return value; endfunction\n"
        "endclass endpackage\n"
    )
    Stub = sv_mirror("sv://native_collections_pkg/Base")(type("Stub", (SVMirror,), {}))
    module = ModuleType("native_collection_checks")
    module.Child = inheritance_class()(type("Child", (Stub,), {"__module__": module.__name__}))
    data = manifest_dict(manifest_from_declarations(python_modules=(module,), sv_source_files=(source,)))
    base = data["classes"][0]["base_lineage"][0]
    for binding in (base["fields"][0]["type"], base["constructor"]["parameters"][0]["type"],
                    base["methods"][0]["parameters"][0]["type"], base["methods"][0]["return_type"]):
        assert binding["svtypes"] == type_spec_identity(annotation)
        assert binding["sv"] == "native_collections_pkg::values_t"
    assert "native_collections_pkg::values_t echo" in emit_sv_mirrors(parse_manifest(data))


@pytest.mark.parametrize("changed", [None, "enum", "field", "width", "state", "missing", "ambiguous", "alias"])
def test_source_discovery_reuses_public_value_types_and_rejects_layout_drift(tmp_path, changed):
    pytest.importorskip("pyslang")
    import svtypes
    from tests.integration.source_value_types import Operation, ValuePacket

    enum_run = 4 if changed == "enum" else 3
    tag_name = "other" if changed == "field" else "tag"
    tag_width = 6 if changed == "width" else 7
    flags_type = "bit" if changed == "state" else "logic"
    op_type = "OperationAlias" if changed == "alias" else "Operation"
    source = tmp_path / "values.sv"
    source.write_text(
        f"package value_discovery_pkg; typedef enum int {{ IDLE=0, RUN={enum_run} }} Operation;\n"
        f"typedef struct packed {{ bit [{tag_width}:0] {tag_name}; {flags_type} [3:0] flags; }} ValuePacket_t;\n"
        "typedef Operation OperationAlias;\n"
        f"class Base; {op_type} operation; ValuePacket_t packet;\n"
        f"function new(input {op_type} op, input ValuePacket_t value); operation=op; packet=value; endfunction\n"
        f"virtual function {op_type} echo_op(input {op_type} value); return value; endfunction\n"
        "virtual function ValuePacket_t echo_packet(input ValuePacket_t value); return value; endfunction\n"
        "endclass endpackage\n"
    )
    Stub = sv_mirror("sv://value_discovery_pkg/Base")(type("Stub", (SVMirror,), {}))
    module = ModuleType("value_discovery_checks")
    module.Operation, module.ValuePacket = Operation, ValuePacket
    if changed == "missing":
        del module.Operation
        del module.ValuePacket
    elif changed == "ambiguous":
        module.OtherOperation = type("Operation", (svtypes.Enum,), {"IDLE": 0, "RUN": 3})
    module.Child = inheritance_class()(type("Child", (Stub,), {"__module__": module.__name__}))
    if changed not in {None, "alias"}:
        error = "one matching public SvTypes" if changed in {"missing", "ambiguous"} else "differ"
        with pytest.raises(SVXInheritanceError, match=error):
            manifest_from_declarations(python_modules=(module,), sv_source_files=(source,))
        return
    data = manifest_dict(manifest_from_declarations(python_modules=(module,), sv_source_files=(source,)))
    base = data["classes"][0]["base_lineage"][0]
    for index, annotation in enumerate((Operation, ValuePacket)):
        method = base["methods"][index]
        for binding in (base["fields"][index]["type"], base["constructor"]["parameters"][index]["type"],
                        method["parameters"][0]["type"], method["return_type"]):
            assert binding["svtypes"] == type_spec_identity(annotation)
            assert binding["sv"].startswith("value_discovery_pkg::")
            if index == 0:
                assert binding["sv"] == f"value_discovery_pkg::{op_type}"
    assert len(data["classes"]) == 1
    assert "import value_discovery_pkg::*;" in emit_sv_mirrors(parse_manifest(data))


def test_source_discovery_resolves_default_type_and_value_specialization(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "generic.sv"
    source.write_text(
        "package default_generic_pkg; class Base #(type T=shortint unsigned, int W=8);\n"
        "localparam int UNUSED=2; T item; bit [W-1:0] flags;\n"
        "function new(input T value); item=value; endfunction\n"
        "virtual function T echo(input T value); return value; endfunction\n"
        "endclass endpackage\n"
    )
    Stub = sv_mirror("sv://default_generic_pkg/Base")(type("GenericStub", (SVMirror,), {}))
    module = ModuleType("default_generic_checks")
    module.Child = inheritance_class()(type("Child", (Stub,), {"__module__": module.__name__}))
    data = manifest_dict(manifest_from_declarations(python_modules=(module,), sv_source_files=(source,)))
    base = data["classes"][0]["base_lineage"][0]
    assert len(data["classes"]) == 1
    assert base["specialization"]["arguments"] == [
        {"kind": "type", "type": base["fields"][0]["type"]},
        {"kind": "value", "sv_type": "int", "value": 8}]
    assert base["fields"][1]["type"]["sv"] == "bit [7:0]"
    for actual in (base["constructor"]["parameters"][0]["type"],
                   base["methods"][0]["parameters"][0]["type"], base["methods"][0]["return_type"]):
        assert actual == base["fields"][0]["type"]
    assert "default_generic_pkg::Base#(shortint unsigned, 8)" in emit_sv_mirrors(parse_manifest(data))


def test_source_discovery_resolves_named_nondefault_class_specialization(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "named_generic.sv"
    source.write_text(
        "package named_generic_pkg; class Base #(type T=int, int W=8);\n"
        "T item; bit [W-1:0] flags;\n"
        "function new(input T value); item=value; endfunction\n"
        "virtual function T echo(input T value); return value; endfunction\n"
        "endclass typedef Base#(byte,4) ByteBase; typedef Base#(shortint unsigned,16) ShortBase; endpackage\n"
    )
    module = ModuleType("named_generic_checks")
    for name in ("ByteBase", "ShortBase"):
        Stub = sv_mirror(f"sv://named_generic_pkg/{name}")(type(f"{name}Stub", (SVMirror,), {}))
        setattr(module, name + "Child", inheritance_class()(type(
            name + "Child", (Stub,), {"__module__": module.__name__})))
    data = manifest_dict(manifest_from_declarations(python_modules=(module,), sv_source_files=(source,)))
    assert len(data["classes"]) == 2
    bases = {target["base_lineage"][0]["symbol"]: target["base_lineage"][0] for target in data["classes"]}
    for name, native_type, flags in (("ByteBase", "byte", "bit [3:0]"),
                                     ("ShortBase", "shortint unsigned", "bit [15:0]")):
        base = bases[f"named_generic_pkg::{name}"]
        assert base["canonical_id"] == f"sv://named_generic_pkg/{name}"
        assert "specialization" not in base
        assert base["fields"][0]["type"]["sv"] == native_type
        assert base["fields"][1]["type"]["sv"] == flags
        assert base["methods"][0]["return_type"] == base["fields"][0]["type"]
    emitted = emit_sv_mirrors(parse_manifest(data))
    assert "extends named_generic_pkg::ByteBase " in emitted
    assert "extends named_generic_pkg::ShortBase " in emitted


@pytest.mark.parametrize("named_base", [False, True])
def test_source_discovery_does_not_merge_nondefault_base_with_default(tmp_path, named_base):
    pytest.importorskip("pyslang")
    source = tmp_path / "generic_parent.sv"
    base = "ByteBase" if named_base else "Base#(byte)"
    source.write_text(
        "package generic_parent_pkg; class Base #(type T=int); T item; endclass\n"
        "typedef Base#(byte) ByteBase;\n"
        f"class Child extends {base}; endclass endpackage\n")
    Stub = sv_mirror("sv://generic_parent_pkg/Child")(type("ParentStub", (SVMirror,), {}))
    module = ModuleType("generic_parent_checks")
    module.Derived = inheritance_class()(type("Derived", (Stub,), {"__module__": module.__name__}))
    data = manifest_dict(manifest_from_declarations(python_modules=(module,), sv_source_files=(source,)))
    lineage = data["classes"][0]["base_lineage"]
    assert len(data["classes"]) == 1
    assert [base["symbol"] for base in lineage] == [
        "generic_parent_pkg::ByteBase" if named_base else "generic_parent_pkg::Base",
        "generic_parent_pkg::Child"]
    assert lineage[0]["fields"][0]["type"]["sv"] == "byte"
    if not named_base:
        assert lineage[0]["canonical_id"] == "sv://generic_parent_pkg/Base/specialization/type_byte"
        assert lineage[0]["specialization"]["arguments"][0]["type"]["sv"] == "byte"


@pytest.mark.parametrize("parameter_type", ["int", "integer"])
def test_source_discovery_preserves_default_specialization_state_domain(tmp_path, parameter_type):
    pytest.importorskip("pyslang")
    source = tmp_path / "unknown_generic.sv"
    source.write_text(f"package unknown_generic_pkg; class Base #({parameter_type} W='x); int item; endclass endpackage\n")
    Stub = sv_mirror("sv://unknown_generic_pkg/Base")(type("UnknownStub", (SVMirror,), {}))
    module = ModuleType("unknown_generic_checks")
    module.Child = inheritance_class()(type("Child", (Stub,), {"__module__": module.__name__}))
    if parameter_type == "integer":
        with pytest.raises(SVXInheritanceError, match="parameter W requires explicit closed specialization"):
            manifest_from_declarations(python_modules=(module,), sv_source_files=(source,))
    else:
        data = manifest_dict(manifest_from_declarations(python_modules=(module,), sv_source_files=(source,)))
        assert data["classes"][0]["base_lineage"][0]["specialization"]["arguments"] == [
            {"kind": "value", "sv_type": "int", "value": 0}]


def test_source_discovery_preserves_multiple_unnamed_specialization_chains(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "specialization_chain.sv"
    source.write_text(
        "package specialization_chain_pkg;\n"
        "class Root #(type T=int, int W=8); T item; bit [W-1:0] flags;\n"
        "function new(T value); item=value; endfunction\n"
        "virtual function T echo(T value); return value; endfunction\n"
        "protected static function T static_echo(T value); return value; endfunction endclass\n"
        "class Middle #(type T=int, int W=8) extends Root#(T,W+1);\n"
        "function new(T value); super.new(value); endfunction endclass\n"
        "class ByteChild extends Middle#(byte,4);\n"
        "function new(byte value); super.new(value); endfunction endclass\n"
        "class AnotherByteChild extends Middle#(byte,4);\n"
        "function new(byte value); super.new(value); endfunction endclass\n"
        "class ShortChild extends Middle#(shortint unsigned,16);\n"
        "function new(shortint unsigned value); super.new(value); endfunction endclass\n"
        "endpackage\n")
    module = ModuleType("specialization_chain_checks")
    for name in ("ByteChild", "AnotherByteChild", "ShortChild"):
        Stub = sv_mirror(f"sv://specialization_chain_pkg/{name}")(type(name + "Stub", (SVMirror,), {}))
        setattr(module, name, inheritance_class()(type(
            name, (Stub,), {"__module__": module.__name__})))
    data = manifest_dict(manifest_from_declarations(python_modules=(module,), sv_source_files=(source,)))
    assert len(data["classes"]) == 3
    lineages = {target["symbol"].rsplit(".", 1)[-1]: target["base_lineage"]
                for target in data["classes"]}
    assert lineages["ByteChild"][:2] == lineages["AnotherByteChild"][:2]
    for name, spelling, width in (("ByteChild", "byte", 5), ("ShortChild", "shortint unsigned", 17)):
        root, middle, child = lineages[name]
        assert root["symbol"] == "specialization_chain_pkg::Root"
        assert root["specialization"]["arguments"][1]["value"] == width
        assert middle["specialization"]["arguments"][1]["value"] == width - 1
        assert root["fields"][0]["type"]["sv"] == spelling
        assert root["fields"][1]["type"]["sv"] == f"bit [{width - 1}:0]"
        assert root["constructor"]["parameters"][0]["type"]["sv"] == spelling
        assert root["methods"][0]["return_type"]["sv"] == spelling
    assert lineages["ByteChild"][0]["canonical_id"] != lineages["ShortChild"][0]["canonical_id"]
    assert lineages["ByteChild"][0]["canonical_id"].endswith("/type_byte/value_int_5")
    assert manifest_dict(manifest_from_declarations(
        python_modules=(module,), sv_source_files=(source,))) == data
    manifest = parse_manifest(data)
    mirrors = "\n".join(emit_python_mirrors(manifest).values())
    assert "item = _codec_from_spec(" in mirrors
    assert "flags = _codec_from_spec(" in mirrors
    assert "def echo(" in mirrors
    bridge = emit_sv_mirrors(manifest)
    assert bridge.count("package svx_static_specialization_chain_pkg_Root_pkg;") == 1
    assert "super.new(value);" in bridge
    assert "function new(input byte value);" in bridge
    assert "function new(input shortint unsigned value);" in bridge
    for name in ("ByteChild", "ShortChild"):
        root_id = lineages[name][0]["canonical_id"]
        assert root_id + ".item@svx_field_read" in bridge
        assert root_id + "#echo" in bridge
        assert f'register_static("{root_id}"' in bridge
        assert root_id + "#static_echo" in mirrors


@pytest.mark.parametrize("named_specialization", [False, True])
def test_source_discovery_infers_unmapped_class_and_vif_handles(tmp_path, named_specialization):
    pytest.importorskip("pyslang")
    types = tmp_path / "types.sv"
    packet_definition = ("class PacketTemplate #(int WIDTH=4); endclass typedef PacketTemplate#(8) Packet;"
                         if named_specialization else "class Packet; endclass")
    types.write_text(
        "interface discovered_bus; logic data; modport master(output data); endinterface\n"
        f"package packet_pkg; {packet_definition} endpackage\n"
    )
    source = tmp_path / "base.sv"
    source.write_text(
        "package source_handles_pkg; class Base;\n"
        "packet_pkg::Packet packet; virtual discovered_bus.master vif;\n"
        "function new(packet_pkg::Packet packet, virtual discovered_bus.master vif);\n"
        "this.packet=packet; this.vif=vif; endfunction\n"
        "virtual function packet_pkg::Packet echo_packet(input packet_pkg::Packet value); return value; endfunction\n"
        "virtual function virtual discovered_bus.master echo_vif(input virtual discovered_bus.master value); return value; endfunction\n"
        "endclass endpackage\n"
    )
    Stub = sv_mirror("sv://source_handles_pkg/Base")(type("HandleStub", (SVMirror,), {}))
    module = ModuleType("checks.discovered_handles")
    def echo_packet(self, value: RemoteRef["sv://packet_pkg/Packet"]) -> Function[RemoteRef["sv://packet_pkg/Packet"]]:
        return value
    def echo_vif(self, value: RemoteRef["sv-vif://discovered_bus/master"]) -> Function[RemoteRef["sv-vif://discovered_bus/master"]]:
        return value
    for method in (echo_packet, echo_vif):
        method.__module__ = module.__name__
    module.Child = inheritance_class()(type("Child", (Stub,), {
        "__module__": module.__name__, "echo_packet": inheritance_method(echo_packet),
        "echo_vif": inheritance_method(echo_vif),
    }))
    manifest = manifest_from_declarations(python_modules=(module,), sv_source_files=(types, source))
    assert [target.name for target in manifest.classes] == ["Child"]
    base = manifest.classes[0].base_lineage[0]
    packet, vif = base.methods
    packet_type = "packet_pkg::PacketTemplate#(8)" if named_specialization else "packet_pkg::Packet"
    for handle in (packet.parameters[0].handle, packet.return_handle, base.fields[0].handle,
                   base.constructor.parameters[0].handle):
        assert handle.kind == "sv_class"
        assert handle.sv_type == packet_type
        assert handle.target_type_name == "sv://packet_pkg/Packet"
    for handle in (vif.parameters[0].handle, vif.return_handle, base.fields[1].handle,
                   base.constructor.parameters[1].handle):
        assert handle.kind == "virtual_interface"
        assert handle.target_type_name == "sv-vif://discovered_bus/master"
        assert [operation.method.name for operation in handle.operations] == ["write_data"]
    assert json.loads(packet.return_type.svtypes_identity_json) == type_spec_identity(RemoteRef["sv://packet_pkg/Packet"])
    assert module.Child.__svx_inheritance_class__["methods"][0].get("return_handle") is None
    assert manifest.classes[0].methods[0].return_handle.sv_type == packet_type
    assert manifest.classes[0].methods[1].return_handle.operations
    emitted = emit_sv_mirrors(manifest)
    assert f"{packet_type} value" in emitted
    assert "virtual discovered_bus.master value" in emitted


@pytest.mark.parametrize("proxy_base,separate_package", [("A", False), ("Other", False), ("A", True)])
def test_source_discovery_connects_proxy_and_mirror_into_complete_alternating_lineage(tmp_path, monkeypatch, proxy_base, separate_package):
    pytest.importorskip("pyslang")
    namespace = ModuleType("checks")
    namespace.__path__ = []
    monkeypatch.setitem(sys.modules, "checks", namespace)
    source = tmp_path / "alternating.sv"
    prefix = (
        "package alternating_pkg;\n"
        "class A; virtual function int check(); return 1; endfunction endclass\n"
        "class Other; endclass\n"
    )
    c_package = "consumer_pkg" if separate_package else "alternating_pkg"
    if separate_package:
        prefix += "endpackage\npackage bridge_pkg;\n"
        proxy_base = "alternating_pkg::" + proxy_base
    marker_header = tmp_path / "proxy.svh"
    marker_header.write_text(f"`SVX_PY_PROXY(BProxy, \"py://checks/alternating/B\", {proxy_base})\n")
    prefix += '`include "proxy.svh"\n'
    if separate_package:
        prefix += "endpackage\npackage consumer_pkg;\n"
    proxy_type = "bridge_pkg::BProxy" if separate_package else "BProxy"
    source.write_text(prefix +
        f"class C extends {proxy_type}; function int check(); return 2; endfunction\n"
        "function int compute(input int value); return extra + value; endfunction endclass\n"
        "endpackage\n"
    )
    AStub = sv_mirror("sv://alternating_pkg/A")(type("AStub", (SVMirror,), {}))
    parent_module = ModuleType("checks.alternating")
    monkeypatch.setitem(sys.modules, parent_module.__name__, parent_module)
    def compute(self, value: Int) -> Function[Int]:
        return self.extra + value
    compute.__module__ = parent_module.__name__
    B = inheritance_class(canonical_id="py://checks/alternating/B")(
        type("B", (AStub,), {"__module__": parent_module.__name__,
                            "extra": Int(), "compute": inheritance_method(compute)})
    )
    CStub = sv_mirror(f"sv://{c_package}/C")(type("CStub", (SVMirror,), {}))
    target_module = ModuleType("checks.alternating_target")
    target_module.B = B
    target_module.D = inheritance_class()(
        type("D", (CStub, B), {"__module__": target_module.__name__})
    )
    if proxy_base.endswith("Other"):
        with pytest.raises(SVXInheritanceError, match="base does not match Python Mirror base"):
            manifest_from_declarations(python_modules=(target_module,), sv_source_files=(source,),
                                       sv_include_dirs=(tmp_path,))
        return
    manifest = manifest_from_declarations(python_modules=(target_module,), sv_source_files=(source,),
                                          sv_include_dirs=(tmp_path,))
    assert [target.name for target in manifest.classes] == ["D"]
    lineage = manifest_dict(manifest)["classes"][0]["base_lineage"]
    assert [(ancestor["language"], ancestor["symbol"]) for ancestor in lineage] == [
        ("sv", "alternating_pkg::A"), ("python", "checks.alternating.B"),
        ("sv", c_package + "::C"),
    ]
    assert lineage[-1]["methods"][0]["virtual"] is True
    assert lineage[-1]["methods"][1]["name"] == "compute"
    assert lineage[-1]["methods"][1]["virtual"] is True
    assert [field["name"] for field in lineage[1]["fields"]] == ["extra"]
    from svx.sv_source_options import _source_parse_options
    scaffold = scan_sv_sources(
        [source], parse_options=_source_parse_options({}, (), [tmp_path], discover_proxies=True),
        proxy_context=[B.__svx_inheritance_class__],
    )
    proxy_symbol = "bridge_pkg::BProxy" if separate_package else "alternating_pkg::BProxy"
    assert "compute" in scaffold[proxy_symbol].virtual_methods
    assert [(field.name, field.sv_type) for field in scaffold[proxy_symbol].fields] == [("extra", "int")]
    assert all("discovery_base_id" not in ancestor for ancestor in lineage)
    assert all("BProxy" not in ancestor["symbol"] for ancestor in lineage)
    assert B.__svx_inheritance_class__["base_lineage"] == []
    from svx.source_layout import _emit_sv_root_source_unit
    generated_sv = _emit_sv_root_source_unit(manifest, source.read_text(), include_dirs=(tmp_path,))
    generated_base = "bridge_pkg::_svx_proxy_B" if separate_package else "_svx_proxy_B"
    assert f"class C extends {generated_base}" in generated_sv
    assert "typedef _svx_proxy_B BProxy;" in generated_sv
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_dict(manifest)))
    arguments = ["inheritance-gen", "--manifest", str(manifest_path),
                 "--sv-include-dir", str(tmp_path),
                 "--sv-source", str(source), "--sv-integrated-dir", str(tmp_path / "sv"),
                 "--python-out", str(tmp_path / "python"),
                 "--artifact-manifest", str(tmp_path / "artifacts.json")]
    assert main(arguments, out=StringIO()) == 0
    integrated = (tmp_path / "sv" / "source.sv").read_text()
    assert f"class C extends {generated_base}" in integrated
    assert "typedef _svx_proxy_B BProxy;" in integrated
    assert integrated.index("class _svx_proxy_B") < integrated.index("typedef _svx_proxy_B BProxy;")
    assert integrated.index("typedef _svx_proxy_B BProxy;") < integrated.index("class C extends")
    assert main([*arguments, "--check"], out=StringIO()) == 0
    if separate_package:
        packages = source.read_text().split("endpackage\n")
        with pytest.raises(SVXInheritanceError, match="precedes its SV base definition"):
            _emit_sv_root_source_unit(manifest, "endpackage\n".join(
                [packages[1], packages[0], packages[2], packages[3]]), include_dirs=(tmp_path,))
        with pytest.raises(SVXInheritanceError, match="precedes its Python Proxy definition"):
            _emit_sv_root_source_unit(manifest, "endpackage\n".join(
                [packages[0], packages[2], packages[1], packages[3]]), include_dirs=(tmp_path,))


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

    selected = ModuleType("checks.selected_mirror_descendant")
    selected.Child = Child
    selected.Leaf = inheritance_class(canonical_id="py://checks/Leaf")(
        type("Leaf", (Child,), {"__module__": selected.__name__}))
    expanded = manifest_from_declarations(
        python_modules=(selected,), sv_declaration_files=(sv_file,))
    leaf = next(item for item in expanded.classes if item.canonical_id == "py://checks/Leaf")
    assert [item.canonical_id for item in leaf.base_lineage] == [
        "sv://tb_pkg/BaseDriver", "py://checks/Child"]
    assert "py://checks/Child" not in {item.canonical_id for item in expanded.classes}
    assert Child.__svx_inheritance_class__["base_lineage"] == []


def test_discovery_expands_imported_python_ancestors_without_extra_targets():
    module = ModuleType("checks.selected_descendant")
    root = inheritance_class(canonical_id="py://other/Root")(
        type("Root", (), {"__module__": "checks.other"}))
    middle = inheritance_class(canonical_id="py://other/Middle")(
        type("Middle", (root,), {"__module__": "checks.other"}))
    leaf = inheritance_class(canonical_id="py://selected/Leaf")(
        type("Leaf", (middle,), {"__module__": module.__name__}))
    module.Leaf = leaf
    module.Middle = middle
    original = dict(middle.__svx_inheritance_class__)
    manifest = manifest_from_declarations(python_modules=(module,))
    assert [item.canonical_id for item in manifest.classes] == ["py://selected/Leaf"]
    assert [item.canonical_id for item in manifest.classes[0].base_lineage] == [
        "py://other/Root", "py://other/Middle"]
    assert middle.__svx_inheritance_class__ == original
    assert "python_base_ids" not in manifest_dict(manifest)["classes"][0]


def test_discovery_uses_direct_mirror_not_earlier_python_portion(tmp_path):
    a = sv_mirror("sv://p/A")(type("AMirror", (SVMirror,), {}))
    b = inheritance_class(canonical_id="py://p/B")(
        type("B", (a,), {"__module__": "checks.other"}))
    c = sv_mirror("sv://p/C")(type("CMirror", (SVMirror,), {}))
    d = inheritance_class(canonical_id="py://p/D")(
        type("D", (c, b), {"__module__": "checks.selected"}))
    assert d.__svx_inheritance_class__["mirror_base_ids"] == ["sv://p/C"]
    assert d.__svx_inheritance_class__["python_base_ids"] == ["py://p/B"]
    module = ModuleType("checks.selected")
    module.D = d
    a_declaration = {"canonical_id": "sv://p/A", "language": "sv",
                     "symbol": "p::A", "methods": []}
    c_declaration = {"canonical_id": "sv://p/C", "language": "sv",
                     "symbol": "p::C", "methods": []}
    sv_file = tmp_path / "declarations.json"

    def write_declarations():
        sv_file.write_text(json.dumps({"schema_uri": SV_DECLARATION_SCHEMA_URI,
                                      "schema_version": SV_DECLARATION_SCHEMA_VERSION,
                                      "classes": [a_declaration, c_declaration]}))

    write_declarations()
    with pytest.raises(SVXInheritanceError, match="bases absent from its SV mirror lineage"):
        manifest_from_declarations(python_modules=(module,), sv_declaration_files=(sv_file,))
    b_declaration = {key: value for key, value in b.__svx_inheritance_class__.items()
                     if key not in {"base_lineage", "mirror_base_ids", "python_base_ids"}}
    c_declaration["base_lineage"] = [a_declaration, b_declaration]
    write_declarations()
    manifest = manifest_from_declarations(python_modules=(module,), sv_declaration_files=(sv_file,))
    target = next(item for item in manifest.classes if item.canonical_id == "py://p/D")
    assert [item.canonical_id for item in target.base_lineage] == [
        "sv://p/A", "py://p/B", "sv://p/C"]
    assert "py://p/B" not in {item.canonical_id for item in manifest.classes}


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


def test_redefined_field_refreshes_discovery_codec_factory(monkeypatch):
    import svtypes

    module = ModuleType("checks.redefined_fields")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    for width in (8, 16):
        module.Driver = inheritance_class()(type(
            "Driver", (), {"__module__": module.__name__, "data": Bit[width]()}
        ))
        manifest = manifest_from_declarations(python_modules=(module,))
        binding = manifest.classes[0].fields[0].type_binding
        codec = module.__svx_declared_codec_Driver_data()
        assert svtypes.unified_type_name(codec) == binding.unified_type_name
        assert svtypes.encoding_descriptor(codec) == svtypes.encoding_descriptor(Bit[width]())


def test_discovery_codec_factory_rejects_user_name_collision(monkeypatch):
    module = ModuleType("checks.codec_collision")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    module.__svx_declared_codec_Driver_data = lambda: Int()
    Driver = type("Driver", (), {"__module__": module.__name__, "data": Bit[8]()})
    with pytest.raises(SVXInheritanceError, match="unavailable"):
        inheritance_class()(Driver)


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


def test_pyslang_validates_specialization_parameter_count_kind_and_order(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "parameters.sv"
    source.write_text(
        "package p; class Base #(type T=int, U=bit, int N=2, M=3); "
        "endclass endpackage"
    )
    assert scan_sv_sources([source])["p::Base"].parameter_kinds == (
        "type", "type", "value", "value"
    )
    valid = {"symbol": "p::Base", "specialization": {"arguments": [
        {"kind": kind} for kind in ("type", "type", "value", "value")
    ]}}
    validate_sv_declarations([valid], [source])
    wrong_count = {"symbol": "p::Base", "specialization": {"arguments": []}}
    with pytest.raises(SVXInheritanceError, match="requires 4 ordered source parameters"):
        validate_sv_declarations([wrong_count], [source])
    wrong_order = {"symbol": "p::Base", "specialization": {"arguments": [
        {"kind": kind} for kind in ("type", "value", "type", "value")
    ]}}
    with pytest.raises(SVXInheritanceError, match="argument 1 expects type, got value"):
        validate_sv_declarations([wrong_order], [source])
    source.write_text("package p; class Base #(int N=2); endclass endpackage\n")
    assert scan_sv_sources([source])["p::Base"].parameter_kinds == ("value",)
    with pytest.raises(SVXInheritanceError, match="requires 1 ordered source parameters"):
        validate_sv_declarations([valid], [source])


def test_sv_scanner_accepts_warnings_but_rejects_syntax_errors(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "warning.sv"
    source.write_text("package p; class A; endclass endpackage")
    assert "p::A" in scan_sv_sources([source])
    source.write_text("interface bus; logic data; endinterface")
    assert "bus" in scan_sv_virtual_interfaces([source])
    source.write_text("package p; class A; function broken(; endpackage\n")
    with pytest.raises(SVXInheritanceError, match="cannot parse SystemVerilog source"):
        scan_sv_sources([source])
    with pytest.raises(SVXInheritanceError, match="cannot parse SystemVerilog source"):
        scan_sv_virtual_interfaces([source])


def test_sv_method_prototypes_validate_order_direction_timing_and_pure_virtual(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "methods.sv"
    source.write_text(
        "package p; virtual class Base;\n"
        "virtual function int calculate(output int x, y, input int z); return z; endfunction\n"
        "pure virtual task run(input int count);\n"
        "endclass endpackage\n"
        "interface bus; task calculate(output int x, y, input int z); endtask endinterface\n"
    )
    fact = scan_sv_sources([source])["p::Base"]
    assert fact.virtual_methods == {"calculate", "run"}
    assert [(p.name, p.direction, p.sv_type) for p in fact.methods[0].parameters] == [
        ("x", "output", "int"), ("y", "output", "int"), ("z", "input", "int")
    ]
    vif_method = scan_sv_virtual_interfaces([source])["bus"].members[0]
    assert vif_method.parameters == fact.methods[0].parameters
    valid_method = {"name": "calculate", "timing": "function", "virtual": True,
                    "parameters": [
                        {"name": "x", "direction": "output"},
                        {"name": "y", "direction": "output"},
                        {"name": "z"},
                    ]}
    validate_sv_declarations([{"symbol": "p::Base", "methods": [valid_method]}], [source])
    for changed, message in (
        ({"timing": "task"}, "timing is task"),
        ({"parameters": []}, "requires 3 ordered source parameters"),
        ({"parameters": list(reversed(valid_method["parameters"]))}, "parameter 0 expects output x"),
        ({"parameters": [{"name": "x"}, *valid_method["parameters"][1:]]}, "parameter 0 expects output x"),
    ):
        with pytest.raises(SVXInheritanceError, match=message):
            validate_sv_declarations([{"symbol": "p::Base", "methods": [{**valid_method, **changed}]}], [source])
    validate_sv_declarations([{"symbol": "p::Base", "methods": [{
        "name": "run", "virtual": True, "pure_virtual": True,
        "timing": "task", "parameters": [{"name": "count"}]
    }]}], [source])


def test_source_validation_resolves_inherited_and_implicitly_virtual_methods(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "inherited.sv"
    source.write_text(
        "package p; class Base #(type T=int);\n"
        "virtual function int check(input int value); return value; endfunction\n"
        "function int get_count(); return 3; endfunction\n"
        "static function int static_count(); return 4; endfunction\n"
        "endclass endpackage\n"
        "package q; class Child extends p::Base#(int);\n"
        "function int check(input int value); return super.check(value)+1; endfunction\n"
        "endclass endpackage\n"
    )
    assert scan_sv_sources([source])["q::Child"].direct_base == "p::Base"
    declaration = {"symbol": "q::Child", "base_lineage": [{"language": "sv", "symbol": "p::Base"}],
                   "methods": [
                       {"name": "check", "virtual": True, "timing": "function", "parameters": [{"name": "value"}]},
                       {"name": "get_count", "timing": "function", "parameters": []},
                       {"name": "static_count", "static": True, "timing": "function", "parameters": []},
                   ]}
    validate_sv_declarations([declaration], [source])
    with pytest.raises(SVXInheritanceError, match="was not found in scanned source lineage"):
        validate_sv_declarations([{"symbol": "q::Child", "methods": [{"name": "missing"}]}], [source])
    with pytest.raises(SVXInheritanceError, match="requires 0 ordered source parameters"):
        validate_sv_declarations([{"symbol": "q::Child", "methods": [{
            "name": "get_count", "parameters": [{"name": "wrong"}]
        }]}], [source])


def test_body_port_method_declarations_preserve_formal_order_and_directions(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "body_ports.sv"
    body = (
        "function int calculate; input int value; output int first, second; "
        "first=value; second=value+1; return value; endfunction\n"
    )
    source.write_text("package p; class Base; " + body + "endclass endpackage\n"
                      + "interface bus; " + body + "endinterface\n")
    method = scan_sv_sources([source])["p::Base"].methods[0]
    assert [(p.name, p.direction, p.sv_type) for p in method.parameters] == [
        ("value", "input", "int"), ("first", "output", "int"), ("second", "output", "int")
    ]
    assert scan_sv_virtual_interfaces([source])["bus"].members[0].parameters == method.parameters
    validate_sv_declarations([{"symbol": "p::Base", "methods": [{
        "name": "calculate", "timing": "function", "parameters": [
            {"name": "value"}, {"name": "first", "direction": "output"},
            {"name": "second", "direction": "output"},
        ],
    }]}], [source])


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
                                "parameters": [inheritance_parameter("value", Int)],
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
                                        "parameters": [inheritance_parameter("value", Int)],
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


def test_source_discovery_populates_native_handle_fields(tmp_path):
    from svx.declarations import enrich_virtual_interface_manifest
    from tests.integration.constructor_handles_schema import manifest_data

    data = manifest_data()
    base = data["classes"][0]
    for field in base["fields"]:
        field.pop("handle")
    before = json.dumps(data, sort_keys=True)
    model = parse_manifest(data)
    paths = [Path("tests/integration/constructor_handle_types.sv"),
             Path("tests/integration/external_bus_if.sv")]
    enriched = enrich_virtual_interface_manifest(model, sv_source_files=paths)
    fields = enriched.classes[0].fields
    assert fields[0].handle.sv_type == "external_handle_test_pkg::Packet"
    assert fields[1].handle.sv_type == "virtual external_bus_if.master"
    assert fields[1].handle.operations
    assert len(enriched.classes) == len(model.classes)
    assert json.dumps(data, sort_keys=True) == before
    assert all(field.handle is None for field in model.classes[0].fields)

    # Re-reading the same path must expose a changed member type, not cached text.
    source = tmp_path / "types.sv"
    original = paths[0].read_text()
    source.write_text(original)
    assert scan_sv_sources([source])["constructor_handle_pkg::Holder"].fields[2].sv_type == "external_handle_test_pkg::Packet"
    source.write_text(original.replace("Packet native_packet", "PacketReplacement native_packet").replace("class Packet;", "class PacketReplacement;"))
    with pytest.raises(SVXInheritanceError, match="source type"):
        enrich_virtual_interface_manifest(enriched, sv_source_files=[source, paths[1]])


@pytest.mark.parametrize("member", ["static", "local", "array", "missing"])
def test_source_handle_field_discovery_rejects_incompatible_members(tmp_path, member):
    from svx.declarations import enrich_virtual_interface_manifest
    from tests.integration.constructor_handles_schema import manifest_data

    data = manifest_data()
    source = tmp_path / "types.sv"
    original = Path("tests/integration/constructor_handle_types.sv").read_text()
    declaration = "external_handle_test_pkg::Packet native_packet;"
    replacement = {
        "static": "static " + declaration,
        "local": "local " + declaration,
        "array": declaration.replace(";", "[2];"),
        "missing": "",
    }[member]
    source.write_text(original.replace(declaration, replacement))
    with pytest.raises(SVXInheritanceError, match="native_packet"):
        enrich_virtual_interface_manifest(parse_manifest(data), sv_source_files=[source])


def test_source_vif_long_spelling_is_normalized(tmp_path):
    from svx.declarations import enrich_virtual_interface_manifest
    from tests.integration.constructor_handles_schema import manifest_data

    source = tmp_path / "types.sv"
    original = Path("tests/integration/constructor_handle_types.sv").read_text()
    source.write_text(original.replace("virtual external_bus_if.master native_vif",
                                       "virtual interface external_bus_if.master native_vif"))
    model = enrich_virtual_interface_manifest(parse_manifest(manifest_data()), sv_source_files=[
        source, Path("tests/integration/external_bus_if.sv")])
    assert model.classes[0].fields[1].handle.sv_type == "virtual external_bus_if.master"


def test_declaration_handles_generate_vif_operations(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "bus_if.sv"
    source.write_text(
        "interface bus_if;\n"
        "  logic [7:0] data;\n"
        "  task write(input logic [7:0] value); data = value; endtask\n"
        "  function logic [7:0] read(); return data; endfunction\n"
        "  function void snapshot(output logic [7:0] first, second); first=data; second=data; endfunction\n"
        "  modport master(output data, import write, read, snapshot);\n"
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
        "snapshot",
        "write",
        "write_data",
    ]
    assert method.return_handle is not None
    assert sorted(operation.method.name for operation in method.return_handle.operations) == [
        "read",
        "snapshot",
        "write",
        "write_data",
    ]
    snapshot = next(operation.method for operation in method.return_handle.operations
                    if operation.method.name == "snapshot")
    assert snapshot.timing == "function"
    assert snapshot.return_type is None
    assert [parameter.direction for parameter in snapshot.parameters] == ["output", "output"]


def test_inheritance_manifest_cli_generates_and_checks(tmp_path, monkeypatch):
    module_path = tmp_path / "declared.py"
    module_path.write_text(
        "from __future__ import annotations\n"
        "from svtypes import Int\n"
        "from svx import Function, inheritance_class, inheritance_method\n"
        "@inheritance_class(canonical_id='py://declared/Driver')\n"
        "class Driver:\n"
        "    def __init__(self, seed: Int):\n"
        "        self.seed = seed\n"
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
    declared = load_manifest(target).classes[0]
    assert declared.name == "Driver"
    assert [parameter.name for parameter in declared.constructor.parameters] == ["seed"]
    assert declared.constructor.parameters[0].direction == "input"
    assert main([*arguments, "--check"], out=StringIO()) == 0
