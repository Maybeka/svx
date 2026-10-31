from types import SimpleNamespace

import pytest

from svx.source_selection import _observations, source_observations
from svx.sv_library_search import library_search
from svx.sv_source_options import _source_dependencies

pytest.importorskip('pyslang')


def test_dependency_reuse_checks_bytes_and_expires_between_commands(tmp_path, monkeypatch):
    import svx.sv_scan as scan

    source, header = tmp_path / 'source.sv', tmp_path / 'fields.svh'
    source.write_text('package p; class C; `include "fields.svh"\nendclass endpackage')
    header.write_text('int first;\n')
    original = scan._parse_source_batch
    calls = []
    def observed(*args, **kwargs):
        calls.append(1)
        yield from original(*args, **kwargs)
    monkeypatch.setattr(scan, '_parse_source_batch', observed)
    with source_observations() as state:
        assert _source_dependencies([source]) == {source, header}
        with source_observations() as nested:
            assert nested is state
            assert _source_dependencies([source]) == {source, header}
        assert len(calls) == 1 and state.reuses == 1
        header.write_text('int other;\n')
        assert _source_dependencies([source]) == {source, header}
        assert len(calls) == 2 and state.captures == 2
    assert _observations.get() is None
    with source_observations():
        _source_dependencies([source])
    assert len(calls) == 3


