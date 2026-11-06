from contextlib import contextmanager
from io import StringIO

import svtypes

from svx import inheritance as bridge
from svx.cli import main


def named_source(count=3):
    lines = ['package expected_types_pkg;']
    for index in range(count):
        lines += [f'typedef enum bit [1:0] {{Idle{index}=0, Run{index}=1}} State{index};',
                  f'typedef struct packed {{State{index} state; bit [7:0] data;}} Packet{index};']
    for index in range(count):
        lines += [f'class Driver{index};', f'State{index} first[3], second[2];',
                  f'Packet{index} packet;',
                  f'function State{index} echo(input State{index} value); return value; endfunction',
                  f'function void consume(input State{index} values[$], output Packet{index} result);',
                  "result = '0;", 'endfunction', 'endclass']
    return '\n'.join([*lines, 'endpackage', ''])


def test_expected_types_build_original_named_view_once(tmp_path, monkeypatch):
    import svx.sv_scan as scan
    import svx.value_exports as values
    active = [False]
    original_views = []
    validate = scan._validate_member_types
    modules = values.value_modules

    def validation(*args, **kwargs):
        active[0] = True
        try:
            return validate(*args, **kwargs)
        finally:
            active[0] = False

    @contextmanager
    def views(declarations=(), *, codegen=None):
        if active[0] and codegen is False:
            original_views.append(tuple(declarations))
        with modules(declarations, codegen=codegen) as value:
            yield value

    monkeypatch.setattr(scan, '_validate_member_types', validation)
    monkeypatch.setattr(values, 'value_modules', views)
    source = tmp_path / 'types.sv'
    source.write_text(named_source(), encoding='utf-8')
    args = ['export', '--sv-source', str(source), '--package', 'expected_types_pkg',
            '--out', str(tmp_path / 'generated')]
    assert main(args, out=StringIO()) == 0
    assert len(original_views) == 1
    original_views.clear()
    assert main([*args, '--check'], out=StringIO()) == 0
    assert len(original_views) == 1  # New command, fresh source/alias validation.


def test_collection_typedef_can_reuse_prepared_codec(monkeypatch):
    from test_call_execution_plan import spec
    annotation = svtypes.DynArray[svtypes.Int]
    codec = svtypes.materialize_type_spec(annotation, location='test collection')
    metadata = spec(annotation) | {'sv': svtypes.sv_type_expression(codec),
                                   'sv_packer': svtypes.sv_packer_expression(codec)}
    binding = bridge._type_binding(metadata, 'test', allow_void=False)
    expected = bridge._sv_collection_typedef(binding)
    assert expected is not None

    def forbidden(*args):
        raise AssertionError('collection type rebuilt an already prepared codec')

    monkeypatch.setattr(bridge, '_codec_from_spec', forbidden)
    assert bridge._sv_collection_typedef(binding, codec=codec) == expected
