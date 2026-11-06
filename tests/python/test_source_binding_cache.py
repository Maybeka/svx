import svtypes
import svx.declarations as declarations


def test_source_primitive_cache_is_scoped_and_returns_independent_metadata(monkeypatch):
    original = declarations._svtypes_binding
    calls = []
    def observed(annotation, *, where):
        calls.append(annotation)
        return original(annotation, where=where)
    monkeypatch.setattr(declarations, '_svtypes_binding', observed)

    @declarations._with_source_bindings
    def discover():
        first = declarations._source_binding(svtypes.Int, where='first')
        expected = declarations._source_binding(svtypes.Int, where='second')
        first['sv'] = 'changed'
        first['encoding_descriptor']['encoding_fingerprint'] = 'changed'
        assert declarations._source_binding(svtypes.Int, where='third') == expected

    discover()
    assert calls == [svtypes.Int]
    discover()
    assert calls == [svtypes.Int, svtypes.Int]


def test_source_binding_cache_does_not_memoize_user_types(monkeypatch):
    calls = []
    class UserType:
        pass
    def observed(annotation, *, where):
        calls.append(where)
        return {'where': where}
    monkeypatch.setattr(declarations, '_svtypes_binding', observed)

    @declarations._with_source_bindings
    def discover():
        assert declarations._source_binding(UserType, where='one') == {'where': 'one'}
        assert declarations._source_binding(UserType, where='two') == {'where': 'two'}
    discover()
    assert calls == ['one', 'two']


def test_source_owned_named_binding_reuses_metadata_without_sharing_mutations(monkeypatch):
    calls = []
    class SourceType:
        pass
    def observed(annotation, *, where):
        calls.append(where)
        return {'sv': 'Named', 'nested': {'values': [1, 2]}}
    monkeypatch.setattr(declarations, '_svtypes_binding', observed)

    @declarations._with_source_bindings
    def discover():
        first = declarations._source_binding(SourceType, where='one', source_owned=True)
        first['nested']['values'].append(3)
        second = declarations._source_binding(SourceType, where='two', source_owned=True)
        assert second['nested']['values'] == [1, 2]
    discover()
    discover()
    assert calls == ['one', 'one']


def test_intrinsic_semantic_conversion_reuse_is_scoped_and_independent(monkeypatch):
    from pyslang.ast import Compilation
    from pyslang.syntax import SyntaxTree
    compilation = Compilation()
    compilation.addSyntaxTree(SyntaxTree.fromText('package p; int a, b; bit [7:0] x, y; endpackage'))
    package = compilation.getPackage('p')
    calls = []
    original = declarations._source_binding

    def binding(*args, **kwargs):
        calls.append(kwargs['where'])
        return original(*args, **kwargs)
    monkeypatch.setattr(declarations, '_source_binding', binding)

    @declarations._with_source_bindings
    def discover():
        for first, second in [('a', 'b'), ('x', 'y')]:
            result = declarations._source_semantic_type_declaration(package.lookupName(first).type, where=first)
            expected = declarations._source_semantic_type_declaration(package.lookupName(second).type, where=second)
            result['encoding_descriptor']['encoding_fingerprint'] = 'changed'
            assert declarations._source_semantic_type_declaration(package.lookupName(first).type, where=first) == expected
    discover()
    assert calls == ['a', 'x']
    discover()
    assert calls == ['a', 'x', 'a', 'x']
