"""Generate the deliberately selected UART boundary from public SvTypes types."""
import argparse
import copy
import json
from pathlib import Path

import svtypes


def binding(annotation, sv=None):
    codec = svtypes.materialize_type_spec(annotation, location="OpenTitan UART")
    return dict(unified_type_name=svtypes.unified_type_name(codec),
                svtypes=svtypes.type_spec_identity(annotation),
                sv=sv or svtypes.sv_type_expression(codec),
                sv_packer=svtypes.sv_packer_expression(codec),
                encoding_descriptor=svtypes.encoding_descriptor(codec).to_dict())


def manifest_data():
    integer, bit = binding(svtypes.Int), binding(svtypes.Bit[1], "bit")
    byte = binding(svtypes.Bit[8, svtypes.Signed], "byte")
    handle = binding(svtypes.RemoteRef["sv://uart_agent_pkg/uart_item"])
    native = dict(kind="sv_class", target_type_name="sv://uart_agent_pkg/uart_item",
                  sv_type="uart_agent_pkg::uart_item")
    cid = "sv://uart_svx_bridge_pkg/UartSequence"
    def parameter(name, type_, **extra):
        return dict(name=name, type=type_, **extra)
    item = lambda name: parameter(name, handle, handle=native)
    tx_index = [parameter("tx", bit), parameter("index", integer)]
    methods = []
    def method(name, params=(), result="void", timing="function", virtual=False, **extra):
        methods.append(dict(canonical_id=cid + "#" + name, name=name,
                            parameters=list(params), return_type=result, timing=timing,
                            virtual=virtual, pure_virtual=False, **extra))
    for name in ("body", "process_tx", "process_rx", "uart_init", "dut_shutdown",
                 "spinwait_txidle", "spinwait_rxidle"):
        method(name, timing="task", virtual=True)
    for name in ("send_tx_byte", "send_rx_byte"):
        method(name, [parameter("data", byte)], timing="task", virtual=True)
    method("read_rx", [parameter("value", integer, direction="output")], timing="task", virtual=True)
    method("observed_count", [parameter("tx", bit)], integer)
    method("observed_item", tx_index, handle, return_handle=native)
    for name in ("parity_enabled", "parity_odd"):
        method(name, tx_index, bit)
    for name in ("item_data", "item_frame", "item_identity"):
        method(name, [item("item")], integer)
    method("same_item", [item("first"), item("second")], bit)
    method("make_item", [parameter("data", integer)], handle, return_handle=native)
    method("set_item_data", [item("item"), parameter("data", integer)])
    base = dict(canonical_id=cid, language="sv", symbol="uart_svx_bridge_pkg::UartSequence",
                constructor=dict(initiator="python", parameters=[]), methods=methods)
    overrides = {"body", "process_tx", "process_rx", "send_tx_byte", "send_rx_byte"}
    child = dict(canonical_id="py://uart_migration/PythonUart", language="python",
                 symbol="uart_migration.PythonUart", base_lineage=[copy.deepcopy(base)],
                 methods=[dict(m, canonical_id="py://uart_migration/PythonUart#" + m["name"])
                          for m in methods if m["name"] in overrides])
    return dict(schema_uri="https://svx.dev/schema/inheritance-manifest/v2", schema_version="2.0.0",
                generator_abi_version=2, required_runtime_capabilities=[
                    "svtypes.checked-encoding-descriptor.v1", "svtypes.codec-context.v1",
                    "svtypes.record-schema.v1", "svtypes.remote-reference.v1"], classes=[base, child])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--sv-build-command", type=Path,
                        help="original compiler argv JSON (directory and arguments)")
    args = parser.parse_args()
    args.output = args.output.resolve()
    if not args.check:
        args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / "manifest.json"
    content = json.dumps(manifest_data(), indent=2) + "\n"
    if args.check:
        if not path.is_file() or path.read_text() != content:
            raise SystemExit("UART manifest is stale; rerun generate.py")
    elif not path.is_file() or path.read_text() != content:
        path.write_text(content)
    # The public CLI owns generation and the artifact inventory.
    import subprocess
    import sys
    command = [sys.executable, "-m", "svx", "inheritance-gen", "--manifest", str(path),
                    "--python-out", str(args.output / "python"), "--sv-out", str(args.output / "mirrors.sv"),
                    "--artifact-manifest", str(args.output / "artifacts.json")]
    if args.sv_build_command:
        command += ["--sv-build-command", str(args.sv_build_command.resolve()),
                    "--sv-source", str(Path(__file__).with_name("uart_bridge.sv").resolve())]
    subprocess.run([*command, *(["--check"] if args.check else [])], check=True)


if __name__ == "__main__":
    main()
