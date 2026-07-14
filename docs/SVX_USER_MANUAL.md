# SVX User Manual

Status: active user guide for SVX 0.1.0.

This manual explains how to use the current SVX milestone implementation in an
existing SystemVerilog verification environment.

SVX is not a replacement simulator scheduler and it is not a new component
framework. The intended user is a SystemVerilog verification engineer who wants
to keep timing-aware verification structure in SystemVerilog while moving
higher-level test intent, data modeling, generation, and checking into Python.

## 1. Core Usage Model

Use this split as the default design rule:

- SystemVerilog owns clocks, resets, interfaces, signal driving, monitor
  sampling, agents, sequencers, UVM phases, process scheduling, and simulator
  integration.
- Python owns tests, sequences, transaction construction, configuration data,
  expected data, scoreboarding policy, and reusable scenario logic.
- SVX connects the two through explicit exported Python entry points,
  simulator-owned primitives, and binary SvTypes channels.

Python `async`/`await` is not part of the SVX simulation model. Python threads,
subprocesses, or host-native async code may be used only for host-side work
that does not call SVX primitive APIs.

## 2. First Adoption Pattern

Start with a Python-controlled test around an existing SV or UVM environment.

1. Keep the existing SV testbench structure.
2. Add `svx_init()` and one simulator-started Python entry point.
3. Keep the existing SV driver and monitor timing code.
4. Replace only the sequence-item source or checker sink with SVX channels.
5. Let Python generate transactions and check responses or observations.

This proves the SVX boundary without moving signal-level behavior out of
SystemVerilog.

For an example, see
[examples/milestone_5_existing_env](../examples/milestone_5_existing_env).

## 3. Define SvTypes Models

Define transaction, response, observation, and configuration objects in Python.
Group them by protocol or subsystem.

```text
verification/
  svtypes_models/
    apb_types.py
  sv/
    generated/
      apb_types.sv
  tests/
    apb_smoke.py
```

Example model:

```python
from svtypes import Bits, Int, SvObject, get_package, svobj

pkg = get_package("apb_types")

@svobj(registry=pkg)
class ApbReq(SvObject):
    id = Int()
    addr = Bits(32)
    data = Bits(32)
    write = Bits(1)
```

SvTypes is independent from the SVX runtime. It is the data contract used by
Python, generated SystemVerilog, and generated C++ support code.

## 4. Generate SystemVerilog Types

Generate matching SV classes from the Python model module:

```sh
PYTHONPATH=python:. python3 -m svx svtypes-gen \
  --module verification.svtypes_models.apb_types \
  --out verification/sv/generated/apb_types.sv
```

Generate only selected declarations when needed:

```sh
PYTHONPATH=python:. python3 -m svx svtypes-gen \
  --module verification.svtypes_models.apb_types \
  --types ApbReq,ApbRsp,ApbObs \
  --out verification/sv/generated/apb_types.sv
```

Generate SystemVerilog typed-channel helpers at the same time:

```sh
PYTHONPATH=python:. python3 -m svx svtypes-gen \
  --module verification.svtypes_models.apb_types \
  --types ApbReq,ApbRsp,ApbObs \
  --channel-helpers \
  --out verification/sv/generated/apb_types_and_channels.sv
```

Generated files should be deterministic. For integration projects, either
commit generated SV files or regenerate them as an explicit build step.

## 5. Inspect Build Inputs

Use the SVX CLI to discover package files, include paths, and simulator flags.

```sh
PYTHONPATH=python:. python3 -m svx share
PYTHONPATH=python:. python3 -m svx sv-files
PYTHONPATH=python:. python3 -m svx compile-flags
PYTHONPATH=python:. python3 -m svx libs
```

These commands are intended to make project build scripts depend on SVX tooling
instead of hard-coded local paths.

## 6. Include SVX in SystemVerilog

Include the SvTypes runtime, SVX package, and generated model file in the SV
testbench or a project package.

```systemverilog
`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "verification/sv/generated/apb_types_and_channels.sv"

module tb;
  import svx_pkg::*;
endmodule
```

SystemVerilog remains responsible for timed behavior. Drivers should consume
request objects, drive interfaces, and publish response objects. Monitors
should sample interfaces and publish observations.

## 7. Start Python From SystemVerilog

Use `svx_run_test(module_name, function_name)` when you want a single
registered Python test entry point.

```systemverilog
initial begin
  svx_init();

  fork
    begin
      svx_run_test("verification.tests.apb_smoke", "test_apb_smoke");
    end
    begin
      existing_driver();
    end
    begin
      existing_monitor();
    end
  join

  $finish;
end
```

`svx_run_test` is a convenience wrapper over module loading and exported
function startup. The Python function must still be registered explicitly.

## 8. Write Python Tests

Use `@svx.test` for simulator-started tests. Use role helpers for common
request/response and monitor channel patterns.

```python
import svx
from svtypes import clear_svx_object_registry
from verification.svtypes_models.apb_types import ApbObs, ApbReq, ApbRsp

