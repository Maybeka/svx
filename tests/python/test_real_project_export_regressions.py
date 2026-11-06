from collections import Counter
from io import StringIO
import json
from types import SimpleNamespace

import pytest
import svtypes

from svx import _native
from svx.cli import main
from svx.declarations import SVMirror, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import _remote_ref_validator
from svx.sv_value_scan import SourceValues


def test_plain_mirror_reserves_receiver_for_constructor_virtual_calls(tmp_path):
    source = tmp_path / 'constructor.sv'
    source.write_text('''package p;
      class Item;
        int value;
        function new(int seed = 3); value = transform(seed); endfunction
        virtual function int transform(int seed); return seed + 1; endfunction
      endclass
    endpackage''')
    output = tmp_path / 'generated'
    assert main(['export', '--sv-source', str(source), '--class', 'p::Item',
                 '--out', str(output)], out=StringIO()) == 0
    sv = (output / 'mirrors.sv').read_text()
    py = (output / 'python/svx_mirror/p.py').read_text()
    assert '::enter(object_id, this)' in sv
    assert 'super.new(seed);' in sv
    assert '`SVX_COMPLETE_CONSTRUCTED_RECEIVER(' in sv
    method = sv.split('virtual function int transform', 1)[1].split('endfunction', 1)[0]
    assert method.index('this.__svx_reserve_early_receiver();') < method.index('svx_inheritance_call_python_function(')
    assert '__svx_direct_mirror_field_ids__' in py
    assert '_create_sv_with_direct_mirror(' in py


def test_randomization_hooks_preserve_method_qualifiers_and_validate(tmp_path):
    source = tmp_path / 'hooks.sv'
    source.write_text('''package p;
      virtual class Base;
        pure virtual function int check();
        static function int version(); return 7; endfunction
        function void pre_randomize(); endfunction
        function void post_randomize(); endfunction
      endclass
    endpackage''')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['p::Base'])
    methods = {m.name: m for m in manifest.classes[0].methods}
    assert methods['check'].virtual and methods['check'].pure_virtual
    assert methods['version'].is_static
    for name in ('pre_randomize', 'post_randomize'):
        assert not methods[name].is_static and not methods[name].pure_virtual
    output = tmp_path / 'generated'
    arguments = ['export', '--sv-source', str(source), '--class', 'p::Base', '--out', str(output)]
    assert main(arguments, out=StringIO()) == 0
    assert main([*arguments, '--check'], out=StringIO()) == 0


def test_mirror_handle_arguments_use_declared_base_target_and_live_identity(monkeypatch):
    class Mirror(SVMirror):
        __svx_foreign_class_id__ = 'sv://p/Child'
        __svx_foreign_class_ids__ = ('sv://p/Base', 'sv://p/Child')

    mirror = Mirror()
    mirror._svx_remote_object_id = 17
    monkeypatch.setattr(_native, 'inheritance_get', lambda oid: mirror if oid == 17 else None)
    codec = svtypes.RemoteRef['sv://p/Base']()
    normalize = _remote_ref_validator(codec)
    expected = svtypes.RemoteRefValue('sv://p/Base', 17)
    assert normalize(mirror) == expected
    assert normalize(expected) == expected
    assert normalize(None) is None
    collection = _remote_ref_validator(svtypes.Queue[svtypes.RemoteRef['sv://p/Base']]())
    assert collection([mirror, None]) == [expected, None]
    wrong = _remote_ref_validator(svtypes.RemoteRef['sv://p/Unrelated']())
    with pytest.raises(SVXInheritanceError, match='foreign object type mismatch'):
        wrong(mirror)
    monkeypatch.setattr(_native, 'inheritance_get', lambda oid: None)
    with pytest.raises(SVXInheritanceError, match='unknown or stale'):
        normalize(mirror)
    mirror._svx_remote_object_id = None
    with pytest.raises(SVXInheritanceError, match='unbound or retired'):
        normalize(mirror)


def test_class_value_graph_resolves_native_members_only_once():
    visits = Counter()

    class Node:
        genericClass = None
        def __init__(self, name, entries):
            self.name, self.entries = name, entries
        def __iter__(self):
            visits[self.name] += 1
            return iter(self.entries)
        def lookupName(self, name):
            visits['lookup'] += 1
            return next(entry for entry in self.entries if entry.name == name)

    leaf = Node('leaf', [])
    leaf.isClass = True
    alias = SimpleNamespace(name='Alias', kind=SimpleNamespace(name='TypeAlias'),
                            canonicalType=leaf, visibility=SimpleNamespace(name='Public'))
    root = Node('root', [alias])
    values = SourceValues({})
    for index in range(32):
        values.register_class_values(root, f'p::Owner{index}')
    assert visits == {'root': 1, 'leaf': 1}
    assert len(values.class_value_members) == 32


def test_class_value_cache_preserves_distinct_alias_paths(tmp_path):
    source = tmp_path / 'aliases.sv'
    source.write_text('''package p;
      class Leaf #(int WIDTH = 9);
        typedef enum bit [1:0] {Idle, Active} Mode;
      endclass
      class Root;
        typedef Leaf#(9) Left;
        typedef Leaf#(9) Right;
      endclass
    endpackage''')
    output = tmp_path / 'generated'
    assert main(['export', '--sv-source', str(source), '--type',
                 'p::Root::Left::Mode', 'p::Root::Right::Mode', '--out', str(output)],
                out=StringIO()) == 0
    manifest = json.loads((output / 'inheritance.json').read_text())
    assert {t['symbol'] for t in manifest['value_types']} >= {'p::Root::Left::Mode', 'p::Root::Right::Mode'}
