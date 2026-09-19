# Basic Bootstrap

[中文](README.zh-CN.md)

Use this as the smallest runnable SVX boundary. It establishes the
simulator-hosted Python path:

1. SV initializes SVX.
2. SV loads a Python module.
3. SV starts an explicitly exported Python function.
4. Python calls `svx.display`.
5. Python calls `svx.delay(1.5, "ns")`.

The final SV time advances by 1.5 ns, rounded according to `svx_pkg` time
precision. Continue with the [typed bus example](../milestone_7_sv_typed_helpers)
for a production-oriented transaction boundary.

## Build

Preferred local/native build:

```sh
cmake -S . -B build
cmake --build build
```

Integrate `tb.sv`, the SVX package files, and the built runtime using the
target simulator's standard DPI flow. The SystemVerilog testbench and Python
test source in this directory are intentionally toolchain-neutral.
