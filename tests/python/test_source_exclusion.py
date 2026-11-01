import io
import json
from pathlib import Path

import pytest

from svx.cli import main
from svx.errors import SVXInheritanceError


@pytest.fixture
def project(tmp_path):
    api = tmp_path / 'api.sv'
    api.write_text('package api; class Driver; int count; endclass endpackage', encoding='utf-8')
    rtl = tmp_path / 'rtl.sv'
    rtl.write_text('module broken; this is deliberately invalid RTL; endmodule', encoding='utf-8')
    filelist = tmp_path / 'project.f'
    filelist.write_text('api.sv\nrtl.sv\n', encoding='utf-8')
    return api, rtl, filelist


def arguments(project):
    api, rtl, filelist = project
    return ['-f', str(filelist), '--sv-build-directory', str(api.parent),
            '--exclude-source', str(rtl)]


def test_inspection_reports_selected_and_excluded_in_original_order(project):
    api, rtl, _ = project
    output = io.StringIO()
    main(['compile-config', *arguments(project)], out=output)
    data = json.loads(output.getvalue())
    assert [Path(p).resolve() for p in data['sources']] == [api]
    assert [Path(p).resolve() for p in data['excluded_parse_inputs']] == [rtl]


def test_export_and_check_skip_only_explicit_root(project, tmp_path):
    pytest.importorskip('pyslang')
    _, rtl, _ = project
    output = io.StringIO()
    root = tmp_path / 'generated'
    argv = ['export', '--package', 'api', *arguments(project), '--out', str(root)]
    main(argv, out=output)
    assert 'Excluded explicit parse input:' in output.getvalue()
    provenance = json.loads((root / 'inheritance.json.svx-discovery.json').read_text(encoding='utf-8'))
    config = provenance['configuration']
    assert [Path(root, p).resolve() for p in config['sv_excluded_sources']] == [rtl]
    assert rtl not in [Path(root, p).resolve() for p in config['sv_dependencies']]
    # Original build inputs and their source order are not rewritten.
    assert [Path(root, p).resolve() for p in config['sv_build']['configuration']['sources']] == list(project[:2])
    rtl.write_text('module changed; also invalid; endmodule', encoding='utf-8')
    main([*argv, '--check'], out=io.StringIO())


@pytest.mark.parametrize('shared', [['--sv-compilation-unit'], []])
def test_shared_macro_units_reject_source_removal(project, shared):
    if not shared:
        project[2].write_text('-mfcu\napi.sv\nrtl.sv\n', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='shared unit'):
        main(['compile-config', *arguments(project), *shared], out=io.StringIO())


def test_unknown_and_all_sources_are_rejected(project):
    with pytest.raises(SVXInheritanceError, match='not an explicit parse input'):
        main(['compile-config', *arguments(project), '--exclude-source', 'not-an-input.sv'], out=io.StringIO())
    with pytest.raises(SVXInheritanceError, match='every SV parse input'):
        main(['compile-config', *arguments(project), '--exclude-source', str(project[0])], out=io.StringIO())


def test_excluded_source_is_still_protected_against_output_overwrite(project):
    original = project[1].read_bytes()
    with pytest.raises(SVXInheritanceError, match='input'):
        main(['compile-config', *arguments(project), '--out', str(project[1])], out=io.StringIO())
    assert project[1].read_bytes() == original


def test_exclusion_does_not_disable_include_dependencies(project, tmp_path):
    pytest.importorskip('pyslang')
    api, rtl, _ = project
    rtl.write_text('`define COUNT_TYPE int\n', encoding='utf-8')
    api.write_text('`include "rtl.sv"\npackage api; class Driver; `COUNT_TYPE count; endclass endpackage', encoding='utf-8')
    root = tmp_path / 'generated'
    main(['export', '--package', 'api', *arguments(project), '--out', str(root)], out=io.StringIO())
    record = json.loads((root / 'inheritance.json.svx-discovery.json').read_text(encoding='utf-8'))
    assert rtl in [Path(root, p).resolve() for p in record['configuration']['sv_dependencies']]
    rtl.write_text('`define COUNT_TYPE longint\n', encoding='utf-8')
    with pytest.raises((SVXInheritanceError, SystemExit), match='stale|changed'):
        main(['export', '--package', 'api', *arguments(project), '--out', str(root), '--check'], out=io.StringIO())


def test_excluding_required_base_does_not_fabricate_a_replacement(project, tmp_path):
    pytest.importorskip('pyslang')
    api, rtl, _ = project
    rtl.write_text('package bases; class Base; endclass endpackage', encoding='utf-8')
    api.write_text('package api; class Driver extends bases::Base; endclass endpackage', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='bases|Base|base'):
        main(['export', '--package', 'api', *arguments(project), '--out', str(tmp_path / 'generated')], out=io.StringIO())
    assert not (tmp_path / 'generated/inheritance.json').exists()


def test_excluded_only_edit_keeps_zero_parse_incremental_hit(project, tmp_path, monkeypatch):
    pytest.importorskip('pyslang')
    argv = ['export', '--package', 'api', *arguments(project), '--out', str(tmp_path / 'generated'), '--incremental']
    main(argv, out=io.StringIO())
    project[1].write_text('unrelated RTL changed, still not a parse input', encoding='utf-8')
    import svx.sv_scan as scan
    def forbidden(*args, **kwargs):
        pytest.fail('excluded-only change must not parse the selected API again')
    monkeypatch.setattr(scan, '_parse_source_batch', forbidden)
    stream = io.StringIO()
    main([*argv, '--check'], out=stream)
    assert 'reused verified export' in stream.getvalue()
