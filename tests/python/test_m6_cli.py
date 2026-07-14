from io import StringIO

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
    assert "typedef enum int" in generated
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