@svx.test
def test_apb_smoke():
    clear_svx_object_registry()

    bus = svx.reqrsp_channel("env.apb0", ApbReq, ApbRsp)
    mon = svx.mon_channel("env.apb0.mon", ApbObs)

    req = ApbReq()
    req.id.value = 1
    req.addr.value = 0x1000
    req.data.value = 0x12345678
    req.write.value = 1

    rsp = bus.request(req)
    assert rsp.id.value == 1

    obs = mon.get()
    assert obs.addr.value == req.addr.value
```

Uncaught Python exceptions are reported through the configured SVX exception
policy. The default policy is fatal.

Use `pytest` for pure-Python model, generator, and helper tests that do not
need a simulator.

## 9. Use Typed Helpers in SV

Generated typed-channel helpers remove manual payload metadata checks and
`pack`/`unpack` boilerplate from drivers and monitors.

```systemverilog
ApbReq req;
ApbRsp rsp;
ApbObs obs;

svx_get_ApbReq("env.apb0.req", req);

// Drive timed SV behavior here.

rsp = new();
svx_put_ApbRsp("env.apb0.rsp", rsp);

obs = new();
svx_put_ApbObs("env.apb0.mon", obs);
```

For nonblocking empty-channel checks, use the task-form `try_get` helper:

```systemverilog
bit ok;
ApbReq req;

svx_try_get_ApbReq("env.apb0.req", ok, req);
if (!ok) begin
  // Channel was empty.
end
```

Generated helper names are type-driven:

```text
svx_get_<TypeName>
svx_put_<TypeName>
svx_peek_<TypeName>
svx_try_get_<TypeName>
svx_try_put_<TypeName>
```

Generated helpers validate:

- payload kind is `svtypes`
- content type is `application/x-svtypes`
- payload type metadata matches the expected SvTypes class
- unpack consumed the entire byte stream

Fatal diagnostics include helper name, channel name, expected type, and actual
metadata when available.

## 10. Channel Naming

Use stable, hierarchical names:

```text
<env>.<agent_or_block>.<role>
```

Recommended roles:

- `req`: request or sequence item
- `rsp`: response or completion item
- `mon`: monitor observation
- `config`: configuration object
- `expected`: expected scoreboard item
- `actual`: actual scoreboard item
- `control`: explicit test-control message

Examples:

```text
env.bus0.req
env.bus0.rsp
env.bus0.mon
```

Avoid language-specific names such as `python_to_sv`, global names such as
`req`, and reusing one channel for unrelated object types.

## 11. Existing SV Driver Pattern

An existing SV driver can keep its timing and interface code. Only its item
source changes.

```systemverilog
task automatic existing_style_driver();
  Req tx;
  forever begin
    svx_get_Req("env.bus0.req", tx);
    drive_interface(tx);
    svx_put_Rsp("env.bus0.rsp", rsp);
  end
endtask
```

Do not move clock waits, handshakes, or interface assignments into Python.

## 12. Existing SV Monitor Pattern

An existing SV monitor can keep sampling in SV and publish typed observations
to Python.

```systemverilog
task automatic existing_style_monitor();
  Obs obs;
  forever begin
    sample_interface(obs);
    svx_put_Obs("env.bus0.mon", obs);
  end
endtask
```

Python can consume `env.<agent>.mon` and compare observations against expected
data.

## 13. Existing UVM Environment Pattern

For UVM environments, keep the UVM component hierarchy and phase ownership in
SystemVerilog. SVX should enter through narrow typed-channel boundaries instead
of replacing `uvm_driver`, `uvm_monitor`, sequencer arbitration, config-db, or
factory behavior.

Recommended first adoption points:

- a test or environment phase calls `svx_init()` and starts one Python entry
  point
- an existing driver retrieves SvTypes sequence items from a named `req`
  channel instead of a legacy sequence source
- an existing monitor publishes generated SvTypes observation objects to a
  named `mon` channel
- Python owns scenario construction and high-level checking
- SV translates Python config objects into existing UVM config objects when
  that avoids broad testbench churn

Keep `raise_objection`, `drop_objection`, interface timing, sequencer policy,
and monitor sampling in SV until a dedicated adapter milestone defines a
stronger UVM integration layer.

## 14. Object Lifecycle Rules

At independent test boundaries:

- clear the Python SvTypes object registry
- clear the SV object registry when possible
- drain channels or use unique named channels
- do not persist `__svx_obj_id` across simulation runs
- document any intentional object sharing scope

For object graphs, use the current default policy:

- update compatible registered objects in place
- rebind fields to the selected registry object
- fail on type mismatch

## 15. Compile and Run

Compile the SVX package files, the SvTypes runtime, generated type helpers,
and the project testbench using the target simulator's normal DPI integration
mechanism. Build the C++ runtime for the Python ABI used by the simulator
process, then make its library path available to the simulator.

Project build scripts should derive SVX include paths, SV file lists, and
library paths from the CLI commands in section 5 instead of hard-coding local
paths.

## 16. Reference Examples

Prepare the M5 existing-environment example:

```sh
PYTHONPATH=python:. python3 examples/milestone_5_existing_env/generate_sv.py \
  > examples/milestone_5_existing_env/generated_types.sv

