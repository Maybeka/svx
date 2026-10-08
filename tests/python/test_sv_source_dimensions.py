import pytest

from svx.declarations import _vif_operations
from svx.errors import SVXInheritanceError
from svx.sv_scan import scan_sv_sources, scan_sv_virtual_interfaces


@pytest.mark.parametrize("prototype", [
    "function int inspect(input int values[$], output int samples[3]); return 0; endfunction",
    "function int inspect; input int values[$]; output int samples[3]; return 0; endfunction",
])
def test_method_source_facts_preserve_unpacked_formal_dimensions(tmp_path, prototype):
    pytest.importorskip("pyslang")
    source = tmp_path / "dimensions.sv"
    source.write_text("package p; class A; " + prototype + " endclass endpackage\n"
                      + "interface bus; " + prototype + " endinterface\n")
    parameters = scan_sv_sources([source])["p::A"].methods[0].parameters
    assert [(parameter.name, parameter.sv_type) for parameter in parameters] == [
        ("values", "int [$]"), ("samples", "int [3]"),
    ]
    interface = scan_sv_virtual_interfaces([source])["bus"]
    assert interface.members[0].parameters == parameters
    # Until a collection mapping exists, never silently lower this to int.
    with pytest.raises(SVXInheritanceError, match="no declared SvTypes VIF mapping"):
        _vif_operations("sv-vif://bus", interface, None)


def test_vif_source_preserves_each_declarators_own_dimensions(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "signals.sv"
    source.write_text(
        "interface bus; logic [7:0] scalar, array[2], matrix[2][3]; "
        "modport view(input scalar, array, matrix); endinterface\n"
    )
    fact = scan_sv_virtual_interfaces([source])["bus"]
    assert [(member.name, member.sv_type) for member in fact.members] == [
        ("scalar", "logic [7:0]"), ("array", "logic [7:0] [2]"),
        ("matrix", "logic [7:0] [2][3]"),
    ]
    with pytest.raises(SVXInheritanceError, match="bus.array.*no declared SvTypes VIF mapping"):
        _vif_operations("sv-vif://bus/view", fact, "view")


def test_explicit_direction_resets_implicit_type_to_logic(tmp_path):
    pytest.importorskip("pyslang")
    from pyslang.ast import Compilation
    from pyslang.syntax import SyntaxTree

    text = (
        "package p; class A; function void inspect(input int a, output b, c, input d); "
        "endfunction endclass endpackage\n"
        "interface bus; function void inspect(input int a, output b, c, input d); "
        "endfunction endinterface\n"
    )
    source = tmp_path / "directions.sv"
    source.write_text(text)
    facts = scan_sv_sources([source])["p::A"].methods[0].parameters
    assert [(item.name, item.direction, item.sv_type) for item in facts] == [
        ("a", "input", "int"), ("b", "output", "logic"),
        ("c", "output", "logic"), ("d", "input", "logic"),
    ]
    assert scan_sv_virtual_interfaces([source])["bus"].members[0].parameters == facts
    compilation = Compilation()
    compilation.addSyntaxTree(SyntaxTree.fromText(text))
    compilation.getRoot()
    method = compilation.getPackage("p").lookupName("A").lookupName("inspect")
    assert [(argument.name, str(argument.type)) for argument in method.arguments] == [
        (item.name, item.sv_type) for item in facts
    ]
