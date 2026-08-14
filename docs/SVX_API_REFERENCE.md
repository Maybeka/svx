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
- inheritance declarations: `inheritance_type`, `inheritance_parameter`,
  `inheritance_method`, `inheritance_class`, and `manifest_from_declarations`;
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

Generated Python mirrors keep the foreign class and method names. Their method
signatures contain `input`, `inout`, and `ref` values; pure `output` values are
not call arguments. A method with only a function result returns that result
directly. A method with any copy-out value returns its generated SvTypes
response value, exported by the generated module as
`<Class><Method>Response`; its fields are the declared `output`, `inout`, and
`ref` values followed by `result` when present. Field values use normal
SvTypes generated-object access, including `.value` for scalar descriptors.

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

The `svx_inheritance_registry`, dispatcher/factory interfaces, raw `chandle`
payload functions, DPI imports/exports, and generated adapter entry points are
implementation ABI. They are public only to generated SVX code and must not be
called directly by application code.

## Compatibility

SVX 1.x accepts inheritance manifest major 2, generator ABI 2, and generated
artifact manifest major 1. It rejects incompatible Python/native/SystemVerilog product or runtime ABI,
generator ABI, manifest major, SvTypes major, formal capability names, encoding descriptor,
or generated file hash before dispatch.

Raw payload APIs are untyped integration facilities. They do not define the
wire contract of typed channels, inheritance calls, or hierarchical access.
