import io
import json
import os
from pathlib import Path

import pytest

from svx.cli import main
from svx.discovery_provenance import validate_discovery_provenance
from svx.errors import SVXInheritanceError
from svx.inheritance import load_manifest
from svx.source_selection import source_observations

pytest.importorskip('pyslang')


def discover(root):
    high, low = root / 'high', root / 'low'
    high.mkdir()
    low.mkdir()
    header = low / 'config.svh'
    header.write_text('`define INITIAL 1\n', encoding='utf-8')
    source = root / 'source.sv'
    source.write_text('''`include "config.svh"
package agent_pkg;
  class Agent;
    int value = `INITIAL;
    function new(); endfunction
    function int get(); return value; endfunction
  endclass
endpackage
''', encoding='utf-8')
    manifest = root / 'manifest.json'
    main(['inheritance-manifest', '--package', 'agent_pkg', '--sv-source', str(source),
          '-I', str(high), '-I', str(low), '--out', str(manifest)], out=io.StringIO())
    return manifest, source, header, high


def test_provenance_reads_each_sv_digest_once_with_fresh_selection_replay(tmp_path, monkeypatch):
    with source_observations():
        manifest, source, header, _ = discover(tmp_path)
        data = json.loads(manifest.read_text(encoding='utf-8'))
        counts = {source: 0, header: 0}
        original = Path.read_bytes
        def read(path):
            if path in counts:
                counts[path] += 1
            return original(path)
        monkeypatch.setattr(Path, 'read_bytes', read)
        validate_discovery_provenance(data, manifest)
        assert counts == {source: 1, header: 1}
        validate_discovery_provenance(data, manifest)
        assert counts == {source: 2, header: 2}


def test_replay_detects_same_size_header_change_with_restored_mtime(tmp_path):
    with source_observations():
        manifest, _, header, _ = discover(tmp_path)
        status = header.stat()
        header.write_text('`define INITIAL 2\n', encoding='utf-8')
        os.utime(header, ns=(status.st_atime_ns, status.st_mtime_ns))
        with pytest.raises(SVXInheritanceError, match='discovery source changed'):
            load_manifest(manifest)


def test_replay_rejects_new_higher_priority_header_even_with_identical_bytes(tmp_path):
    with source_observations():
        manifest, _, header, high = discover(tmp_path)
        (high / header.name).write_bytes(header.read_bytes())
        with pytest.raises(SVXInheritanceError, match='dependency selection changed'):
            load_manifest(manifest)


def test_without_existing_proof_changed_source_rejects_before_dependency_parse(tmp_path, monkeypatch):
    manifest, source, _, _ = discover(tmp_path)
    source.write_text(source.read_text(encoding='utf-8').replace('int value', 'int count'), encoding='utf-8')
    import svx.sv_source_options as options
    monkeypatch.setattr(options, '_source_dependencies', lambda *args, **kwargs: pytest.fail('stale source parsed'))
    with pytest.raises(SVXInheritanceError, match='discovery source changed'):
        load_manifest(manifest)
