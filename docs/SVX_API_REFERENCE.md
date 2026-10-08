# SVX Public API Reference

Status: release-candidate API classification for SVX 1.0.

## Stable Python API

The following names exported from `svx` are stable:

- registration: `export`, `test`, `list_exports`;
- simulator services: `display`, `delay`, `fork_join`, `fork_join_any`, and
  `fork_join_none`;
- process handles: `ProcessGroup` and `ProcessStatus`, including `status()`,
  `await_()`, `kill()`, and `kill_running()`;
- channels: `Payload`, `Channel`, `channel`, the typed role classes, and their
  corresponding factory functions: `ReqChannel`, `RspChannel`, `MonChannel`,
  `ConfigChannel`, `ReqRspChannel`, `req_channel`, `rsp_channel`, `mon_channel`,
  `config_channel`, and `reqrsp_channel`;
- inheritance lifecycle: `close_instance`;
- inheritance declarations: `Task`, `Function`, `Input`, `Output`, `Inout`,
  `inheritance_parameter`, `inheritance_method`,
  `inheritance_class`, `sv_class_handle`, `virtual_interface_handle`,
  `SVMirror`, `sv_mirror`, and
  `manifest_from_declarations`;
- hierarchical access: `Signal` and `declare_signal`;
- runtime and errors: `RuntimeState`, `runtime_state`, the `SVXError` hierarchy,
  `SVXContextError`, `SVXExportError`, `SVXChannelError`, `SVXInheritanceError`,
  `SVXRemoteError`, `SVXSignalError`, `FATAL`, `REPORT`, `set_exception_policy`,
  `get_exception_policy`, and package metadata `__version__`.

