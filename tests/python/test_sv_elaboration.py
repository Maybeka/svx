import io
import json

import pytest

from svx.cli import main
from svx.discovery_provenance import _configuration
from svx.errors import SVXInheritanceError
from svx.sv_frontend import elaborate_sources, source_elaboration

pytest.importorskip('pyslang')


def compilation(text):
    from pyslang.ast import Compilation
    from pyslang.syntax import SyntaxTree

    result = Compilation()
    result.addSyntaxTree(SyntaxTree.fromText(text))
    return result


def test_package_elaboration_omits_dut_and_keeps_original_package_semantics():
    text = '''package p;typedef bit[12:0] Word;
class Driver;Word value;endclass endpackage
module child;logic[31:0] data;endmodule
module dut;for(genvar i=0;i<1000;i++) begin:g child c();end endmodule'''
    ordinary = elaborate_sources(compilation(text))
    assert [item.name for item in ordinary.getRoot().topInstances] == ['dut']
    assert sum(item.kind.name == 'GenerateBlock'
               for item in ordinary.getRoot().topInstances[0].body.lookupName('g')) == 1000
    with source_elaboration('packages'):
        limited = elaborate_sources(compilation(text))
    assert [item.name for item in limited.getRoot().topInstances] == ['svx_export_analysis_root']
    assert limited.getPackage('p').lookupName('Driver').lookupName('value').type.bitWidth == 13
    assert len(limited.getSyntaxTrees()) == 2
    assert str(limited.getSyntaxTrees()[0].root) == str(ordinary.getSyntaxTrees()[0].root)
    assert not list(limited.getAllDiagnostics())


def test_internal_analysis_top_does_not_collide_or_leak_policy():
    text = 'module svx_export_analysis_root;endmodule module svx_export_analysis_root_;endmodule'
    with source_elaboration('packages'):
        limited = elaborate_sources(compilation(text))
        assert [item.name for item in limited.getRoot().topInstances] == ['svx_export_analysis_root__']
        with source_elaboration('all'):
            assert len(elaborate_sources(compilation(text)).getRoot().topInstances) == 2
    assert len(elaborate_sources(compilation(text)).getRoot().topInstances) == 2


def test_cli_policy_reaches_all_semantic_consumers_and_tracks_all_inputs(tmp_path, monkeypatch):
    import svx.sv_frontend as frontend
    import svx.sv_scan as scan

    include = tmp_path / 'config.svh'
    include.write_text('`define WIDTH 13\n', encoding='utf-8')
    source = tmp_path / 'design.sv'
    source.write_text('''`include "config.svh"
package p;typedef bit[`WIDTH-1:0] Word;
class Base;virtual function Word status();return 3;endfunction endclass
class Driver extends Base;endclass endpackage
module dut;for(genvar i=0;i<500;i++) begin:g logic[31:0] data;end endmodule''', encoding='utf-8')
    output = tmp_path / 'generated'
    observed = []

    def trace(original):
        result = elaborate_sources(original)
        observed.append([item.name for item in result.getRoot().topInstances])
        return result

    monkeypatch.setattr(frontend, 'elaborate_sources', trace)
    monkeypatch.setattr(scan, 'elaborate_sources', trace)
    args = ['export', '--package', 'p', '--sv-source', str(source), '-I', str(tmp_path),
            '--sv-elaboration', 'packages', '--out', str(output)]
    stream = io.StringIO()
    assert main(args, out=stream) == 0
    assert observed and all(names == ['svx_export_analysis_root'] for names in observed)
    assert 'retained explicit sources still preprocessed' in stream.getvalue()
    evidence = json.loads((output / 'inheritance.json.svx-discovery.json').read_text(encoding='utf-8'))
    assert evidence['configuration']['sv_elaboration'] == 'packages'
    assert {'../design.sv', '../config.svh'} <= {item['path'] for item in evidence['sources']}
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['generation_inputs']['sv_elaboration'] == 'packages'
    assert main(args + ['--check'], out=io.StringIO()) == 0
    # A DUT-only edit still invalidates evidence, even when its hierarchy is omitted.
    source.write_text(source.read_text(encoding='utf-8').replace('i<500', 'i<600'), encoding='utf-8')
    with pytest.raises(SystemExit, match='provenance is stale'):
        main(args + ['--check'], out=io.StringIO())


def test_package_mode_does_not_hide_dut_syntax_errors(tmp_path):
    source = tmp_path / 'bad.sv'
    source.write_text('package p;class A;endclass endpackage module dut;int = ;endmodule', encoding='utf-8')
    with pytest.raises(SVXInheritanceError):
        main(['export', '--class', 'p::A', '--sv-elaboration', 'packages',
              '--sv-source', str(source), '--out', str(tmp_path / 'generated')], out=io.StringIO())
    assert not (tmp_path / 'generated/inheritance.json').exists()


