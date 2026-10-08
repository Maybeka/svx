from pathlib import Path
import ast
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _package_symbols(package, syntax):
    symbols = set()
    for member in package.members:
        kind = member.kind
        if kind in (syntax.SyntaxKind.FunctionDeclaration, syntax.SyntaxKind.TaskDeclaration):
            symbols.add(str(member.prototype.name).strip())
        elif kind == syntax.SyntaxKind.DPIImport:
            symbols.add(str(member.method.name).strip())
        elif kind in (syntax.SyntaxKind.ClassDeclaration, syntax.SyntaxKind.TypedefDeclaration):
            symbols.add(str(member.name).strip())
            if kind == syntax.SyntaxKind.TypedefDeclaration and member.type.kind == syntax.SyntaxKind.EnumType:
                symbols.update(str(item.name).strip() for item in member.type.members if hasattr(item, "name"))
        elif kind == syntax.SyntaxKind.ParameterDeclarationStatement:
            symbols.update(str(item.name).strip() for item in member.parameter.declarators if hasattr(item, "name"))
        elif kind not in (syntax.SyntaxKind.TimeUnitsDeclaration, syntax.SyntaxKind.DPIExport):
            pytest.fail(f"unhandled package declaration kind: {kind}")
    return symbols


def _classification():
    text = (ROOT / "docs/SVX_API_REFERENCE.md").read_text()
    table = text.split("### Package Declarations\n", 1)[1].split("### Generated Interfaces", 1)[0]
    result = {}
    for row in table.splitlines():
        columns = [column.strip() for column in row.split("|")]
        if len(columns) != 5 or columns[1] not in {"Stable", "Private", "Fixed Limit"}:
            continue
        for name in re.findall(r"`([^`]+)`", columns[3]):
            assert name not in result, f"duplicate classification for {name}"
            result[name] = columns[1]
    assert result
    return result


def test_all_sv_package_declarations_have_explicit_classification():
    pyslang = pytest.importorskip("pyslang")
    from pyslang import syntax

    manager = pyslang.SourceManager()
    manager.addUserDirectories(str(ROOT))
    tree = syntax.SyntaxTree.fromFile(str(ROOT / "sv/svx_pkg.sv"), manager)
    assert not list(tree.diagnostics)
    package = tree.root
    if package.kind == syntax.SyntaxKind.CompilationUnit:
        assert len(package.members) == 1
        package = package.members[0]
    assert package.kind == syntax.SyntaxKind.PackageDeclaration
    actual = _package_symbols(package, syntax)
    classified = _classification()
    assert actual == set(classified), {
        "unclassified": sorted(actual - set(classified)),
        "not_declared": sorted(set(classified) - actual),
    }


def test_every_core_dpi_export_has_a_compiler_signature_check():
    pyslang = pytest.importorskip("pyslang")
    manager = pyslang.SourceManager()
    manager.addUserDirectories(str(ROOT))
    tree = pyslang.syntax.SyntaxTree.fromFile(str(ROOT / "sv/svx_pkg.sv"), manager)
    assert not list(tree.diagnostics)
    package = tree.root.members[0]
    exports = {str(member.name).strip() for member in package.members
               if member.kind == pyslang.syntax.SyntaxKind.DPIExport}
    native = (ROOT / "svx_runtime/src/sv_dpi.cpp").read_text()
    checks = set(re.findall(r"decltype\(&::([A-Za-z_][A-Za-z_0-9]*)\)", native))
    assert exports == checks
    assert "using func_t = void (*)(" not in native


def test_fork_fixed_array_capacity_agrees_at_the_native_boundary():
    pyslang = pytest.importorskip("pyslang")
    manager = pyslang.SourceManager()
    manager.addUserDirectories(str(ROOT))
    tree = pyslang.syntax.SyntaxTree.fromFile(str(ROOT / "sv/svx_pkg.sv"), manager)
    package = tree.root.members[0]
    parameter = next(member.parameter for member in package.members
                     if member.kind == pyslang.syntax.SyntaxKind.ParameterDeclarationStatement
                     and any(str(item.name).strip() == "SVX_MAX_FORK_NUM"
                             for item in member.parameter.declarators))
    sv_capacity = int(str(parameter.declarators[0].initializer.expr).strip())
    native = (ROOT / "svx_runtime/include/svx/common.hpp").read_text()
    native_capacity = int(re.search(r"SVX_MAX_FORK_NUM\s*=\s*(\d+)", native).group(1))
    assert sv_capacity == native_capacity
    fork = next(member for member in package.members
                if member.kind == pyslang.syntax.SyntaxKind.TaskDeclaration
                and str(member.prototype.name).strip() == "fork_svx")
    assert "procs[SVX_MAX_FORK_NUM]" in str(fork.prototype)