Simulator-facing operations require an active SVX execution context. Handles
from a stopped session are stale. Typed values cross the boundary only through
public SvTypes descriptors and codecs.
SVX requires SvTypes `>=1.4.2,<2.0.0` and its callable public TypeSpec
normalization/identity APIs. An incomplete dependency is rejected at startup
and declaration/canonical-manifest generation, not diagnosed as an invalid
user annotation merely because a dependency API is missing.
Startup also requires `SvObject.codec_template()` before allocating its session.
SvTypes `1.4.2` includes the codec and external-field fixes required by SVX;
the older `1.4.1` release is not sufficient. See the
[release dependency note](RELEASE_1.0.0.md#compatibility).
The runtime supports one initialized session per simulator process; shutdown is
terminal, not an invitation to call `svx_init()` again.

`close_instance(instance)` releases an allocated cross-language pair without
requiring application access to generated private object-ID attributes.
`close_instance(object_id=...)` also accepts the existing nonzero unsigned
64-bit integer form. Boolean, zero, negative and oversized IDs are rejected.
For an instance, an existing native binding must refer to that same receiver.
Repeated close is idempotent within an active context; it does not revive an
object or alter its saved identity. Projected fields and retained field views
remain invalid after close, while unprojected Python-local fields remain usable.
Release also removes the receiver's own SvTypes codec-session registration;
it does not close the shared session or remove registrations of other objects.
This operation does not dispose arbitrary native class/VIF handles or RemoteRef
values. User methods named `close` are not replaced by a generated lifecycle
method. Python close uses a nonblocking DPI function bridge, including from
SV function callbacks. Cleanup hooks and their attribute lookup cannot delay,
wait, or start SV processes. Both registries are retired before the SV gateway
reports a cleanup failure and terminates the simulation, even under REPORT.

`ProcessGroup.kill()` requests cooperative cancellation and waits for its children
to finish unwinding before returning. It is idempotent for an already killed group;
`kill_running()` is an alias. A process cannot synchronously kill a group containing
itself. Stopped-session handles fail instead of acting on a new session.
Use `finally` for cleanup and do not swallow the internal cancellation exception.
Dropping a group handle does not cancel its children. The runtime retains their
execution state until they return, and reclaims completed unreferenced groups at
the next fork or shutdown. `svx_shutdown()` first cancels and joins tracked
children, while their cleanup still has access to channels and object registries.
As with `kill()`, a user SV task that does not observe cancellation must return
before shutdown can finish; shutdown cannot forcibly unwind arbitrary Python
or foreign task code. The embedded interpreter is retained until simulator exit.

When SV disables an active DPI task call, object/static inheritance task bridges
propagate the internal cancellation exception rather than wrapping it as a
remote-method failure. Python `finally` blocks still run. An interrupted call
does not copy out `Output`/`Inout` holders, although writes already performed by
the SV method are not rolled back. Nested SV-to-Python task callbacks acknowledge
disable after releasing their execution context and callback frame. A new
ordinary exception raised during cleanup remains an error, not cancellation.
This is distinct from cooperative `kill()`: arbitrary user SV tasks still need
to return or observe cooperative cancellation before `kill()` can finish.

Function callbacks and constructors reject SVX task/wait operations before dispatch.
Function methods and projected field operations use nonblocking SV function gateways.
Manifest declarations do not statically analyze arbitrary Python method bodies.
Regenerate all bridge artifacts when updating the generator/runtime together.

`REPORT` applies to exported entry functions and process children. Generated
inheritance/constructor failures remain fatal under either exception policy.

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
response records remain private transport implementation details.
Functions without a value result are supported, including virtual void callbacks
with copy-out parameters. They return `None` in Python. A formal named `result`
is an ordinary parameter, not an application-visible return-record slot.
Internal return slots and method-local names avoid declared parameter names
deterministically; users need not rename parameters to accommodate bridge locals.
Field values use normal SvTypes generated object access, including `.value` for scalar
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

Python-source `"static": true` declarations are accepted as logical manifest
data and require a source `@staticmethod`. Standalone Python-source proxies
generate static function/task bridges with receiver ID 0; importing the generated
Python module registers the declared source methods without constructing an
instance. Generated Python static views use the same class-level dispatcher.
Function callbacks cannot wait; task callbacks retain synchronous SV timing.
SV-root alternating projections also declare their Python static source by its
manifest symbol. The first callback resolves that exact source class, never a
dynamic derived receiver; generated modules avoid eagerly importing a source
that itself imports its mirror. Qualified static calls retain class ownership
when an SV or Python child hides the same name. Source-integrated generation
supports qualified Python-root alternating chains; arbitrary lineage shapes and
independent ancestor constructor routing remain incomplete.

Foreign class and virtual-interface formals use a concrete
`svtypes.RemoteRef[target]` as the SvTypes type. Add
`handle=svx.sv_class_handle(target, sv_type)` or
`handle=svx.virtual_interface_handle(target, sv_type)` to the explicit
`inheritance_parameter` declaration; a function result uses the corresponding
`return_handle=` on `inheritance_method`. An external class handle is opaque in
Python and can only be retained, passed, or returned. A virtual-interface
handle decodes to its generated restricted view. Run the manifest/generator
command with `--sv-source` to derive that view's visible signals, tasks, and
functions from the static interface/modport declaration.

Constructor input parameters use the same concrete handle declarations. Generated
SV constructors expose the native class or VIF type; their private request record
contains only RemoteRef values. Factories decode those references before new,
and SV-initiated construction encodes native handles before Python initialization.
VIF arguments reach Python as generated views, including a transport-only view
when no operations were exposed. Nulls retain the ordinary RemoteRef null
representation; unknown or incompatible handles fail rather than constructing
an object with a reinterpreted pointer. This does not implement the separately
planned per-ancestor construction records or qualify arbitrary alternating
constructor shapes. Qualified Python-root chains use the integrated source path.

## Experimental Python API

`publish_object` (`publish_object(name, instance)`) explicitly hands an already-bound live
cross-language object to an SV consumer using `SVX_GET_OBJECT`. It does not
publish arbitrary Python objects, transfer ownership, or provide reflective
lookup. This handoff API is experimental, not part of the stable Python API.

All names in `svx.__all__` are classified in the stable or experimental sections
above. An importable name in another module is not thereby a public application
API; private generated/native bridges remain private.

## Stable CLI

Expected SVX declaration and filesystem errors are printed to stderr with a
nonzero exit status (2). Place `--debug` before the subcommand to retain their
Python traceback, for example `svx --debug inheritance-gen ...`. Unexpected
implementation exceptions are not suppressed.

- `svx share`, `svx native-source`, `svx sv-files`, `svx libs`, and
  `svx compile-flags` locate installed build inputs.
- `svx svtypes-gen` generates SystemVerilog declarations and optional typed
  channel helpers from SvTypes modules. With `--out`, byte-identical output
  preserves its existing timestamp instead of triggering downstream rebuilds.
- `svx inheritance-gen` validates a manifest and generates Python mirrors,
  SystemVerilog mirrors, and an optional compatibility artifact manifest.
  `--check` verifies that all three requested output groups are current.
  Python and staged SV output directories have generator-owned file inventories;
  checks include obsolete owned files, and regeneration removes them. Other user
  files are retained. Use a dedicated output root for each manifest. The first
  inventory cannot identify unrecorded artifacts left by older generators.
  Before changing outputs, generation rejects existing non-generated files at
  target paths and paths escaping the output root, including through parent
  symlinks. The ownership checks cover Python, staged SV, and merged SV targets.
  Atomic replacement applies to individual files, not a crash-safe transaction
  spanning every output; use `--check` after an interrupted generation.
  Regeneration preserves timestamps of byte-identical files, including the
  ownership inventories, so unchanged generated inputs do not force recompilation.
  `--sv-source` additionally scans interface declarations to generate
  virtual-interface views.
  `--sv-integrated-dir DIR` emits `DIR/source.sv`, integrating the selected
  original source units with ordered bridge declarations. Compile it in place
  of those originals, after the runtime packages; original files are not edited.
  It is mutually exclusive with `--sv-out` and `--sv-stage-dir`. Multiple ordered
  source inputs require `--sv-compilation-unit`. Shared macro input files,
  definitions and include paths participate in the artifact freshness check.
  Integrated outputs use the same inventory, input-overwrite protection and
  unchanged-file timestamp policy. Invalid output combinations and missing
  required options reject before loading declarations or parsing source.
  Ordinary user source imports actually compiled during generation are persisted as
  `generation_inputs.python_imports`; changes make `--check` stale even when
  bridge output matches. Reused audited cached imports remain recorded and
  protected against output replacement; changed cached sources require a fresh
  command process. This is not discovery-to-generation provenance or tracking
  of custom importers and arbitrary external build dependencies.
  SVX/SvTypes/source-parser implementation sources are excluded from automatic user input
  records so framework preloads do not change freshness. Consumed-source
  stability/overwrite guards and explicit `--python-source` inputs are retained;
  these records are not a framework dependency lock.
  Automatic import records reject malformed digests, noncanonical/absolute paths
  and duplicate resolved source paths, including symlink aliases. Fresh command
  processes recompute the import set and prune dependencies no longer imported.
  This is not automatic declaration discovery or support for every source form;
  see [the source workflow](SVX_USER_MANUAL.md) for the build and check sequence.
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
imports/exports other than the explicitly listed payload API, and generated
adapter registration/dispatch entry points are implementation ABI.
They are public only to generated SVX code and must not be called directly by
application code. The stable low-level `svx_channel_*_payload` tasks are an
untyped SV channel API; application code normally uses byte or generated typed
helpers instead.

The stable channel application entry points are:

- `svx_channel_put_payload`, `svx_channel_get_payload`,
  `svx_channel_peek_payload`, `svx_channel_try_put_payload`, and
  `svx_channel_try_get_payload`;
- `svx_channel_put_bytes`, `svx_channel_put_byte_queue`,
  `svx_channel_try_put_bytes`, and `svx_channel_try_put_byte_queue`;
- `svx_payload_from_bytes`, `svx_payload_from_byte_queue`, and
  `svx_payload_to_byte_queue`;
- raw payload allocation/access: `svx_payload_create`, `svx_payload_push_byte`,
  `svx_payload_size`, `svx_payload_get_byte`, and `svx_payload_destroy`;
- raw payload metadata: `svx_payload_kind`, `svx_payload_type_name`,
  `svx_payload_content_type`, `svx_payload_unified_type_name`,
  `svx_payload_encoding_fingerprint`, `svx_payload_binary_format_version`, and
  `svx_payload_set_encoding_descriptor`.

Generated typed channel helpers (`svx_put_<Type>`, `svx_get_<Type>`, and
`svx_try_get_<Type>`) are stable application adapters. Their internal validation
helpers, channel registry/classes, cancellation-aware DPI variants, process
manager/enums, field envelopes, raw inheritance create/invoke/release gateways,
and all remaining package implementation symbols are private. Resource-limit
constants describe fixed runtime limits, not per-user configuration controls.

The complete support-package declaration inventory below is checked against
the package syntax. A private symbol does not become supported merely because
it can be imported from `svx_pkg`.

`SVX_GET_OBJECT` is experimental and paired with `publish_object`.
`SVX_PY_PROXY` is a source-discovery marker with no runtime expansion; it is
not an executable proxy or a standalone generated-code replacement. Its use
must follow the supported staged-generation workflow. Include guards are not
application interfaces; `svx_signal.sv` is a compatibility include with no
signal dispatcher.

For a Python-owned constructible root, the generated public package also exposes
`<Class>Factory#(Implementation)`. Application startup constructs one instance
after `svx_init()` and before Python constructs the paired object. The selected
SV class extends the generated Proxy and provides `new(object_id, ...arguments)`:
the opaque ID is forwarded to `super.new`, not allocated or bound by application
code. The generated factory handles typed request decoding and registry setup.
Select one implementation for each Python root per run. `<Class>Factory` is a
reserved helper name in that generated package; conflicting projected names
are rejected. This public implementation-selection helper is distinct from
the private `svx_factory` interface and registry operations.

## Compatibility

SVX 1.x accepts inheritance manifest major 2, generator ABI 2, and generated
artifact manifest major 1. It rejects incompatible Python/native/SystemVerilog product or runtime ABI,
generator ABI, manifest major, SvTypes major, formal capability names, encoding descriptor,
or generated file hash before dispatch.

The current function/task gateway implementation uses runtime ABI 3. Upgrade
the native library and SV support files together and regenerate bridge artifacts;
ABI 1 native libraries and compatibility artifacts are rejected at initialization.

The generated artifact manifest keeps `classes` as the explicitly requested
target IDs. Its `generated_types` table also includes actual ancestor bridge
types needed by those targets, with their public Python/SV qualified names.
Callable and constructor records cover lineage declarations, and `types`
includes field codecs as well as argument/result codecs for startup validation.
This metadata coverage does not generate user ancestor classes or change the
target list. Request/response record names and return slots remain private ABI;
applications return ordinary Python values rather than constructing records.

Raw payload APIs are untyped integration facilities. They do not define the
wire contract of typed channels, inheritance calls, or hierarchical access.

## Support-Package Declaration Inventory

SV visibility does not imply a supported application interface. Members of
private classes inherit their private classification.

### Package Declarations

| Classification | Group | Symbols |
|---|---|---|
| Stable | Lifecycle | `svx_init`, `svx_init_with_signal_declarations`, `svx_load`, `svx_start`, `svx_run_test`, `svx_shutdown` |
| Stable | Raw channels | `svx_channel_put_payload`, `svx_channel_get_payload`, `svx_channel_peek_payload`, `svx_channel_try_put_payload`, `svx_channel_try_get_payload`, `svx_channel_put_bytes`, `svx_channel_put_byte_queue`, `svx_channel_try_put_bytes`, `svx_channel_try_put_byte_queue` |
| Stable | Payload conversion | `svx_payload_from_bytes`, `svx_payload_from_byte_queue`, `svx_payload_to_byte_queue` |
| Stable | Payload allocation and access | `svx_payload_create`, `svx_payload_push_byte`, `svx_payload_size`, `svx_payload_get_byte`, `svx_payload_destroy` |
| Stable | Payload metadata | `svx_payload_kind`, `svx_payload_type_name`, `svx_payload_content_type`, `svx_payload_unified_type_name`, `svx_payload_encoding_fingerprint`, `svx_payload_binary_format_version`, `svx_payload_set_encoding_descriptor` |
| Fixed Limit | Resource bounds | `SVX_MAX_FORK_NUM`, `SVX_CHANNEL_CAPACITY`, `SVX_MAX_PAYLOAD_BYTES` |
| Private | Runtime metadata | `SVX_SV_RUNTIME_ABI_VERSION`, `SVX_SV_PRODUCT_VERSION` |
| Private | Runtime DPI imports | `svx_runtime_init`, `svx_runtime_init_with_signal_declarations`, `svx_runtime_load`, `svx_runtime_start`, `svx_runtime_shutdown`, `svx_runtime_abi_version`, `svx_runtime_state_name` |
| Private | Process types | `svx_process_manager`, `svx_proc_man`, `e_proc_state`, `e_svx_fork_join_type`, `e_svx_time_unit` |
| Private | Process implementation | `svx_process__exec`, `svx_process__set_svobj_idx`, `set_proc_index`, `start_process`, `proc_status_svx`, `kill_proc_svx`, `request_cancel_proc_svx`, `await_proc_svx`, `delay_svx`, `fork_svx` |
| Private | Enum members | `FINISHED`, `RUNNING`, `WAITING`, `SUSPENDED`, `KILLED`, `NOT_CREATED`, `REMOVED`, `FORK_JOIN`, `FORK_JOIN_ANY`, `FORK_JOIN_NONE`, `SVX_TIME_S`, `SVX_TIME_MS`, `SVX_TIME_US`, `SVX_TIME_NS`, `SVX_TIME_PS`, `SVX_TIME_FS` |
| Private | Channel storage and cancellation | `svx_channel`, `svx_channel_registry`, `svx_channel_put_payload_cancelable`, `svx_channel_get_payload_cancelable`, `svx_channel_peek_payload_cancelable` |
| Private | Generated payload validation | `svx_require_svtypes_payload`, `svx_require_svtypes_wire_payload`, `svx_payload_to_checked_byte_queue`, `svx_require_unpacked_all` |
| Private | Object and session interfaces | `svx_dispatchable`, `svx_function_dispatchable`, `svx_static_function_dispatchable`, `svx_static_dispatchable`, `svx_factory`, `svx_external_handle`, `svx_session_resource` |
| Private | Object registries | `svx_object_id_allocator`, `svx_external_handle_registry`, `svx_inheritance_registry` |
| Private | Staged construction context | `svx_construction_frame`, `svx_construction_context`, `svx_constructor_cache`, `svx_constructor_cache_registry` |
| Private | Field envelopes | `svx_field_operation`, `svx_field_take_u32`, `svx_field_take_bytes`, `svx_field_operation_unpack` |
| Private | Object dispatch and lifecycle | `svx_create_object`, `svx_create_object_function`, `svx_invoke_object`, `svx_invoke_object_function`, `svx_invoke_static`, `svx_invoke_static_function`, `svx_release_object`, `svx_release_object_function`, `svx_publish_object`, `svx_require_published_object` |
| Private | Inheritance DPI imports | `svx_inheritance_call_python`, `svx_inheritance_call_python_function`, `svx_inheritance_shutdown`, `svx_inheritance_release_python`, `svx_inheritance_release_python_function`, `svx_inheritance_create_python`, `svx_inheritance_create_python_function` |
| Private | Fatal reporting implementation | `svx_fatal_svx` |

Stable raw payload calls are untyped integration facilities, not a second typed
wire protocol. Fixed limits describe runtime bounds; do not override them
independently of the matching native runtime.

### Generated Interfaces

This inventory covers the support package, not manifest-dependent names.
Generated public classes, typed channel adapters, and implementation-selection
factories are classified in [the API reference](SVX_API_REFERENCE.md).
Their registration, request/response records, field endpoints, and raw dispatch
methods are private generated ABI even when SV makes them accessible.

`SVX_GET_OBJECT` is an experimental application macro. `SVX_PY_PROXY` is a
source-discovery declaration marker, not a runtime bridge. Include guards and
internal macro expansion names are not application interfaces.

## Manifest Field Inventory

The table below inventories the current inheritance-manifest parser, not a
claim that every accepted logical lineage is executable. Stable fields are
versioned by `schema_version` and `generator_abi_version`; their values and
cross-field rules remain subject to validation. Unknown keys are rejected.
Canonical SvTypes identity objects are validated by SvTypes, not by a second
SVX type schema.

| Object | Classification | Accepted Fields | Rules |
|---|---|---|---|
| root | Stable | `schema_uri`, `schema_version`, `generator_abi_version`, `required_runtime_capabilities`, `classes`, `discovery_provenance` | The first five fields are required; classes contains only explicit generation targets. Optional discovery_provenance requires validated file-backed evidence. |
| class | Stable | `canonical_id`, `language`, `symbol`, `methods`, `constructor`, `specialization`, `fields`, `base_lineage` | ID, language and symbol required; methods, fields and lineage default empty; constructor and specialization optional. Lineage entries cannot contain base_lineage. |
| method | Stable | `canonical_id`, `name`, `parameters`, `return_type`, `return_handle`, `timing`, `virtual`, `pure_virtual`, `static` | ID, name, return_type, timing and virtual required; parameters default empty; pure_virtual and static default false; return_handle optional. |
| parameter | Stable | `name`, `type`, `direction`, `handle` | Name and type required; direction defaults input independently for each parameter; handle optional. ref and const ref rejected. |
| field | Stable | `name`, `type`, `handle` | Name and type required; optional handle uses the same static endpoint metadata as parameters. Initialization and policy metadata are not implemented in this field shape. |
| constructor | Stable | `initiator`, `parameters` | Initiator required, python or sv; parameters default empty and must be input. This is not the planned per-ancestor ConstructionRequest. |
| type_binding | Stable | `unified_type_name`, `svtypes`, `python`, `sv`, `sv_packer`, `encoding_descriptor` | Exactly one of canonical svtypes or legacy python; other fields required. Identity and encoding are compared with the materialized codec. SV type/packer spellings receive character validation, not a semantic equivalence proof. The string void is accepted only in return positions. |
| encoding_descriptor | Stable | `unified_type_name`, `encoding_fingerprint`, `binary_format_version` | All required by comparison with the public SvTypes encoding descriptor. |
| python_factory | Legacy | `module`, `symbol`, `args`, `kwargs` | Module and symbol required; args and kwargs default empty. New source declarations emit canonical SvTypes identities. |
| handle | Stable | `kind`, `target_type_name`, `sv_type`, `operations` | First three required; kind is sv_class or virtual_interface. Operations default empty and are allowed only for virtual_interface. |
| vif_operation | Stable | `operation`, `member`, `method` | Required; operation is task, function, signal_read or signal_write. Method uses the method shape, with virtual and pure_virtual default false. |
| specialization | Stable | `arguments` | Nonempty ordered array; only an SV source class may specialize. |
| specialization_type_argument | Stable | `kind`, `type` | Required; kind is type and type is a non-void type binding. |
| specialization_value_argument | Stable | `kind`, `sv_type`, `value` | Required; kind is value, with normalized JSON scalar literal and concrete SV type. |

The discovery CLI automatically emits `discovery_provenance` and a sibling
`<manifest-name>.svx-discovery.json`; keep both files together. Its object has exactly
`schema_version` (`1.0.0`) and `path` (a canonical relative path, resolved from
the manifest directory). The referenced JSON record has exactly `schema_version`,
`contract_sha256`, `sources` and `configuration`. Each source has a canonical
relative `path` and lowercase SHA-256 `sha256`; resolved identities must be
unique and cannot include the manifest or the provenance record itself.
Discovery stages changed members of the pair before publication and attempts
rollback on handled publication errors. Successful rollback preserves existing
files and removes newly published members; incomplete recovery reports saved
originals. Matching files are not rewritten. This is not crash-atomic publication,
multi-writer locking, or a transaction covering all generated bridge artifacts.
Readers must validate the pair and reject transient missing or mismatched evidence.
`contract_sha256` binds the manifest content excluding the provenance reference,
using sorted compact ASCII JSON. Configuration records discovery options, not
generation targets or a simulator build recipe. Accepted configuration keys are
`python_modules`, `python_selections`, `python_namespaces`, `python_sources`, `sv_declarations`, `sv_sources`, `sv_dependencies`,
`sv_predefines`, `sv_undefines`, `sv_include_dirs` and `source_mode`.
Ordered sources/include paths and macro options are retained. Automatically
compiled ordinary user imports are recorded without an additional file list;
standard-library, framework and source-parser implementation imports are excluded
from that automatic user graph. Standard-library roots and module identities are
checked together: installed third-party packages and same-name user modules are
not excluded. Explicit source inputs retain their fingerprints and protection.
For source-scanned SV records, validation replays the stored source order,
include search paths, macros and compilation-unit mode and compares the selected
dependency identities, not only file contents. Adding a preferred include
candidate invalidates the record even when it has the same bytes as the old
header. This validation requires the `manifest` installation extra even if the
generation command does not repeat `--sv-source`. Older source-scanned records
without the selected dependency inventory require rediscovery; they are not
silently accepted as complete evidence.

`load_manifest(path)` and `inheritance-gen` validate referenced evidence before
class/codec-factory parsing. Missing evidence, source edits or contract mismatch
reject rather than falling back to a handwritten manifest. `parse_manifest`
requires `source_path` when this reference is present. CLI generation includes
the evidence and sources in final stability checks and input-overwrite protection.
File-backed API parsing also revalidates evidence after class materialization.
A manifest without the reference remains compatible but provides no discovery
evidence. Discovery checks both files read-only. A body-only edit makes the source
record stale; rediscovery refreshes it without rewriting a matching manifest.
Regeneration then refreshes artifact inputs without rewriting matching bridges.
An already-cached entry requires current prior discovery evidence, otherwise
use a fresh command process. This is not complete tracking of custom importers,
unaudited cached dependencies or external build inputs; keep the two-stage checks.
Ordinary imports from actively audited declaration sources reject cached helpers
without current prior discovery evidence; this includes `from`/relative imports
and `importlib.import_module()`. Valid prior evidence permits unchanged reuse.
Explicit source listing cannot prove which bytes produced cached definitions.
Use fresh command processes when rejected. Existing object references, custom
loaders and imports outside audited source execution are not fully certified.
`python_selections` records ordinary file-backed user modules as objects with
`module` and canonical relative `path`. Validation resolves their current filesystem
selection before class parsing, without running package initializers or trusting
cached module paths. Added preferred same-name modules invalidate the record even
when recorded source bytes are unchanged. Python-entry records without a selection
inventory require rediscovery. Use the application's current import paths for checks.
`python_namespaces` records participating namespace ancestors as objects with
`module` and ordered relative directory `paths` (where `.` denotes the manifest
directory). Validation compares package kind and ordered locations; adding an
initializer or changing namespace locations invalidates old evidence even if
the selected child source is unchanged. Older incomplete namespace evidence
requires rediscovery. This does not certify arbitrary custom importers, runtime
package-path mutations or external build inputs; keep the ordered two-stage checks.
Applications should not manufacture provenance records to certify old declarations.

Generated artifact manifests are generator/runtime validation metadata. Applications
may inspect their public type-name mappings but must not hand-author private
call records, fingerprints, paths or ownership inventories. Constructor records,
dispatch functions, registration helpers and field operation envelopes remain
private ABI; their names are not extension hooks. Applications must not allocate
or interpret bridge object IDs. The typed implementation-selection constructor
described above is the explicit exception for forwarding its opaque ID to
super.new; that documented forwarding does not expose registry or DPI APIs.
Use the generated public mirror/proxy classes and typed implementation-selection
factories instead. [Lineage status](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md) records
the design capabilities that are not yet executable.
