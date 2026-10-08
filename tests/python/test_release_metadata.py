import os
import tomllib
from io import StringIO
from pathlib import Path

import svx
import svx.cli as cli
from svx.cli import main


def test_source_distribution_includes_sv_headers_for_examples_and_tests():
    import shlex

    rules = [shlex.split(line) for line in Path("MANIFEST.in").read_text().splitlines()
             if line.startswith("recursive-include ")]
    for root in ("examples", "tests"):
        patterns = [pattern for rule in rules if rule[1] == root for pattern in rule[2:]]
        assert "*.sv" in patterns
        assert "*.svh" in patterns


def test_public_version_matches_project_metadata():
    metadata = tomllib.loads(Path("pyproject.toml").read_text())
    assert metadata["project"]["version"] == "1.0.0"
    assert svx.__version__ == metadata["project"]["version"]
    assert metadata["project"]["dependencies"] == ["svtypes>=1.4.2,<2.0.0", "greenlet>=3.1,<4.0"]
    release_contract = Path("docs/RELEASE_1.0.0.md").read_text()
    assert "| SvTypes | `>=1.4.2,<2.0.0` |" in release_contract
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


def test_release_native_build_gates_require_full_signal_backend_and_python_abi():
    contract = Path('docs/RELEASE_1.0.0.md').read_text()
    gates = contract.split('## Release Gates', 1)[1].split('## Release Inputs', 1)[0]
    assert gates.count('-DSVX_REQUIRE_DIRECT_VPI=ON') == 2
    assert gates.count('-DPython3_EXECUTABLE=') == 2
    assert gates.count('-DSVX_SIMULATOR_INCLUDE_DIR=') == 2
    assert 'cannot satisfy these release gates' in gates
    assert 'python -m pytest --runxfail -q' in gates
    assert 'expected-failure marker is not release acceptance' in gates


def test_cli_finds_support_beside_target_install_without_overrides(monkeypatch, tmp_path):
    target = tmp_path / "installed"
    package = target / "svx"
    package.mkdir(parents=True)
    share = target / "share/svx"
    (share / "sv").mkdir(parents=True)
    (share / "sv/svx_pkg.sv").write_text("package svx_pkg; endpackage\n")
    (share / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n")
    (share / "svx_runtime/src").mkdir(parents=True)
    (share / "svx_runtime/src/svx.cpp").write_text("// runtime source\n")
    monkeypatch.delenv("SVX_SHARE_DIR", raising=False)
    monkeypatch.setattr(cli, "__file__", str(package / "cli.py"))
    monkeypatch.setattr(cli.sysconfig, "get_path", lambda _key: str(tmp_path / "other-prefix"))
    assert cli.sv_dir() == share / "sv"
    out = StringIO()
    assert main(["native-source"], out=out) == 0
    assert out.getvalue().strip() == str(share)
