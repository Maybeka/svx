# CLI 生成工作流

[English](README.md)

在项目构建中集成生成类型时，使用此示例。它展示：

- 用 `python -m svx svtypes-gen` 生成 SV type
- 在 Python 中使用 typed channel role helper
- 用 `svx_run_test` 启动同步 Python test
- 在 SystemVerilog 中保留 bus timing 和 monitor sampling

生成 SystemVerilog model：

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module examples.milestone_6_cli_workflow.tests.types \
  --channel-helpers \
  --out examples/milestone_6_cli_workflow/generated/types.sv
```

检查 SVX 集成信息：

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx share
PYTHONPATH=python:../svtypes/python:. python3 -m svx compile-flags
```

通过目标仿真器的正常 DPI flow 集成 `tb.sv` 和生成 type 文件。
