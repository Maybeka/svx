from pathlib import Path

import pytest

from svx.declarations import manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.cli import main

pytest.importorskip('pyslang')


def source(tmp_path: Path, count=15):
    path = tmp_path / 'errors.sv'
    path.write_text('package p;\n' + '\n'.join(
        f'import "DPI-C" function void f{i:02}(output int values[]);'
        for i in range(count)) + '\nendpackage\n', encoding='utf-8')
    return path


@pytest.mark.parametrize('limit', [1, 3, 10, 20])
def test_discovery_error_limit(tmp_path, limit):
    with pytest.raises(SVXInheritanceError) as caught:
        manifest_from_declarations(sv_source_files=[source(tmp_path)],
                                   sv_package_targets=['p'], max_errors=limit)
    message = str(caught.value)
    assert message.count('output DPI open array cannot') == min(limit, 15)
    assert 'p::f00.values' in message
    assert f'p::f{min(limit, 15)-1:02}.values' in message
    if limit <= 15:
        assert f'error limit {limit} reached' in message
        assert 'discovery stopped early' in message
        assert 'further errors may remain' in message
    else:
        assert 'stopped early' not in message


def test_default_limit_and_collector_reset(tmp_path):
    path = source(tmp_path)
    with pytest.raises(SVXInheritanceError) as caught:
        manifest_from_declarations(sv_source_files=[path], sv_package_targets=['p'])
    assert str(caught.value).count('output DPI open array cannot') == 10
    path.write_text('package p; function int f(); return 1; endfunction endpackage\n', encoding='utf-8')
    assert len(manifest_from_declarations(sv_source_files=[path], sv_package_targets=['p']).callables) == 1


@pytest.mark.parametrize('limit', [0, -1, True, '3'])
def test_invalid_error_limit(tmp_path, limit):
    with pytest.raises(SVXInheritanceError, match='max_errors must be a positive integer'):
        manifest_from_declarations(sv_source_files=[source(tmp_path)], sv_package_targets=['p'], max_errors=limit)


def test_multiple_class_members_are_reported(tmp_path):
    path = tmp_path / 'fields.sv'
    path.write_text('package p; class A; static int first; static int second; '
                    'function void method(ref int third); endfunction endclass endpackage\n', encoding='utf-8')
    with pytest.raises(SVXInheritanceError) as caught:
        manifest_from_declarations(sv_source_files=[path], sv_class_targets=['p::A'])
    assert all(name in str(caught.value) for name in ('p::A.first', 'p::A.second', 'p::A.method.third'))


def test_multiple_parameters_of_one_callable_are_reported(tmp_path):
    path = tmp_path / 'parameters.sv'
    path.write_text('package p; import "DPI-C" function void f(output int first[], output int second[]); endpackage\n', encoding='utf-8')
    with pytest.raises(SVXInheritanceError) as caught:
        manifest_from_declarations(sv_source_files=[path], sv_package_targets=['p'])
    assert 'p::f.first' in str(caught.value) and 'p::f.second' in str(caught.value)


def test_cli_limit_preserves_existing_output(tmp_path):
    path = source(tmp_path)
    output = tmp_path / 'generated'
    output.mkdir()
    sentinel = output / 'mirrors.sv'
    sentinel.write_text('// existing user code\n', encoding='utf-8')
    with pytest.raises(SVXInheritanceError) as caught:
        main(['export', '--sv-source', str(path), '--package', 'p', '--max-errors', '3', '--out', str(output)])
    assert str(caught.value).count('output DPI open array cannot') == 3
    assert sentinel.read_text(encoding='utf-8') == '// existing user code\n'
    assert sorted(p.name for p in output.iterdir()) == ['mirrors.sv']
