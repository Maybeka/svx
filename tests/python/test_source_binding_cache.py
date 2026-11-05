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