def test_package_mode_prunes_dut_library_requests_but_keeps_imports_and_vif(tmp_path):
    from svx.compile_config import import_compile_configuration
    from svx.sv_library_search import library_search
    from svx.sv_source_options import _source_dependencies

    library = tmp_path / 'lib'
    library.mkdir()
    source = tmp_path / 'top.sv'
    source.write_text('''package p;import base_pkg::*;
class Driver extends Base;virtual bus_if vif;endclass endpackage
module tb;import extra_pkg::*;dut u();endmodule''', encoding='utf-8')
    (library / 'base_pkg.sv').write_text('package base_pkg;class Base;int value;endclass endpackage', encoding='utf-8')
    (library / 'bus_if.sv').write_text('interface bus_if;logic ready;endinterface', encoding='utf-8')
    (library / 'extra_pkg.sv').write_text('package extra_pkg;class Unselected;endclass endpackage', encoding='utf-8')
    (library / 'dut.sv').write_text('module dut;leaf u();endmodule', encoding='utf-8')
    (library / 'leaf.sv').write_text('module leaf;endmodule', encoding='utf-8')
    filelist = tmp_path / 'files.f'
    filelist.write_text('-y lib +libext+.sv\ntop.sv', encoding='utf-8')
    config = import_compile_configuration({'directory': str(tmp_path), 'filelists': [str(filelist)]})
    with library_search(config), source_elaboration('packages'):
        limited = _source_dependencies(config.sources)
    assert limited == {source, library / 'base_pkg.sv', library / 'bus_if.sv', library / 'extra_pkg.sv'}
    with library_search(config):
        assert _source_dependencies(config.sources) == limited | {library / 'dut.sv', library / 'leaf.sv'}
    output = tmp_path / 'generated'
    args = ['export', '--class', 'p::Driver', '-f', str(filelist),
            '--sv-build-directory', str(tmp_path), '--sv-elaboration', 'packages', '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    # Validation outside the command must replay the recorded library policy.
    from svx.inheritance import load_manifest
    assert load_manifest(output / 'inheritance.json').classes[0].symbol == 'p::Driver'
    assert main(args + ['--check'], out=io.StringIO()) == 0
    (library / 'dut.sv').write_text('changed unused DUT library payload !', encoding='utf-8')
    assert main(args + ['--check'], out=io.StringIO()) == 0


def test_shared_syntax_does_not_conflate_library_loading_modes(tmp_path):
    from svx.compile_config import CompileConfiguration
    from svx.sv_frontend import source_analysis
    from svx.sv_library_search import library_search
    from svx.sv_scan import _parse_sources, _pyslang

    source = tmp_path / 'top.sv'
    source.write_text('module top;leaf u();endmodule', encoding='utf-8')
    (tmp_path / 'leaf.sv').write_text('module leaf;endmodule', encoding='utf-8')
    config = CompileConfiguration([source], [], {}, [], [], library_dirs=[tmp_path], library_extensions=['.sv'])
    with library_search(config), source_analysis() as analysis:
        with source_elaboration('packages'):
            assert len(tuple(_parse_sources(_pyslang(), [source]))) == 1
        assert len(tuple(_parse_sources(_pyslang(), [source]))) == 2
        assert analysis.parse_batches == 2


def test_package_mode_preserves_library_precedence_and_detects_new_candidate(tmp_path):
    (tmp_path / 'first').mkdir()
    (tmp_path / 'second').mkdir()
    source = tmp_path / 'top.sv'
    source.write_text('package p;class Driver extends base_pkg::Base;endclass endpackage', encoding='utf-8')
    second = tmp_path / 'second/base_pkg.sv'
    second.write_text('package base_pkg;class Base;bit[13:0] data;endclass endpackage', encoding='utf-8')
    filelist = tmp_path / 'files.f'
    filelist.write_text('-y first -y second +libext+.sv\ntop.sv', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'p::Driver', '-f', str(filelist),
            '--sv-build-directory', str(tmp_path), '--sv-elaboration', 'packages', '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    before = (output / 'inheritance.json').read_bytes()
    (tmp_path / 'first/base_pkg.sv').write_text(
        'package base_pkg;class Base;bit[7:0] data;endclass endpackage', encoding='utf-8')
    with pytest.raises(SystemExit, match='stale'):
        main(args + ['--check'], out=io.StringIO())
    assert (output / 'inheritance.json').read_bytes() == before


@pytest.mark.parametrize('mode', [None, [], {}, 1, 'unknown'])
def test_invalid_provenance_elaboration_mode_is_rejected(mode):
    assert not _configuration({'sv_elaboration': mode})
