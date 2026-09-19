# 基础启动

[English](README.md)

这是最小可运行的 SVX 边界示例，展示仿真器托管的 Python 调用路径：

1. SV 初始化 SVX。
2. SV 加载 Python module。
3. SV 启动显式导出的 Python function。
4. Python 调用 `svx.display`。
5. Python 调用 `svx.delay(1.5, "ns")`。

最终 SV 时间前进 1.5 ns，并按 `svx_pkg` 的时间精度取整。需要面向实际
transaction 的端到端路径时，继续阅读 [typed bus 示例](../milestone_7_sv_typed_helpers/README.zh-CN.md)。

## 构建

推荐先构建本地 native runtime：

```sh
cmake -S . -B build
cmake --build build
```

通过目标仿真器的标准 DPI 流程集成本目录的 `tb.sv`、SVX package 文件及已
构建 runtime。本目录的 SystemVerilog testbench 和 Python 测试源码不依赖
特定工具链。
