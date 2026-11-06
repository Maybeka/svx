from types import SimpleNamespace

import pytest
import svtypes

from svx import inheritance as bridge
import svx.sv_scan as scan


def test_members_and_argument_lists_are_read_once_and_type_pairs_reused(monkeypatch):
    from pyslang.ast import MethodFlags
    calls = {'lookup': 0, 'arguments': 0, 'matching': 0, 'expected_lookup': 0}

    class Type:
        isError = False
        @property
        def canonicalType(self):
            return self
        def isMatching(self, other):
            calls['matching'] += 1
            return True

    actual, expected = Type(), Type()
    class Method:
        isVirtual = False
        flags = MethodFlags(0)
        visibility = SimpleNamespace(name='Public')
        returnType = actual
        @property
        def arguments(self):
            calls['arguments'] += 1
            return [SimpleNamespace(type=actual) for _ in range(64)]
    method = Method()

    def lookup(name):
        calls['lookup'] += 1
        return method

    native = SimpleNamespace(lookupName=lookup)
    checked = SimpleNamespace(returnType=expected, arguments=[SimpleNamespace(type=expected)])
    def expected_lookup(name):
        calls['expected_lookup'] += 1
        return checked
    probe = SimpleNamespace(baseClass=native, lookupName=expected_lookup)
    monkeypatch.setattr(scan, '_lookup_sv_symbol', lambda compilation, symbol: probe)
    checks = [('method', 'f', index, 'int', f'parameter p{index}') for index in range(64)]
    checks.append(('method', 'f', None, 'int', 'return type'))
    scan._compare_signature_probes(None, [('p::A', 'probe', checks, None, [{'name': 'f'}])])
    assert calls == {'lookup': 1, 'arguments': 1, 'matching': 1, 'expected_lookup': 2}


def test_cached_matching_does_not_merge_distinct_enum_types(tmp_path):
    source = tmp_path / 'enums.sv'
    source.write_text('''package p;
      typedef enum bit [1:0] {A0, A1} E0;
      typedef enum bit [1:0] {B0, B1} E1;
      class A;
        function void first(input E0 value); endfunction
        function void second(input E1 value); endfunction
      endclass
    endpackage''')
    methods = [{'name': name, 'timing': 'function', 'return_type': 'void',
                'parameters': [{'name': 'value', 'type': {'sv': 'p::E0'}}]}
               for name in ('first', 'second')]
    with pytest.raises(bridge.SVXInheritanceError, match=r'p::A.second parameter value.*does not match'):
        scan.validate_sv_declarations([{'symbol': 'p::A', 'methods': methods}], [source])


def test_type_binding_cache_has_no_entry_limit():
    from test_call_execution_plan import spec
    metadata = []
    for width in range(1, 601):
        codec = svtypes.Bit[width]()
        metadata.append(spec(svtypes.Bit[width]) | {
            'sv': svtypes.sv_type_expression(codec), 'sv_packer': svtypes.sv_packer_expression(codec)})

    @bridge._type_binding_scope
    def collect():
        values = [bridge._type_binding(item, 'cache test', allow_void=False) for item in metadata]
        assert len(bridge._type_binding_cache.get()) == 600
        assert bridge._type_binding(metadata[-1], 'cache test', allow_void=False) is values[-1]
    collect()
    assert bridge._sv_type_syntax_error.cache_info().maxsize is None


def test_expected_type_cache_has_no_entry_limit(tmp_path, monkeypatch):
    from test_call_execution_plan import spec
    source = tmp_path / 'wide.sv'
    methods, declarations = [], []
    for width in range(1, 601):
        annotation = svtypes.Bit[width]
        codec = annotation()
        binding = spec(annotation) | {'sv': svtypes.sv_type_expression(codec),
                                    'sv_packer': svtypes.sv_packer_expression(codec)}
        methods.append(f'function bit [{width-1}:0] f{width}(input bit [{width-1}:0] v); return v; endfunction')
        declarations.append({'name': f'f{width}', 'parameters': [{'name': 'v', 'type': binding}],
                             'return_type': binding, 'timing': 'function'})
    source.write_text('package p; class A;\n' + '\n'.join(methods) + '\nendclass endpackage')
    calls = []
    original = bridge._type_binding

    def binding(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(bridge, '_type_binding', binding)
    scan.validate_sv_declarations([{'symbol': 'p::A', 'methods': declarations}], [source])
    assert len(calls) == 600


def test_expected_type_cache_includes_declared_named_types(tmp_path, monkeypatch):
    from io import StringIO
    from svx.cli import main
    from test_expected_type_preparation import named_source
    active = [False]
    calls = []
    original = scan._validate_member_types
    materialize = bridge._type_binding

    def validation(*args, **kwargs):
        active[0] = True
        try:
            return original(*args, **kwargs)
        finally:
            active[0] = False

    def binding(metadata, *args, **kwargs):
        if active[0]:
            calls.append(metadata)
        return materialize(metadata, *args, **kwargs)

    monkeypatch.setattr(scan, '_validate_member_types', validation)
    monkeypatch.setattr(bridge, '_type_binding', binding)
    source = tmp_path / 'named.sv'
    source.write_text(named_source(3))
    assert main(['export', '--sv-source', str(source), '--package', 'expected_types_pkg',
                 '--out', str(tmp_path / 'generated')], out=StringIO()) == 0
    assert len(calls) == len({id(item) for item in calls})
    import json
    keys = [json.dumps(item, sort_keys=True) for item in calls]
    assert len(keys) == len(set(keys))
