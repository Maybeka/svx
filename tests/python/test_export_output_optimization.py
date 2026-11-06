from collections import Counter
from pathlib import Path

import pytest

from svx.cli import _protect_generation_inputs
from svx.errors import SVXInheritanceError


@pytest.mark.parametrize('alias', ['same', 'symlink', 'hardlink'])
def test_input_protection_rejects_file_aliases(tmp_path, alias):
    source = tmp_path / 'source.sv'
    source.write_text('input')
    target = tmp_path / 'generated.sv'
    if alias == 'same':
        target = source
    elif alias == 'symlink':
        target.symlink_to(source)
    else:
        target.hardlink_to(source)
    with pytest.raises(SVXInheritanceError, match='input source'):
        _protect_generation_inputs([target], {source.resolve()})


def test_input_protection_checks_nonexistent_source_path(tmp_path):
    target = tmp_path / 'missing.sv'
    with pytest.raises(SVXInheritanceError, match='input source'):
        _protect_generation_inputs([target], {target})


def test_input_identity_index_is_linear_and_call_local(tmp_path, monkeypatch):
    sources = [tmp_path / f'input{i}.sv' for i in range(12)]
    targets = [tmp_path / f'output{i}.sv' for i in range(8)]
    for path in [*sources, *targets]:
        path.write_text('content')
    counts = Counter()
    original = Path.stat

    def stat(path, *args, **kwargs):
        counts[path] += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', stat)
    _protect_generation_inputs(targets, sources)
    assert all(counts[path] == 1 for path in sources)
    assert all(counts[path] <= 2 for path in targets)  # resolve may also stat.
    targets[0].unlink()
    targets[0].hardlink_to(sources[0])
    with pytest.raises(SVXInheritanceError, match='input source'):
        _protect_generation_inputs(targets, sources)


def test_fresh_outputs_do_not_probe_input_identities(tmp_path, monkeypatch):
    source = tmp_path / 'input.sv'
    source.write_text('source')
    original = Path.stat

    def stat(path, *args, **kwargs):
        assert path != source
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', stat)
    _protect_generation_inputs([tmp_path / f'new{i}.sv' for i in range(10)], [source])


def test_startup_collector_matches_generated_syntax(tmp_path, monkeypatch):
    import io
    import svx.cli as cli
    from pyslang import SourceManager
    from svx.sv_scan import _pyslang
    from svx.source_layout import _startup_registrations

    source = tmp_path / 'source.sv'
    source.write_text('''package startup_pkg;
      function int echo(int x); return x; endfunction
      class Driver;
        function new(); endfunction
        virtual function int status(); return 3; endfunction
        static function int count(); return 4; endfunction
      endclass
    endpackage''')
    import svx.source_layout as layout
    original = layout.emit_sv_mirrors
    seen = []

    def emit(manifest, *, startup_registrations):
        bridge = original(manifest, startup_registrations=startup_registrations)
        manager = SourceManager()
        manager.addUserDirectories(str(cli.sv_dir().parent))
        tree = _pyslang().SyntaxTree.fromText(bridge, manager)
        expected = [item for package in tree.root.members
                    if str(package.kind) == 'SyntaxKind.PackageDeclaration'
                    for item in _startup_registrations(package)]
        assert startup_registrations == expected
        assert len(expected) >= 3  # package function, static dispatcher, constructor.
        seen.extend(expected)
        return bridge

    monkeypatch.setattr(layout, 'emit_sv_mirrors', emit)
    assert cli.main(['export', '--sv-source', str(source), '--package', 'startup_pkg',
                     '--out', str(tmp_path / 'export')], out=io.StringIO()) == 0
    assert seen
