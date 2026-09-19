# CLI Generation Workflow

[中文](README.zh-CN.md)

Use this example when integrating generated types into a project build. It
demonstrates:

- generate SV types with `python -m svx svtypes-gen`
- use typed channel role helpers from Python
- start a synchronous Python test with `svx_run_test`
- keep bus timing and monitor sampling in SystemVerilog

Generate the SystemVerilog model:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module examples.milestone_6_cli_workflow.tests.types \
  --channel-helpers \
  --out examples/milestone_6_cli_workflow/generated/types.sv
```

Inspect SVX integration information:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx share
PYTHONPATH=python:../svtypes/python:. python3 -m svx compile-flags
```

Integrate `tb.sv` and the generated type file using the target simulator's
normal DPI flow.
