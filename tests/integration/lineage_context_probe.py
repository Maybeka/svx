"""Global manifest graph consistency and read-only generation failure probe."""

from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from svx.cli import main
from svx.errors import SVXInheritanceError
from svx.inheritance import _manifest_lineage_contexts, parse_manifest
from tests.integration.python_root_proxy_schema import probe_manifest_data
from tests.integration.sv_field_mirror_schema import manifest_data as baseline_manifest


def branch_manifest():
    data = probe_manifest_data()
    first = deepcopy(data["classes"][4])
    second = deepcopy(first)
    second["canonical_id"] = "sv://other_pkg/OtherGrandchild"
    second["symbol"] = "other_pkg::OtherGrandchild"
    for method in second["methods"]:
        method["canonical_id"] = second["canonical_id"] + "#" + method["name"]
    data["classes"] = [first, second]
    return data


def conflicting_branch(kind):
    data = branch_manifest()
    lineage = data["classes"][1]["base_lineage"]
    if kind == "member":
        lineage[1]["fields"][0]["name"] = "different_field"
    elif kind == "prefix":
        root = lineage[0]
        root["canonical_id"] = "py://tests/integration/python_root/OtherRoot"
        root["symbol"] = "tests.integration.python_root_proxy_test.OtherRoot"
        for method in root["methods"]:
            method["canonical_id"] = root["canonical_id"] + "#" + method["name"]
    elif kind == "root":
        del lineage[0]
    else:
        raise ValueError(kind)
    return data


def run_probe():
    model = parse_manifest(branch_manifest())
    contexts = _manifest_lineage_contexts(model)
    assert len(model.classes) == 2
    assert len(contexts[model.classes[0].base_lineage[1].canonical_id]) == 1
    with TemporaryDirectory(prefix="svx-lineage-context-") as directory:
        root = Path(directory)
        manifest = root / "manifest.json"
        python = root / "python"
        sv = root / "mirror.sv"
        artifact = root / "svx-artifacts.json"
        manifest.write_text(json.dumps(baseline_manifest()))
        arguments = ["inheritance-gen", "--manifest", str(manifest), "--python-out", str(python),
                     "--sv-out", str(sv), "--artifact-manifest", str(artifact)]
        assert main(arguments, out=StringIO()) == 0
        paths = [path for path in root.rglob("*") if path.is_file() and path != manifest]
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        for kind in ("member", "prefix", "root"):
            manifest.write_text(json.dumps(conflicting_branch(kind)))
            output = StringIO()
            try:
                main(arguments, out=output)
            except SVXInheritanceError as error:
                expected = "conflicting lineage declarations" if kind == "member" else "conflicting lineage ancestry"
                assert expected in str(error), str(error)
            else:
                raise AssertionError("conflicting manifest graph was accepted: " + kind)
            assert output.getvalue() == ""
            assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths} == before
            assert {path for path in root.rglob("*") if path.is_file() and path != manifest} == set(paths)
            print("LINEAGE_CONTEXT_" + kind.upper() + "_PASS", flush=True)
    print("LINEAGE_CONTEXT_PASS", flush=True)


if __name__ == "__main__":
    run_probe()