def test_dependency_reuse_replays_preferred_include_selection(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    source = tmp_path / 'source.sv'
    source.write_text('package p; `include "value.svh"\nendpackage')
    (second / 'value.svh').write_text('typedef int Value;\n')
    with source_observations() as state:
        assert _source_dependencies([source], include_dirs=[first, second]) == {source, second / 'value.svh'}
        (first / 'value.svh').write_text('typedef int Value;\n')
        assert _source_dependencies([source], include_dirs=[first, second]) == {source, first / 'value.svh'}
        assert state.captures == 2 and state.reuses == 0


def test_dependency_reuse_replays_preferred_library_selection(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    source = tmp_path / 'source.sv'
    source.write_text('package p; import base_pkg::*; endpackage')
    text = 'package base_pkg; typedef int Value; endpackage\n'
    (second / 'base_pkg.sv').write_text(text)
    config = SimpleNamespace(library_dirs=(first, second), library_extensions=('.sv',), top_modules=())
    with library_search(config), source_observations() as state:
        assert _source_dependencies([source]) == {source, second / 'base_pkg.sv'}
        (first / 'base_pkg.sv').write_text(text)
        assert _source_dependencies([source]) == {source, first / 'base_pkg.sv'}
        assert state.captures == 2 and state.reuses == 0


def test_observation_scope_is_cleaned_after_failure():
    with pytest.raises(RuntimeError):
        with source_observations():
            raise RuntimeError('stop')
    assert _observations.get() is None


def test_reuse_separates_macros_and_accepts_one_shot_options(tmp_path):
    source = tmp_path / 'source.sv'
    first, second = tmp_path / 'first.svh', tmp_path / 'second.svh'
    source.write_text('package p;\n`ifdef FIRST\n`include "first.svh"\n'
                      '`else\n`include "second.svh"\n`endif\nendpackage')
    first.write_text('typedef int Value;\n')
    second.write_text('typedef bit Value;\n')
    with source_observations() as state:
        assert _source_dependencies([source], predefines={'FIRST': None},
            include_dirs=iter([tmp_path]), undefines=iter(())) == {source, first}
        assert _source_dependencies([source]) == {source, second}
        assert state.captures == 2
        with pytest.raises(TypeError, match='sequence of names'):
            _source_dependencies([source], undefines='FIRST')


def test_unreplayable_dependency_observations_keep_original_parser(tmp_path, monkeypatch):
    import svx.source_selection as selection
    import svx.sv_scan as scan

    source = tmp_path / 'source.sv'
    source.write_text('package p; endpackage')
    original = scan._parse_source_batch
    calls = []
    def observed(*args, **kwargs):
        calls.append(1)
        yield from original(*args, **kwargs)
    monkeypatch.setattr(scan, '_parse_source_batch', observed)
    record = selection.record_source_trees
    def unreplayable(trees):
        record(trees)
        selection._recording.get()['replayable'] = False
    monkeypatch.setattr(selection, 'record_source_trees', unreplayable)
    with source_observations() as state:
        assert _source_dependencies([source]) == {source}
        assert _source_dependencies([source]) == {source}
        assert state.captures == 2 and state.reuses == 0 and len(calls) == 2
        assert selection.capture_selection([source]) is None
        assert len(calls) == 3


def test_changed_capture_still_reparses_instead_of_using_stale_dependencies(tmp_path, monkeypatch):
    import svx.source_selection as selection
    import svx.sv_scan as scan

    source = tmp_path / 'source.sv'
    first, second = tmp_path / 'first.svh', tmp_path / 'second.svh'
    first.write_text('typedef int Value;\n')
    second.write_text('typedef bit Value;\n')
    source.write_text('package p; `include "first.svh"\nendpackage')
    original = scan._parse_source_batch
    calls = []
    def observed(*args, **kwargs):
        calls.append(1)
        yield from original(*args, **kwargs)
    validate = selection.validate_selection
    def mutate(proof, context):
        source.write_text('package p; `include "second.svh"\nendpackage')
        return validate(proof, context)
    monkeypatch.setattr(scan, '_parse_source_batch', observed)
    monkeypatch.setattr(selection, 'validate_selection', mutate)
    with source_observations() as state:
        assert _source_dependencies([source]) == {source, second}
        assert len(calls) == 2 and not state.proofs


def test_macro_expanded_include_uses_each_fresh_parse_once(tmp_path, monkeypatch):
    import svx.source_selection as selection
    import svx.sv_scan as scan

    source, header = tmp_path / 'source.sv', tmp_path / 'value.svh'
    source.write_text('`define LOAD_TYPES `include "value.svh"\n'
                      'package p;\n`LOAD_TYPES\nendpackage\n')
    header.write_text('typedef int Value;\n')
    original = scan._parse_source_batch
    calls = []
    def observed(*args, **kwargs):
        calls.append(1)
        yield from original(*args, **kwargs)
    monkeypatch.setattr(scan, '_parse_source_batch', observed)
    assert selection.capture_selection([source]) is None
    with source_observations() as state:
        assert _source_dependencies([source]) == {source, header}
        header.write_text('typedef bit Value;\n')
        assert _source_dependencies([source]) == {source, header}
        assert len(calls) == 3 and state.captures == 2 and state.reuses == 0


def test_parser_include_directory_follows_symlink_before_parent_component(tmp_path):
    project, base, target = (tmp_path / name for name in ('project', 'base', 'target'))
    for directory in (project, base, target / 'nested'):
        directory.mkdir(parents=True)
    source = project / 'source.sv'
    source.write_text('package p; `include "value.svh"\nendpackage')
    (base / 'value.svh').write_text('typedef bit Value;\n')
    (target / 'value.svh').write_text('typedef int Value;\n')
    link = base / 'link'
    try:
        link.symlink_to(target / 'nested', target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('directory symlinks unavailable')
    spelled = link / '..'
    assert spelled.resolve() == target
    assert _source_dependencies([source], include_dirs=[spelled]) == {source, target / 'value.svh'}
    with source_observations() as state:
        assert _source_dependencies([source], include_dirs=[target]) == {source, target / 'value.svh'}
        assert _source_dependencies([source], include_dirs=[spelled]) == {source, target / 'value.svh'}
        assert state.captures == 1 and state.reuses == 1


def test_equivalent_include_spelling_reuses_proof_without_reordering_inputs(tmp_path):
    from svx.source_selection import selection_context

    project, first, second = (tmp_path / name for name in ('project', 'first', 'second'))
    for directory in (project, first / 'nested', second):
        directory.mkdir(parents=True)
    source = project / 'source.sv'
    source.write_text('package p; `include "value.svh"\nendpackage')
    for directory in (first, second):
        (directory / 'value.svh').write_text('typedef int Value;\n')
    spelled = [first / 'nested' / '..', second, first]
    original = list(spelled)
    canonical = [first, second, first]
    assert selection_context([source], include_dirs=spelled)['include_dirs'] == list(map(str, canonical))
    with source_observations() as state:
        assert _source_dependencies([source], include_dirs=spelled) == {source, first / 'value.svh'}
        assert _source_dependencies([source], include_dirs=canonical) == {source, first / 'value.svh'}
        assert state.captures == 1 and state.reuses == 1
        assert _source_dependencies([source], include_dirs=[second, first, first]) == {source, second / 'value.svh'}
        assert state.captures == 2
    assert spelled == original


def test_retargeted_include_directory_does_not_reuse_old_identity(tmp_path):
    project, first, second = (tmp_path / name for name in ('project', 'first', 'second'))
    for directory in (project, first, second):
        directory.mkdir()
    source = project / 'source.sv'
    source.write_text('package p; `include "value.svh"\nendpackage')
    for directory in (first, second):
        (directory / 'value.svh').write_text('typedef int Value;\n')
    alias = tmp_path / 'headers'
    try:
        alias.symlink_to(first, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('directory symlinks unavailable')
    with source_observations() as state:
        assert _source_dependencies([source], include_dirs=[alias]) == {source, first / 'value.svh'}
        alias.unlink()
        alias.symlink_to(second, target_is_directory=True)
        assert _source_dependencies([source], include_dirs=[alias]) == {source, second / 'value.svh'}
        assert state.captures == 2 and state.reuses == 0


def test_missing_include_prefix_is_not_collapsed_to_existing_directory(tmp_path):
    from svx.source_selection import selection_context

    target = tmp_path / 'target'
    target.mkdir()
    missing = tmp_path / 'missing' / '..' / 'target'
    assert not (tmp_path / 'missing').exists()
    assert selection_context([], include_dirs=[missing])['include_dirs'] == [str(missing.absolute())]
    assert selection_context([], include_dirs=[missing]) != selection_context([], include_dirs=[target])
