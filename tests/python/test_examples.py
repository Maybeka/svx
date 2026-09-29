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
        "foreign_handles",
        "hierarchical_signal_access",
        "Capability Matrix",
        "SVX Cookbook (Chinese)",
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


def test_every_cookbook_example_has_an_operational_run_guide():
    english_guide = EXAMPLES / "RUNNING_EXAMPLES.md"
    chinese_guide = EXAMPLES / "RUNNING_EXAMPLES.zh-CN.md"
    assert english_guide.is_file()
    assert chinese_guide.is_file()

    for readme in sorted(EXAMPLES.glob("*/README.md")):
        assert "RUNNING_EXAMPLES.md" in readme.read_text(), (
            f"missing operational run guide: {readme}"
        )
        chinese = readme.with_name("README.zh-CN.md")
        assert "RUNNING_EXAMPLES.zh-CN.md" in chinese.read_text(), (
            f"missing Chinese operational run guide: {chinese}"
        )


def test_normal_example_testbenches_shutdown_svx_before_finishing():
    fatal_demo = EXAMPLES / "milestone_1_error" / "tb.sv"
    for testbench in sorted(EXAMPLES.glob("*/tb.sv")):
        if testbench == fatal_demo:
            continue
        source = testbench.read_text()
        assert "svx_shutdown();" in source, f"missing deterministic shutdown: {testbench}"
        assert source.index("svx_shutdown();") < source.index("$finish;"), (
            f"shutdown must precede finish: {testbench}"
        )


def test_cookbook_is_linked_and_covers_every_core_example_boundary():
    cookbook = Path("docs/SVX_COOKBOOK.zh-CN.md").read_text()
    for path in (
        "milestone_1_basic",
        "milestone_1_fork",
        "milestone_1_shared_state",
        "milestone_1_error",
        "milestone_2_payload_channel",
        "milestone_2_typed_channel",
        "milestone_5_existing_env",
        "milestone_6_cli_workflow",
        "milestone_7_sv_typed_helpers",
        "cross_language_inheritance",
        "python_owned_inheritance",
        "foreign_handles",
        "hierarchical_signal_access",
    ):
        assert f"../examples/{path}" in cookbook

    assert "SystemVerilog 拥有仿真" in cookbook
    assert "SvTypes 拥有数据契约" in cookbook
    assert "svx_init_with_signal_declarations" in cookbook
    assert "svx_proxy_base_monitor::BaseMonitor" in cookbook
    assert "put_payload(" in cookbook
    assert "原始字节必须使用" in cookbook
    assert "示例运行指南" in cookbook


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
    assert "BaseDriver" in testbench
    assert "svx_mirror_sv_example_driver_pkg_BaseDriver" not in testbench
    assert '`SVX_GET_OBJECT(example_driver_pkg::BaseDriver, "example.driver", driver)' in testbench
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


def test_foreign_handle_example_artifacts_are_current():
    manifest = EXAMPLES / "foreign_handles" / "generated" / "handles.json"
    assert (
        main(
            [
                "inheritance-manifest",
                "--python-module",
                "examples.foreign_handles.python_api",
                "--sv-source",
                "examples/foreign_handles/bus_if.sv",
                "--out",
                str(manifest),
                "--check",
            ],
            out=StringIO(),
        )
        == 0
    )
    assert (
        main(
            [
                "inheritance-gen",
                "--manifest",
                str(manifest),
                "--sv-source",
                "examples/foreign_handles/bus_if.sv",
                "--python-out",
                "examples/foreign_handles/generated/python",
                "--sv-out",
                "examples/foreign_handles/generated/mirrors.sv",
                "--artifact-manifest",
                "examples/foreign_handles/generated/svx-artifacts.json",
                "--check",
            ],
            out=StringIO(),
        )
        == 0
    )
    testbench = (EXAMPLES / "foreign_handles" / "tb.sv").read_text()
    assert "TaggedPacket" in testbench
    assert "virtual example_bus_if.master" in testbench


def test_hierarchical_signal_example_predeclares_paths_at_initialization():
    declarations = (EXAMPLES / "hierarchical_signal_access" / "signal_declarations.py").read_text()
    testbench = (EXAMPLES / "hierarchical_signal_access" / "tb.sv").read_text()
    assert declarations.count("svx.declare_signal(") == 3
    assert "svx_init_with_signal_declarations" in testbench
    assert "examples.hierarchical_signal_access.signal_declarations" in testbench
    assert "reg ready;" in testbench
    assert "reg [7:0] data;" in testbench
