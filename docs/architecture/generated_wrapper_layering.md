# SVX Generated Wrapper Layering

M6 standardizes the intended layering for generated files and user-owned code.
This is documentation for the current CLI and examples, not a new RPC or
component framework.

## 1. Principles

- Python SvTypes declarations are the source of truth for transaction,
  configuration, and observation data.
- Generated SystemVerilog code should be deterministic and reviewable.
- Generated code should not own signal-level timing or UVM phase behavior.
- User SystemVerilog code owns interfaces, drivers, monitors, agents,
  sequencers, DUT binding, and simulator timing.
- User Python code owns test intent, scenario construction, expected data, and
  high-level checking.
- All simulator-visible concurrency remains SystemVerilog-owned.

## 2. Layers

Recommended downstream layering:

```text
Python SvTypes models
  -> generated SV type package/classes
  -> optional generated typed-channel helper package
  -> user SV drivers/monitors/tests
  -> user Python tests/checkers/sequences
```

The M6 implementation focused on the first and last parts:

- `python -m svx svtypes-gen` generates deterministic SV type declarations.
- Python role helpers wrap existing M2 typed channels.
- `svx_run_test` is a convenience wrapper over `svx_load` and `svx_start`.

The M7 implementation adds generated SystemVerilog typed-channel helpers:

- `python -m svx svtypes-gen --channel-helpers` emits typed SV channel helpers.
- `svx_get_<TypeName>` and `svx_put_<TypeName>` wrap payload metadata checks,
  byte-queue conversion, and generated SvTypes pack/unpack.
- `svx_try_get_<TypeName>` uses a task form with an output success bit for
  portability.
- The generated helper layer remains separate from user-owned SV drivers,
  monitors, and timing behavior.

## 3. Generated SV Type Package

The generated SV type package or include file may contain:

- enum typedefs
- forward class typedefs
- SvTypes object classes
- pack/unpack methods
- object graph metadata and registry interactions

It must not contain:

- driver timing
- monitor sampling loops
- UVM phase ownership
- DUT hierarchy references
- Python async/thread integration

## 4. Typed Channel Helpers

Typed channel helpers should remain thin wrappers around named channels.

Python-side role helpers such as `req_channel`, `rsp_channel`, `mon_channel`,
`config_channel`, and `reqrsp_channel` standardize naming and expected item
types, but they do not create a component framework.

Generated SV channel helpers provide typed get/put functions around the same
payload contract. These helpers remain separate from user drivers and monitors.

## 5. Typed API Layer

Manifest-driven cross-language inheritance now supplies declarative typed
method adapters in addition to these channel helpers. That layer preserves the
same separation:

- generated interfaces describe callable boundaries
- generated bridge code handles marshalling
- user SV code implements hardware-coupled behavior
- user Python code implements test intent and checking

The generated adapters preserve the SVX rule that Python is not a
simulator scheduler.

Generated Python method adapters preserve declared parameter names and order.
The implicit instance receiver is renamed when an SV parameter is named
`self`; it is not part of the foreign method's argument contract. If a parameter
shadows `invoke_sv` or `invoke_sv_static`, the adapter uses a collision-free
local import alias. These implementation names must not require users to rename
legal source-method parameters. Constructor wrappers and SV record generation
have separate naming scopes and require their own collision checks.

Generated Python constructors also isolate their receiver, bridge imports and
object-ID temporary from declared formals. Before SV generation or runtime call
record construction, SVX compares the public SvTypes schema's ordered fields
with the declared contract. Missing, renamed or reordered fields are a dependency
contract error, not permission to drop a user parameter. The current dependency
does not preserve underscore-prefixed explicit RecordSchema fields; complete
construction with such formals remains unqualified despite the wrapper fix.
