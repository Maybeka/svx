import pytest

from svx.sv_frontend import source_analysis
from svx.sv_inventory import declaration_inventory
from svx.sv_selection import package_import_names, source_packages

pytest.importorskip('pyslang')
from pyslang.syntax import SyntaxKind, SyntaxNode, SyntaxTree


@pytest.mark.parametrize('inventory_first', [False, True])
def test_package_import_facts_shared_between_inventory_and_selection(tmp_path, monkeypatch, inventory_first):
    source = tmp_path / 'source.sv'
    source.write_text('''package dep; endpackage
package method_dep; endpackage
package p;
  import dep::*;
  class Driver;
    function void run();
      import method_dep::*;
      typedef int Hidden;
    endfunction
  endclass
  task tick(); import dep::*; endtask
endpackage
''', encoding='utf-8')
    original = SyntaxNode.visit
    traversed = []
    def observed(node, f=None, lookup_table=None):
        if lookup_table is not None and set(lookup_table) == {SyntaxKind.PackageImportItem}:
            traversed.append(node)
        return original(node, f=f, lookup_table=lookup_table)
    monkeypatch.setattr(SyntaxNode, 'visit', observed)
    with source_analysis() as state:
        if inventory_first:
            inventory = declaration_inventory([source])
            selected = source_packages([source])
        else:
            selected = source_packages([source])
            inventory = declaration_inventory([source])
        assert selected == {'dep': (), 'method_dep': (), 'p': ('dep', 'method_dep')}
        package = next(item for item in inventory['declarations'] if item['symbol'] == 'p')
        assert package['imports'] == ['dep', 'method_dep']
        package['imports'].append('not_a_dependency')
        assert source_packages([source]) == selected
        assert len(traversed) == len(state.package_imports) == 3


def test_package_import_facts_keep_tree_identity_not_package_name():
    first = SyntaxTree.fromText('package p; import first_dep::*; endpackage')
    second = SyntaxTree.fromText('package p; import second_dep::*; endpackage')
    with source_analysis() as state:
        assert package_import_names(first.root) == ('first_dep',)
        assert package_import_names(second.root) == ('second_dep',)
        assert len(state.package_imports) == 2


def test_package_import_facts_expire_with_analysis_scope(tmp_path):
    source = tmp_path / 'source.sv'
    source.write_text('package p; import first_dep::*; endpackage', encoding='utf-8')
    with source_analysis():
        assert source_packages([source]) == {'p': ('first_dep',)}
    source.write_text('package p; import second_dep::*; endpackage', encoding='utf-8')
    with source_analysis():
        assert source_packages([source]) == {'p': ('second_dep',)}


def test_inventory_does_not_visit_subroutine_local_declarations(tmp_path, monkeypatch):
    source = tmp_path / 'source.sv'
    source.write_text('''package p;
  typedef int Public;
  function int get(); typedef int FunctionLocal; return 1; endfunction
  task tick(); typedef int TaskLocal; endtask
  class Driver;
    function void method(); typedef int MethodLocal; endfunction
  endclass
endpackage
''', encoding='utf-8')
    original = SyntaxNode.visit
    names = []
    def observed(node, f=None, lookup_table=None):
        if lookup_table is not None:
            def wrap(handler):
                if handler.__qualname__ != 'declaration_inventory.<locals>.visit':
                    return handler
                def record(value):
                    if value.kind == SyntaxKind.TypedefDeclaration:
                        names.append(str(value.name.valueText))
                    return handler(value)
                return record
            lookup_table = {kind: wrap(handler) for kind, handler in lookup_table.items()}
        return original(node, f=f, lookup_table=lookup_table)
    monkeypatch.setattr(SyntaxNode, 'visit', observed)
    with source_analysis():
        result = declaration_inventory([source])
    assert names == ['Public']
    assert {item['symbol'] for item in result['declarations']} == {'p', 'p::Public', 'p::get', 'p::tick', 'p::Driver'}
