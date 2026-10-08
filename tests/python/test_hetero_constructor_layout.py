from pathlib import Path

from tests.integration.hetero_constructor_schema import emit_sources


def test_heterogeneous_source_construction_preserves_natural_super_calls():
    path = Path('tests/integration/hetero_constructor_source.sv')
    original = path.read_bytes()
    manifest, python, sv = emit_sources()
    target = manifest.classes[0]
    assert len(manifest.classes) == 1
    assert [len(source.constructor.parameters) for source in (*target.base_lineage, target)] == [1, 2, 2, 0]
    source = sv[Path('source.sv')]
    assert 'super.new(child_seed + 10);' in source
    assert 'super.new(7, "abc");' in source
    assert path.read_bytes() == original
    assert 'super.new(child_seed, label);' in source
    assert 'svx-natural-constructor:' in source
    assert '::argument_child_seed(' in source and '::argument_label(' in source
    assert '::resume(this.__svx_remote_object_id)' in source
    child = next(text for key, text in python.items() if key.as_posix().endswith('hetero_child_pkg.py'))
    assert "'child_seed'" in child and "'label'" in child
    assert "_validate_staged_base_constructor" in child
