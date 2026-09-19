from io import StringIO
from pathlib import Path

from svx.cli import main


EXAMPLES = Path("examples")


def test_examples_index_covers_current_adoption_paths():
    index = (EXAMPLES / "README.md").read_text()
    for capability in (
        "Basic bootstrap",
        "Fork/join",
        "Error policy",
        "Raw payload channels",
        "Typed bus testbench",
        "Existing SV environment",
        "CLI workflow",
        "cross_language_inheritance",
        "python_owned_inheritance",
        "hierarchical_signal_access",
        "Capability Matrix",
    ):
        assert capability in index


def test_every_example_readme_has_a_chinese_counterpart():
    english_readmes = sorted(EXAMPLES.rglob("README.md"))
    assert english_readmes
    for english in english_readmes:
        chinese = english.with_name("README.zh-CN.md")
        assert chinese.is_file(), f"missing Chinese example documentation: {chinese}"
        assert "[中文](README.zh-CN.md)" in english.read_text()
        assert "[English](README.md)" in chinese.read_text()


def test_cross_language_inheritance_example_artifacts_are_current():
    out = StringIO()
    assert (
        main(
            [
                "inheritance-gen",
                "--manifest",
                "examples/cross_language_inheritance/inheritance.json",
                "--python-out",
                "examples/cross_language_inheritance/generated/python",
                "--sv-out",
                "examples/cross_language_inheritance/generated/inheritance_mirrors.sv",
                "--artifact-manifest",
                "examples/cross_language_inheritance/generated/svx-artifacts.json",
                "--check",
            ],
            out=out,
        )
        == 0
    )
    testbench = (EXAMPLES / "cross_language_inheritance" / "tb.sv").read_text()
    assert "BaseDriver_python_proxy" in testbench
    assert "svx_shutdown" in testbench


def test_python_owned_inheritance_example_artifacts_are_current():
    out = StringIO()
    assert (
        main(
            [
                "inheritance-gen",
                "--manifest",
                "examples/python_owned_inheritance/inheritance.json",
                "--python-out",
                "examples/python_owned_inheritance/generated/python",
                "--sv-out",
                "examples/python_owned_inheritance/generated/inheritance_mirrors.sv",
                "--artifact-manifest",
                "examples/python_owned_inheritance/generated/svx-artifacts.json",
                "--check",
            ],
            out=out,
        )
        == 0
    )
    testbench = (EXAMPLES / "python_owned_inheritance" / "tb.sv").read_text()
    assert "SvCounterFactory" in testbench
    assert "register_factory" in testbench


def test_hierarchical_signal_example_predeclares_paths_at_initialization():
    declarations = (EXAMPLES / "hierarchical_signal_access" / "signal_declarations.py").read_text()
    testbench = (EXAMPLES / "hierarchical_signal_access" / "tb.sv").read_text()
    assert declarations.count("svx.declare_signal(") == 3
    assert "svx_init_with_signal_declarations" in testbench
    assert "examples.hierarchical_signal_access.signal_declarations" in testbench
    assert "reg ready;" in testbench
    assert "reg [7:0] data;" in testbench
