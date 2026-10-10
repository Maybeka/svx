"""The cookbook project's source discovery and read-only incremental gate."""

import ast
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_register_lab_discovery_selects_targets_and_checks_missing_output(tmp_path):
    manifest = tmp_path / "inheritance.json"
    sources = ["--sv-source", "examples/register_lab/register_if.sv",
               "--sv-source", "examples/register_lab/policy_types.sv"]

    def run(arguments, *, success=True):
        result = subprocess.run([sys.executable, "-m", "svx", *arguments],
                                cwd=ROOT, text=True, capture_output=True)
        if success:
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            assert result.returncode != 0, result.stdout + result.stderr
        return result

    discovery = ["inheritance-manifest", "--python-module",
                 "examples.register_lab.extensions", *sources, "--out", str(manifest)]
    run(discovery)
    targets = json.loads(manifest.read_text())["classes"]
    assert {target["symbol"] for target in targets} == {
        "examples.register_lab.extensions.PythonPolicy",
        "examples.register_lab.extensions.Checker",
    }
    run([*discovery, "--check"])
    output = tmp_path / "inheritance.sv"
    artifact = tmp_path / "artifacts.json"
    generation = ["inheritance-gen", "--manifest", str(manifest), *sources,
                  "--python-out", str(tmp_path / "python"), "--sv-out", str(output),
                  "--artifact-manifest", str(artifact)]
    run(generation)
    mirror = tmp_path / "python/svx_mirror/register_policy_pkg.py"
    classes = {node.name for node in ast.parse(mirror.read_text()).body
               if isinstance(node, ast.ClassDef)}
    assert classes == {"RegisterPolicy"}, "PacketTag is opaque, not another generated target"
    run([*generation, "--check"])
    output.unlink()
    inventory_before = artifact.read_bytes()
    failed = run([*generation, "--check"], success=False)
    assert "stale" in (failed.stdout + failed.stderr).lower()
    assert not output.exists(), "--check must not repair files"
    assert artifact.read_bytes() == inventory_before
    run(generation)
    run([*generation, "--check"])
