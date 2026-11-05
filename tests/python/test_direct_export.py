import io
import json

import pytest

from svx.cli import main
from svx.errors import SVXInheritanceError
from test_direct_integrated_export import source


def generated_code(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and p.suffix in {'.py', '.sv', '.svh', '.f'}}


def export_args(tmp_path):
    pytest.importorskip('pyslang')
    source = tmp_path / 'driver.sv'
    source.write_text('''package direct_pkg;
      class Driver;
        int value;
        function new(int seed=3); value=seed; endfunction
        virtual function int status(); return value; endfunction
        task update(input int x, output int y); value=x; y=value; endtask
      endclass
    endpackage''', encoding='utf-8')
    return ['export', '--sv-source', str(source), '--package', 'direct_pkg']


def test_direct_export_uses_in_memory_manifest_without_audits(tmp_path, monkeypatch):
    import svx.cli as cli
    args = export_args(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail('ordinary export must not invoke the serialized/audited pipeline')
    for name in ('_fresh_declaration_entries', '_generation_inputs', '_manifest_input_fingerprints',
                 '_generated_artifact_text', 'load_manifest', 'enrich_virtual_interface_manifest',
                 '_sv_source_dependencies'):
        monkeypatch.setattr(cli, name, forbidden)
    output = tmp_path / 'direct'
    command = [*args, '--out', str(output)]
    stream = io.StringIO()
    assert main([*command, '--timings'], out=stream) == 0
    assert 'Discovery:' in stream.getvalue() and 'Generation:' in stream.getvalue()
    assert 'SV startup: svx_exports_pkg::initialize();' in stream.getvalue()
    assert (output / 'python/svx_bootstrap.py').is_file()
    assert 'discovery_provenance' not in json.loads((output / 'inheritance.json').read_text())
    assert not (output / 'artifacts.json').exists()
    assert not (output / 'inheritance.json.svx-discovery.json').exists()
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in output.rglob('*') if p.is_file()}
    assert main([*command, '--check'], out=io.StringIO()) == 0
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in output.rglob('*') if p.is_file()}
    mirror = output / 'mirrors.sv'
    mirror.write_text(mirror.read_text() + '// local repair\n')
    with pytest.raises((SVXInheritanceError, SystemExit), match='stale|manually edited'):
        main([*command, '--check'], out=io.StringIO())
    with pytest.raises(SVXInheritanceError, match='manual edits'):
        main(command, out=io.StringIO())
    assert main([*command, '--overwrite-generated'], out=io.StringIO()) == 0


@pytest.mark.parametrize('integrated', [False, True])
def test_direct_and_audited_exports_generate_identical_code(tmp_path, integrated):
    args = export_args(tmp_path)
    if integrated:
        args.append('--integrated')
    direct, audited = tmp_path / 'direct', tmp_path / 'audited'
    assert main([*args, '--out', str(direct)], out=io.StringIO()) == 0
    assert main([*args, '--out', str(audited), '--audit'], out=io.StringIO()) == 0
    assert generated_code(direct) == generated_code(audited)
    assert (audited / 'artifacts.json').is_file()
    assert main([*args, '--out', str(audited), '--audit', '--check'], out=io.StringIO()) == 0
    with pytest.raises(SVXInheritanceError, match='audited export records'):
        main([*args, '--out', str(audited)], out=io.StringIO())


@pytest.mark.parametrize('selector,target', [
    ('--package', 'p'), ('--class', 'p::Outer::Inner'),
    ('--type', 'p::Outer::Packet'), ('--constant', 'p::COUNT'), ('--callable', 'p::echo'),
])
@pytest.mark.parametrize('integrated', [False, True])
def test_direct_nested_types_and_callables_match_audited(source, tmp_path, selector, target, integrated):
    direct, audited = tmp_path / 'direct', tmp_path / 'audited'
    args = ['export', selector, target, '--sv-source', str(source), '-I', str(tmp_path)]
    if integrated:
        args.append('--integrated')
    assert main([*args, '--out', str(direct)], out=io.StringIO()) == 0
    assert main([*args, '--out', str(audited), '--audit'], out=io.StringIO()) == 0
    assert generated_code(direct) == generated_code(audited)
    assert main([*args, '--out', str(direct), '--check'], out=io.StringIO()) == 0


def test_filelist_only_direct_export_owns_one_analysis_scope(tmp_path, monkeypatch):
    import svx.sv_frontend as frontend
    args = export_args(tmp_path)
    filelist = tmp_path / 'files.f'
    filelist.write_text(args[2] + '\n', encoding='utf-8')
    states = []
    original = frontend.SourceAnalysis
    def record(*args, **kwargs):
        state = original(*args, **kwargs)
        states.append(state)
        return state
    monkeypatch.setattr(frontend, 'SourceAnalysis', record)
    output = tmp_path / 'filelist-output'
    assert main(['export', '-f', str(filelist), '--package', 'direct_pkg', '--out', str(output)],
                out=io.StringIO()) == 0
    assert len(states) == 1
    assert states[0].parse_batches == 1
    assert states[0].class_inventory_builds == 1
    assert states[0].class_inventory_reuses > 0


@pytest.mark.parametrize('mode', [[], ['--audit'], ['--incremental']])
def test_export_progress_is_live_without_symbol_import_list(tmp_path, monkeypatch, mode):
    import svx.cli as cli
    args = [*export_args(tmp_path), *mode, '--out', str(tmp_path / 'generated')]
    class Output(io.StringIO):
        flushes = 0
        def flush(self):
            self.flushes += 1
            super().flush()
    out = Output()
    original = cli.emit_python_mirrors
    def emit(manifest):
        assert 'Generating Python mirrors and contracts...' in out.getvalue()
        assert out.flushes > 0
        assert 'Writing generated outputs...' not in out.getvalue()
        return original(manifest)
    monkeypatch.setattr(cli, 'emit_python_mirrors', emit)
    assert main(args, out=out) == 0
    text = out.getvalue()
    steps = ['Reading project filelists', 'Discovering declarations', 'Generating Python',
             'Generating SV bridges', 'Preparing generated support', 'Validating output paths',
             'Writing generated outputs', 'Export complete.']
    positions = [text.index(step) for step in steps]
    assert positions == sorted(positions)
    assert not any(line.startswith(('from ', 'Type: ', 'Constant: ')) for line in text.splitlines())
    checked = io.StringIO()
    # The generation callback above observes the original stream only.
    monkeypatch.setattr(cli, 'emit_python_mirrors', original)
    assert main([*args, '--check'], out=checked) == 0
    assert 'Writing generated outputs...' not in checked.getvalue()
    assert 'Check complete.' in checked.getvalue()
    if mode == ['--incremental']:
        assert 'reused verified export' in checked.getvalue()
        assert 'Generating Python' not in checked.getvalue()
