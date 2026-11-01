import io
from dataclasses import replace
from pathlib import Path

import pytest

from svx.cli import main
from svx.inheritance import _handle_adapter_stem, _manifest_handle_bindings, load_manifest


@pytest.mark.parametrize('integrated', [False, True])
def test_distinct_package_handle_types_do_not_share_an_adapter_name(tmp_path, integrated, monkeypatch):
    pytest.importorskip('pyslang')
    source = Path(__file__).resolve().parents[1] / 'integration/handle_name_collision.sv'
    output = tmp_path / 'generated'
    args = ['export', '--package', 'collision_api', '--sv-source', str(source), '--out', str(output)]
    if integrated:
        args.append('--integrated')
    main(args, out=io.StringIO())
    manifest = load_manifest(output / 'inheritance.json')
    bindings = _manifest_handle_bindings(manifest)
    names = [_handle_adapter_stem(binding) for binding in bindings]
    assert len(set(names)) == len(names)
    assert len(bindings) == 4
    assert {binding.target_type_name for binding in bindings} == {'sv://a_b/C', 'sv://a/b_C'}
    assert [target.symbol for target in manifest.classes] == ['collision_api::Owner']
    # Semantic collection enumeration must never depend on a codegen alias.
    import svx.inheritance as inheritance
    with monkeypatch.context() as context:
        context.setattr(inheritance, '_handle_adapter_name', lambda binding: 'same_alias')
        assert _manifest_handle_bindings(manifest) == bindings
    main([*args, '--check'], out=io.StringIO())


def test_target_name_escaping_is_injective_and_legal():
    from svx.inheritance import HandleBinding
    import re
    characters = 'aAzZ09_:/-.[]%+$~'
    targets = [f'sv://p/{left}{right}' for left in characters for right in characters]
    bindings = [HandleBinding(kind='sv_class', target_type_name=target, sv_type='p::Item')
                for target in targets]
    names = [_handle_adapter_stem(binding) for binding in bindings]
    assert len(set(names)) == len(targets)
    assert all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) for name in names)
    # Literal escape-looking source text must not alias an escaped character.
    original = bindings[0]
    assert _handle_adapter_stem(replace(original, target_type_name='sv://p/a_b')) != _handle_adapter_stem(
        replace(original, target_type_name='sv://p/a/ub'))