```

Prepare the M6 CLI workflow example:

```sh
PYTHONPATH=python:. python3 -m svx svtypes-gen \
  --module examples.milestone_6_cli_workflow.tests.types \
  --out examples/milestone_6_cli_workflow/generated/types.sv

```

Prepare the M7 typed-helper example:

```sh
PYTHONPATH=python:. python3 -m svx svtypes-gen \
  --module examples.milestone_7_sv_typed_helpers.tests.types \
  --channel-helpers \
  --out examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv

```

Each example supplies SystemVerilog and Python sources for integration with
the project's target simulator configuration.

## 17. Cross-Language Inheritance

Cross-language inheritance is generated from an SVX inheritance manifest. The
manifest is the only runtime input. Every value binding names an SvTypes Python
codec, its SV declaration, and its generated SV packer; SVX transports only
object/method metadata and opaque SvTypes bytes.

```sh
PYTHONPATH=python:. python -m svx inheritance-gen \
  --manifest inheritance.json --python-out generated/python \
  --sv-out generated/inheritance_mirrors.sv
```

For an SV-owned `tb_pkg::BaseDriver`, derive from `svx_sv.tb_pkg.BaseDriver`.
The generated SV `BaseDriver_python_proxy` is the base-typed object used by SV.
For a Python-owned `checks.BaseMonitor`, derive in SV from the generated
`svx_py_checks_pkg::BaseMonitor`; Python accesses the SV-derived object through
`svx_py.checks.BaseMonitor`. Generated proxies retain the foreign base's simple
name. Declared task overrides may call `super()` across either language
boundary.

All proxy objects use a nonzero unique 64-bit remote object ID. Call
`svx.close_instance(id)` for deterministic pair release, or invoke
`svx_pkg::svx_shutdown()` during simulator teardown to clear all inheritance
registries. Calls after either release fail with an unknown-object diagnostic.

Constructible classes declare a manifest `constructor` with an `initiator`
(`python` or `sv`) and an ordered SvTypes-bound parameter list. That initiator
is the sole owner and exposes the generated public factory; callers never
manually provide a remote object ID. The factory allocates the ID, creates both
sides with the same typed values, binds the pair, then runs the post-bind hook.
If either construction step fails, it rolls back both partial entries. Foreign
virtual calls from constructors are invalid until binding completes.

For Python-initiated creation, register a concrete `svx_pkg::svx_factory`
under the manifest class ID before constructing the generated Python proxy.
This tells the generic runtime which application SV-derived class to create;
the manifest names only the foreign Python base.

Supported today: declared task and nonblocking function calls in both
directions, SvTypes payloads, task/function-base `super()` calls, direct
recursive callback rejection, both constructor initiators with SvTypes
arguments, timed task overrides, and explicit shutdown cleanup. Function
callbacks are nonblocking and cannot consume simulator time. General
blocking cycles are rejected when an active object/method frame repeats; the
diagnostic includes the complete repeated-frame path.

Simulator-neutral integration sources, including inheritance regressions, are
available under `tests/integration/`. Their execution harness is maintained in
the project's local verification environment. The public Python suite remains
available through `pytest`.

## 18. Debug Checklist

When integration fails, check:

- `PYTHONPATH` includes the repository and project Python roots
- `LD_LIBRARY_PATH` includes the SVX shared library directory
- simulator command includes `-sv_lib <path-to-libsvx>`
- generated SV matches the current Python SvTypes declarations
- channel names match exactly
- payload kind is `svtypes`
- payload content type is `application/x-svtypes`
- payload type metadata matches the expected class name
- object registries were not cleared too early
- Python code called SVX primitives only inside an active SVX execution context

## 19. Anti-Patterns

Avoid:

- Python `async`/`await` for simulator timing
- Python threads or subprocesses calling SVX primitives
- Python-owned signal-level bus timing
- storing simulator handles in SvTypes objects
- sending typed transaction data as strings or hex text
- reusing one channel for unrelated payload types
- replacing stable SV drivers or monitors before the channel boundary is proven
- creating a new component hierarchy before the current primitives are adopted
- invoking undeclared foreign methods or bypassing generated mirrors
- manually serializing inheritance values outside SvTypes
