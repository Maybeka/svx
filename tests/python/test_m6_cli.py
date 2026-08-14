from io import StringIO
from pathlib import Path

import svx
from svx.cli import main

from examples.milestone_6_cli_workflow.tests.types import M6BusOp, M6BusReq, M6BusRsp


def run_cli(*args: str) -> str:
    out = StringIO()
    assert main(list(args), out=out) == 0
    return out.getvalue()


def test_cli_discovery_commands_source_tree():
    share = run_cli("share")
    assert share.rstrip().endswith("/sv")

    native_source = run_cli("native-source")
    assert native_source.rstrip().endswith("/svx")
    assert (Path(native_source.strip()) / "CMakeLists.txt").is_file()

    sv_files = run_cli("sv-files")
    assert "svtypes_runtime/sv/svtypes_pkg.sv" in sv_files
    assert "sv/svx_pkg.sv" in sv_files

    libs = run_cli("libs")
    assert libs.rstrip().endswith("build/libsvx")

    flags = run_cli("compile-flags")
    assert "+incdir+" in flags
    assert "svtypes_runtime/sv/svtypes_pkg.sv" in flags


def test_svtypes_gen_module_and_explicit_types():
    generated = run_cli("svtypes-gen", "--module", "examples.milestone_6_cli_workflow.tests.types")
    assert "typedef enum bit [7:0]" in generated
    assert "typedef class M6BusReq;" in generated
    assert "class M6BusRsp extends svtypes_pkg::sv_object;" in generated

    explicit = run_cli(
        "svtypes-gen",
        "--module",
        "examples.milestone_6_cli_workflow.tests.types",
        "--types",
        "M6BusOp,M6BusReq",
    )
    assert "typedef class M6BusReq;" in explicit
    assert "class M6BusRsp" not in explicit


def test_committed_typed_example_outputs_are_reproducible():
    m2 = run_cli(
        "svtypes-gen",
        "--module",
        "examples.milestone_2_typed_channel.tests.typed_test",
        "--package",
        "m2_typed_pkg",
        "--channel-helpers",
    )
    assert m2 == Path(
        "examples/milestone_2_typed_channel/generated_types.sv"
    ).read_text()

    m6 = run_cli(
        "svtypes-gen",
        "--module",
        "examples.milestone_6_cli_workflow.tests.types",
        "--channel-helpers",
    )
    assert m6 == Path(
        "examples/milestone_6_cli_workflow/generated/types.sv"
    ).read_text()

    m5 = run_cli(
        "svtypes-gen",
        "--module",
        "examples.milestone_5_existing_env.tests.types",
        "--channel-helpers",
    )
    assert m5 == Path(
        "examples/milestone_5_existing_env/generated_types.sv"
    ).read_text()

    m7 = run_cli(
        "svtypes-gen",
        "--module",
        "examples.milestone_7_sv_typed_helpers.tests.types",
        "--channel-helpers",
    )
    assert m7 == Path(
        "examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv"
    ).read_text()


def test_role_helper_names_and_types():
    req = svx.req_channel("env.apb0.req", M6BusReq)
    assert req.name == "env.apb0.req"
    assert req.item_type is M6BusReq

    rr = svx.reqrsp_channel("env.apb0", M6BusReq, M6BusRsp)
    assert rr.req.name == "env.apb0.req"
    assert rr.rsp.name == "env.apb0.rsp"
    assert rr.req.item_type is M6BusReq
    assert rr.rsp.item_type is M6BusRsp


def test_svx_test_registers_as_export():
    @svx.test(name="m6.named_test")
    def local_test():
        return None

    exports = svx.list_exports()
    assert exports["m6.named_test"].__name__ == "local_test"


def test_type_classes_are_directly_available_for_cli_import():
    assert M6BusOp.__module__ == "examples.milestone_6_cli_workflow.tests.types"
    assert M6BusReq.__module__ == "examples.milestone_6_cli_workflow.tests.types"
