from io import StringIO

import pytest
from svtypes import SvObject

from svx.cli import main
from svx.cli import _emit_svtypes


def run_cli(*args: str) -> str:
    out = StringIO()
    assert main(list(args), out=out) == 0
    return out.getvalue()


def test_channel_helpers_are_generated_for_object_types():
    generated = run_cli(
        "svtypes-gen",
        "--module",
        "examples.milestone_7_sv_typed_helpers.tests.types",
        "--channel-helpers",
    )

    assert "task automatic svx_get_M7BusReq" in generated
    assert "task automatic svx_peek_M7BusReq" in generated
    assert "task automatic svx_put_M7BusRsp" in generated
    assert "task automatic svx_try_get_M7BusObs" in generated
    assert "function automatic bit svx_try_put_M7BusObs" in generated
    assert "svx_payload_to_checked_byte_queue" in generated
    assert "application/x-svtypes" in generated


def test_channel_helpers_respect_explicit_type_selection():
    generated = run_cli(
        "svtypes-gen",
        "--module",
        "examples.milestone_7_sv_typed_helpers.tests.types",
        "--types",
        "M7BusReq",
        "--channel-helpers",
    )

    assert "task automatic svx_get_M7BusReq" in generated
    assert "task automatic svx_get_M7BusRsp" not in generated
    assert "typedef enum" not in generated


def test_channel_helpers_work_inside_package():
    generated = run_cli(
        "svtypes-gen",
        "--module",
        "examples.milestone_7_sv_typed_helpers.tests.types",
        "--package",
        "m7_pkg",
        "--channel-helpers",
    )

    assert "package m7_pkg;" in generated
    assert "  task automatic svx_get_M7BusReq" in generated
    assert "endpackage : m7_pkg" in generated


def test_duplicate_helper_names_fail_clearly():
    first = type("DupTx", (SvObject,), {"__module__": "first"})
    second = type("DupTx", (SvObject,), {"__module__": "second"})

    with pytest.raises(SystemExit, match="duplicate SvTypes object names"):
        _emit_svtypes([first, second], None, "test", channel_helpers=True)
