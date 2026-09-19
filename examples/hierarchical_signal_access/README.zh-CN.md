# 分层信号访问

[English](README.md)

此接口适用于 Python 测试中的目标化 setup、检查和 fault injection，并非 SV
driver、monitor 或高吞吐信号传输的替代品。

`signal_declarations.py` 在 SVX 初始化时被导入，预先声明每条路径及其 SvTypes
codec。`tb.sv` 用该 module 名调用 `svx_init_with_signal_declarations`，因此无效
路径或不兼容的 packed shape 会在 Python 测试开始前失败。

测试展示：

- 二态 `Bit` 读写；
- packed signal 的 `force` 和 `release`；
- 使用 `LogicValue` 对四态 `Logic` 读写；
- 仅在 testbench 需要推进仿真时显式延时。

示例在 `tb.sv` 中将二态路径声明为 `reg` 和 packed `reg`，Python 侧使用
`Bit` codec。这是当前 SVX VPI signal service 所接受的可移植 packed variable
形式。

编译 `tb.sv` 时，SVX 必须带 direct VPI signal service。应用接口不使用 VPI
system task，也不需要单独加载 VPI plugin；SVX library 通过正常 DPI library flow
加载。

将路径保留在一个 declaration module 中，初始化后不要再添加路径。重复驱动或
采样应保留在 SV 中，使用 channel 传输 typed transaction 或 summary。
