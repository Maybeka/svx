# SVX Milestone 1 Basic Example

This example verifies the first simulator-hosted Python path:

1. SV initializes SVX.
2. SV loads a Python module.
3. SV starts an explicitly exported Python function.
4. Python calls `svx.display`.
5. Python calls `svx.delay(1.5, "ns")`.

Expected simulation behavior: the final SV time is advanced by 1.5 ns, rounded
according to `svx_pkg` time precision.

## Build

Preferred local/native build:

```sh
cmake -S . -B build
cmake --build build
```

Integrate `tb.sv`, the SVX package files, and the built runtime using the
target simulator's standard DPI flow. The SystemVerilog testbench and Python
test source in this directory are intentionally toolchain-neutral.
