import os
import tomllib
from io import StringIO
from pathlib import Path

import svx
from svx.cli import main


def test_public_version_matches_project_metadata():
    metadata = tomllib.loads(Path("pyproject.toml").read_text())
    assert metadata["project"]["version"] == "0.1.0"
    assert svx.__version__ == metadata["project"]["version"]


def test_cli_uses_explicit_runtime_locations(monkeypatch, tmp_path):
    share = tmp_path / "share"
    share.mkdir()
    (share / "svx_pkg.sv").write_text("package svx_pkg; endpackage\n")
    lib = tmp_path / "lib"
    lib.mkdir()
    monkeypatch.setenv("SVX_SHARE_DIR", str(share))
    monkeypatch.setenv("SVX_LIB_DIR", str(lib))

    out = StringIO()
    assert main(["share"], out=out) == 0
    assert out.getvalue().strip() == str(share)

    out = StringIO()
    assert main(["libs"], out=out) == 0
    assert out.getvalue().strip() == str(lib / "libsvx")
