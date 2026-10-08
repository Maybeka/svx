"""Separate-package layout preflight and output-preservation regression."""

from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from svx.cli import main
from svx.errors import SVXInheritanceError
from svx.inheritance import (
    emit_python_mirrors, emit_sv_mirrors, emit_sv_mirror_stages,
    parse_manifest, projection_plan,
)
from tests.integration.sv_field_mirror_schema import manifest_data as baseline_manifest


def cyclic_layout(kind):
    path = Path(__file__).with_name("alternating_chain_manifest.json")
    data = json.loads(path.read_text())
    target = data["classes"][0]
    if kind == "sv_package":
        target["base_lineage"][2]["symbol"] = "chain_pkg::C"
        namespace = "chain_pkg"
    elif kind == "python_module":
        target["base_lineage"][1]["symbol"] = "checks.shared.B"
        target["symbol"] = "checks.shared.D"
        descendant = {
            "canonical_id": "sv://last_pkg/E", "language": "sv",
            "symbol": "last_pkg::E", "methods": [],
            "constructor": {"initiator": "python", "parameters": []},
            "base_lineage": deepcopy(target["base_lineage"]),
        }
        portion = deepcopy(target)
        del portion["base_lineage"]
        descendant["base_lineage"].append(portion)
        data["classes"] = [descendant]
        namespace = "svx_proxy_shared"
    else:
        raise ValueError(kind)
    return data, namespace


def check_layout(kind):
    data, namespace = cyclic_layout(kind)
    model = parse_manifest(data)
    plan = projection_plan(model.classes[0])
    assert len(plan.lineage) == (4 if kind == "sv_package" else 5)
    for emitter in (emit_python_mirrors, emit_sv_mirrors, emit_sv_mirror_stages):
        try:
            emitter(model)
        except SVXInheritanceError as error:
            message = str(error)
            assert "declaration cycle" in message, message
            assert namespace in message, message
            assert model.classes[0].canonical_id in message, message
            assert "logical lineage is valid" in message, message
        else:
            raise AssertionError("cyclic package layout emitted: " + kind)
    return data


def run_probe():
    with TemporaryDirectory(prefix="svx-package-layout-") as directory:
        root = Path(directory)
        manifest = root / "manifest.json"
        arguments = [
            "inheritance-gen", "--manifest", str(manifest),
            "--python-out", str(root / "python"),
            "--sv-stage-dir", str(root / "stages"),
            "--artifact-manifest", str(root / "artifacts.json"),
        ]
        manifest.write_text(json.dumps(baseline_manifest()))
        assert main(arguments, out=StringIO()) == 0

        def snapshot():
            return {
                path.relative_to(root): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in root.rglob("*") if path.is_file() and path != manifest
            }

        before = snapshot()
        assert before
        for kind in ("sv_package", "python_module"):
            manifest.write_text(json.dumps(check_layout(kind)))
            output = StringIO()
            try:
                main(arguments, out=output)
            except SVXInheritanceError as error:
                assert "declaration cycle" in str(error), str(error)
            else:
                raise AssertionError("CLI accepted cyclic package layout: " + kind)
            assert output.getvalue() == ""
            assert snapshot() == before
            print("PACKAGE_LAYOUT_" + kind.upper() + "_PASS", flush=True)
    print("PACKAGE_LAYOUT_PRESERVATION_PASS", flush=True)


if __name__ == "__main__":
    run_probe()
