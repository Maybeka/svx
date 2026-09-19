# 异常策略

[English](README.md)

此示例展示 SV/Python 边界上的默认 fatal 异常策略。

导出的 Python function 会抛出未捕获异常。SVX 应报告 Python traceback，
并通过 SV fatal 路径终止仿真。
