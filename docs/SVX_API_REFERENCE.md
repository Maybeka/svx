# SVX Public API Reference

Status: release-candidate API classification for SVX 1.0.

## Stable Python API

The following names exported from `svx` are stable:

- registration: `export`, `test`, `list_exports`;
- simulator services: `display`, `delay`, `fork_join`, `fork_join_any`, and
  `fork_join_none`;
- channels: `Payload`, `Channel`, `channel`, the typed role classes, and their
  corresponding factory functions;
- inheritance lifecycle: `close_instance`;
- inheritance declarations: `Task`, `Function`, `Input`, `Output`, `Inout`,
  `inheritance_parameter`, `inheritance_method`,
  `inheritance_class`, `SVMirror`, `sv_mirror`, and
  `manifest_from_declarations`;
- hierarchical access: `Signal` and `declare_signal`;
- runtime and errors: `RuntimeState`, `runtime_state`, the `SVXError` hierarchy,
  `FATAL`, `REPORT`, `set_exception_policy`, and `get_exception_policy`.

Simulator-facing operations require an active SVX execution context. Handles
from a stopped session are stale. Typed values cross the boundary only through
public SvTypes descriptors and codecs.

`svx._native`, `svx._registry`, raw inheritance bind/call helpers, generated
registration helpers, and names
beginning with an underscore are private runtime ABI and may not be called by
user code.

Generated Python mirrors keep the foreign class method prototype: every
declared `input`, `output`, and `inout` formal remains present and in the same
order. `input` is passed as its decoded value. `svx.Inout(value)` and
`svx.Output()` are mutable copy-out carriers whose `.value` is read or assigned
by Python and is updated after a Python-to-SV call. A function returns its
ordinary Python result; a task returns `None`. Generated SvTypes request and
response records remain private transport implementation details. Field values
use normal SvTypes generated object access, including `.value` for scalar
descriptors. Inheritance callbacks must be synchronous ordinary Python
functions; coroutine functions and awaitable results are rejected fatally.

Inheritance manifests reject `ref` and `const ref`; SVX does not expose a
cross-language lvalue-alias capability. Use an explicit SvTypes object or
getter/setter API when an application needs mutable behavior across the boundary.

The concise Python declaration form uses `@svx.inheritance_method` directly:
an unwrapped concrete SvTypes type `T` or `svx.Input[T]` declares `input`; `svx.Output[T]`
and `svx.Inout[T]` declare their respective parameter directions.
while `-> svx.Task`, `-> svx.Function`, or `-> svx.Function[T]` declares task
or function transport and, in the last form, the SvTypes result binding. These
are declaration-only annotations, not Python runtime value types. Each Python
parameter declares its own direction; no annotation changes the direction of a
subsequent parameter. `Output[T]` and `Inout[T]` remain in their declared
position and receive mutable copy-out carriers. The explicit
`parameters=`, `return_type=`, and `timing=` form remains supported, but it
cannot be mixed with the corresponding prototype annotation. This
classification does not apply to `@svx.export` or `@svx.test`: those are
entered through the task-shaped `svx_start` boundary.

For static checking, SVX makes these declaration markers transparent:
`Input[T]` is treated as `T`, `Function[T]` as its ordinary result type `T`,
and `Task` as `None`. `Output[T]` and `Inout[T]` are typed carriers whose
`.value` has type `T`, so this concise form remains usable in Pyright and LSPs.

An SV source method marked `"static": true` is exposed as a generated Python
`@staticmethod`. It uses a generated class dispatcher, has no object ID, and
calls the qualified SV static implementation. Static and `virtual` are mutually
exclusive; a Python subclass may shadow the name locally but cannot override
the SV static member across the boundary.

## Stable CLI

- `svx share`, `svx native-source`, `svx sv-files`, `svx libs`, and
  `svx compile-flags` locate installed build inputs.
- `svx svtypes-gen` generates SystemVerilog declarations and optional typed
  channel helpers from SvTypes modules.
- `svx inheritance-gen` validates a manifest and generates Python mirrors,
  SystemVerilog mirrors, and an optional compatibility artifact manifest.
  `--check` verifies that all three requested output groups are current.
- `svx inheritance-migrate` converts the supported legacy manifest to the
  declarative schema without evaluating source expressions.
- `svx inheritance-manifest` normalizes decorated Python classes and versioned
  SV declaration metadata to the sole inheritance manifest schema. `--check`
  rejects a stale output.

## Stable SystemVerilog API

User code imports `svx_pkg` and uses `svx_init`,
`svx_init_with_signal_declarations`, `svx_load`, `svx_start`, `svx_run_test`,
and `svx_shutdown`. Channel byte helpers and generated typed helpers are also
stable.

The `svx_inheritance_registry`, dispatcher/factory interfaces, DPI
imports/exports, and generated adapter entry points are implementation ABI.
They are public only to generated SVX code and must not be called directly by
application code. The stable low-level `svx_channel_*_payload` tasks are an
untyped SV channel API; application code normally uses byte or generated typed
helpers instead.

## Compatibility

SVX 1.x accepts inheritance manifest major 2, generator ABI 2, and generated
artifact manifest major 1. It rejects incompatible Python/native/SystemVerilog product or runtime ABI,
generator ABI, manifest major, SvTypes major, formal capability names, encoding descriptor,
or generated file hash before dispatch.

Raw payload APIs are untyped integration facilities. They do not define the
wire contract of typed channels, inheritance calls, or hierarchical access.
