import os
import tomllib
from io import StringIO
from pathlib import Path

import svx
from svx.cli import main


def test_public_version_matches_project_metadata():
    metadata = tomllib.loads(Path("pyproject.toml").read_text())
    assert metadata["project"]["version"] == "1.0.0"
    assert svx.__version__ == metadata["project"]["version"]
    assert metadata["project"]["dependencies"] == ["svtypes>=1.2.0,<2.0.0"]
    release_contract = Path("docs/RELEASE_1.0.0.md").read_text()
    assert "| SvTypes | `>=1.2.0,<2.0.0` |" in release_contract
    assert "-DSVX_ENABLE_SANITIZERS=ON" in release_contract
    requirements = Path("docs/SVX_1_0_REQUIRED_FEATURES.md").read_text()
    specification = Path("docs/SVX_SPEC.md").read_text()
    assert "RemoteRef(target_type_name)" in requirements
    assert "RemoteRef(target_type_name)" in specification
    assert "RemoteRef(target_type_id)" not in requirements
    assert "RemoteRef(target_type_id)" not in specification
    assert 'project(svx VERSION 1.0.0 LANGUAGES CXX)' in Path("CMakeLists.txt").read_text()
    assert "option(SVX_ENABLE_SANITIZERS" in Path("CMakeLists.txt").read_text()
    assert '#define SVX_VERSION "1.0.0"' in Path(
        "svx_runtime/include/svx/python_runtime.hpp"
    ).read_text()
    installed_data = metadata["tool"]["setuptools"]["data-files"]
    assert "CMakeLists.txt" in installed_data["share/svx"]
    assert "svx_runtime/src/python_runtime.cpp" in installed_data[
        "share/svx/svx_runtime/src"
    ]
    assert "svx_runtime/include/svx/python_runtime.hpp" in installed_data[
        "share/svx/svx_runtime/include/svx"
    ]
    assert "call_sv" not in svx.__all__
    assert "bind_instance" not in svx.__all__
    assert "unbind_instance" not in svx.__all__


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