def test_inventory_scanner_detects_a_new_package_function():
    pytest.importorskip("pyslang")
    from pyslang import syntax

    tree = syntax.SyntaxTree.fromText(
        "package svx_pkg; function void newly_added(); endfunction endpackage"
    )
    package = tree.root
    if package.kind == syntax.SyntaxKind.CompilationUnit:
        package = package.members[0]
    assert _package_symbols(package, syntax) - set(_classification()) == {"newly_added"}


_MANIFEST_OBJECTS = {
    "parse_manifest": ("root",),
    "_parse_class": ("class",),
    "_parse_method": ("method",),
    "_parse_parameter": ("parameter",),
    "_parse_field": ("field",),
    "_parse_constructor": ("constructor",),
    "_type_binding": ("type_binding", "encoding_descriptor", "python_factory"),
    "_handle_binding": ("handle",),
    "_parse_vif_operation": ("vif_operation",),
    "_parse_specialization": ("specialization", "specialization_type_argument",
                              "specialization_value_argument"),
}


def _manifest_parser_inventory(source):
    result = {}
    found = set()
    for function in ast.parse(source).body:
        if not isinstance(function, ast.FunctionDef):
            continue
        calls = sorted((node for node in ast.walk(function) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == "_reject_unknown"),
                       key=lambda node: node.lineno)
        if not calls:
            continue
        assert function.name in _MANIFEST_OBJECTS, f"unclassified manifest parser {function.name}"
        found.add(function.name)
        objects = _MANIFEST_OBJECTS[function.name]
        assert len(calls) == len(objects), f"unclassified object shape in {function.name}"
        for name, call in zip(objects, calls):
            allowed = call.args[1]
            if isinstance(allowed, ast.Name):
                assignments = [node.value for node in ast.walk(function) if isinstance(node, ast.Assign)
                               and any(isinstance(target, ast.Name) and target.id == allowed.id
                                       for target in node.targets)]
                assert len(assignments) == 1
                keys = set(ast.literal_eval(assignments[0]))
                for node in ast.walk(function):
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                            and isinstance(node.func.value, ast.Name) and node.func.value.id == allowed.id):
                        assert node.func.attr == "add", "unsupported allowed-key mutation"
                        keys.add(ast.literal_eval(node.args[0]))
            else:
                keys = set(ast.literal_eval(allowed))
            assert all(isinstance(key, str) for key in keys)
            result[name] = keys
    assert found == set(_MANIFEST_OBJECTS)
    return result


def _manifest_document_inventory():
    text = (ROOT / "docs/SVX_API_REFERENCE.md").read_text().split("## Manifest Field Inventory", 1)[1]
    result = {}
    for line in text.splitlines():
        columns = [column.strip() for column in line.split("|")[1:-1]]
        if len(columns) != 4 or columns[1] not in {"Stable", "Legacy"}:
            continue
        assert columns[0] not in result
        names = re.findall(r"`([^`]+)`", columns[2])
        assert len(names) == len(set(names))
        result[columns[0]] = set(names)
    assert result
    return result


def test_manifest_field_inventory_matches_all_parser_object_shapes():
    source = (ROOT / "python/svx/inheritance.py").read_text()
    assert _manifest_parser_inventory(source) == _manifest_document_inventory()


def test_manifest_inventory_detects_an_added_field():
    source = (ROOT / "python/svx/inheritance.py").read_text()
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "_parse_field")
    call = next(node for node in ast.walk(function) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "_reject_unknown")
    call.args[1].elts.append(ast.Constant("new_field_policy"))
    inventory = _manifest_parser_inventory(ast.unparse(tree))
    assert inventory["field"] - _manifest_document_inventory()["field"] == {"new_field_policy"}
