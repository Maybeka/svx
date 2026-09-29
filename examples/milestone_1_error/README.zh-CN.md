# 异常策略

[English](README.md)

请使用[示例运行指南](../RUNNING_EXAMPLES.zh-CN.md)；本示例有意得到 fatal 结果，是正常示例流程的例外。

此示例展示 SV/Python 边界上的默认 fatal 异常策略。

导出的 Python function 会抛出未捕获异常。SVX 应报告 Python traceback，
并通过 SV fatal 路径终止仿真。
