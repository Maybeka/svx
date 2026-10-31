from types import ModuleType

import pytest

from svx.declarations import manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import emit_python_mirrors, emit_sv_mirrors
from svx.sv_scan import scan_sv_sources


@pytest.mark.parametrize("selection, intermediate, expected", [
    ("import base_pkg::*;", "", "base_pkg::Base"),
    ("import base_pkg::Base;", "", "base_pkg::Base"),
    ("import exports::*;", "package exports; import base_pkg::Base; export base_pkg::Base; endpackage", "base_pkg::Base"),
    ("import aliases::Base;", "package aliases; typedef base_pkg::Base Base; endpackage", "aliases::Base"),
])
def test_imported_base_resolves_declaring_package_and_inherited_members(tmp_path, selection, intermediate, expected):
    pytest.importorskip("pyslang")
    base = tmp_path / "base.sv"
    base.write_text("package base_pkg; class Base; int count;\n// method documentation\n"
                    "virtual function int get_status(); return count; endfunction "
                    "\n// timed method documentation\nvirtual task poll(); endtask "
                    "endclass endpackage\n" + intermediate, encoding="utf-8")
    child = tmp_path / "driver.sv"
    child.write_text("package driver_pkg; " + selection +
                     " class Driver extends Base; "
                     "function int get_status(); return super.get_status(); endfunction "
                     "\n// override documentation\ntask poll(); super.poll(); endtask "
                     "endclass endpackage\n", encoding="utf-8")
    module = ModuleType("imported_driver")
    exec('import svx\n'
         '@svx.sv_mirror("sv://driver_pkg/Driver")\n'
         'class Mirror(svx.SVMirror): pass\n'
         '@svx.inheritance_class()\n'
         'class PythonDriver(Mirror): pass\n', module.__dict__)
    paths = [base, child]
    facts = scan_sv_sources(paths)
    assert facts["driver_pkg::Driver"].direct_base == expected
    manifest = manifest_from_declarations(python_modules=[module], sv_source_files=paths)
    lineage = manifest.classes[0].base_lineage
    assert [item.symbol for item in lineage] == [expected, "driver_pkg::Driver"]
    assert next(method for method in lineage[-1].methods if method.name == "get_status").virtual
    poll = next(method for method in lineage[-1].methods if method.name == "poll")
    assert poll.virtual and poll.timing == "task"
    assert any(field.name == "count" for item in lineage for field in item.fields)
    assert "def get_status(self)" in '\n'.join(emit_python_mirrors(manifest).values())
    assert "get_status" in emit_sv_mirrors(manifest)


def test_alias_of_derived_class_retains_resolved_imported_base(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "aliases.sv"
    source.write_text(
        "package base_pkg; class Base; endclass endpackage "
        "package middle_pkg; import base_pkg::*; class Middle extends Base; endclass endpackage "
        "package driver_pkg; typedef middle_pkg::Middle Driver; endpackage", encoding="utf-8")
    facts = scan_sv_sources([source])
    assert facts["middle_pkg::Middle"].direct_base == "base_pkg::Base"
    assert facts["driver_pkg::Driver"].direct_base == "base_pkg::Base"


def test_imported_base_does_not_choose_between_ambiguous_packages(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "ambiguous.sv"
    source.write_text(
        "package first; class Base; endclass endpackage "
        "package second; class Base; endclass endpackage "
        "package driver_pkg; import first::*; import second::*; "
        "class Driver extends Base; endclass endpackage", encoding="utf-8")
    module = ModuleType("ambiguous_driver")
    exec('import svx\n@svx.sv_mirror("sv://driver_pkg/Driver")\n'
         'class Mirror(svx.SVMirror): pass\n@svx.inheritance_class()\n'
         'class PythonDriver(Mirror): pass\n', module.__dict__)
    with pytest.raises(SVXInheritanceError):
        manifest_from_declarations(python_modules=[module], sv_source_files=[source])
