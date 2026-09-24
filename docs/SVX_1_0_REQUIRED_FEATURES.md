# SVX 1.0.0 Required Features

Status: stable release contract.

This document defines the stable `1.0.0` framework contract. It is based on the
simulator-hosted Python
runtime, SystemVerilog package, typed channels, manifest-driven cross-language
inheritance, and predeclared hierarchical signal access.

The goal is to make SVX a dependable integration foundation for long-lived
verification environments and for independently versioned consumers such as
UVMX. It is not to move the simulator kernel, hardware-facing testbench
structure, or UVM semantics into Python.

Normative terms `MUST`, `MUST NOT`, `SHOULD`, and `MAY` describe the intended
`1.0.0` contract. A feature is not stable until its implementation,
documentation, generated artifacts, and required simulator regressions agree.

## 1. Release Relationship With SvTypes

SVX `1.0.0` MUST depend on a released SvTypes `1.x` version and MUST consume
SvTypes only through its stable public APIs and installed runtime artifacts.
SvTypes is the sole contract for typed arguments, results, channel values,
constructor payloads, remote references, and hierarchical signal values.

The SvTypes release used to qualify SVX MUST provide all four prerequisites
identified by the SvTypes `1.0.0` contract:

| SvTypes prerequisite | Required SVX use |
|---|---|
| Generated call request and response types | The SVX manifest generator derives one concrete SvTypes request type and one concrete response type for every non-void constructor or method payload before SystemVerilog compilation. |
| `RemoteRef(target_type_name)` | Foreign class handles passed as arguments or results use this opaque codec; SVX owns lookup, type compatibility, and lifetime. |
| `CodecSession`, `PackContext`, and `UnpackContext` equivalents | Every call or channel operation uses isolated operation state within an explicit simulation/session lifetime and remains correct during nested callbacks. |
| `EncodingDescriptor` and runtime capability descriptors | SVX preserves and checks unified type names, encoding fingerprints, and the public `RuntimeCapabilities` fields before decoding or dispatch. SVX 1.0 requires `package_major_version=1`, `schema_format_version=1`, `binary_format_version=1`, `object_envelope_version=2`, `generator_runtime_abi_version=1`, and the four capabilities below. |

The SvTypes `runtime_capabilities()` capability names required by SVX 1.0 are:

- `svtypes.checked-encoding-descriptor.v1`
- `svtypes.codec-context.v1`
- `svtypes.record-schema.v1`
- `svtypes.remote-reference.v1`

SVX MUST NOT:

- evaluate arbitrary Python codec expressions from a manifest;
- inspect private SvTypes attributes or registries;
- generate handwritten Python source merely to create data schemas;
- reproduce SvTypes unified type names, encoding fingerprints, or binary formats;
- add an SVX scalar, tuple, object, or four-state serialization format; or
- use SvTypes graph-object IDs as SVX foreign-object IDs.

SvTypes may be released and used without SVX. SVX owns all simulator and
cross-language behavior described below.

For channels and generated call request/response values, SVX MUST NOT maintain
a hand-written whitelist of primitive type names. Any stable SvTypes type with
the required public descriptor and Python/SystemVerilog codec-generation
capabilities MUST be usable compositionally. Generation MUST reject a type
whose required backend or capability is unavailable. Hierarchical signal
access is deliberately narrower and accepts only the packed value subset
defined in Section 8.

SvTypes field/code-generation policies such as `rand`, `plusarg`, `dump`,
`cov`, and `pack_bytes`, its optional weak registry, and its standalone C++
generation remain SvTypes features. SVX MAY transport values produced by those
models but MUST NOT duplicate or reinterpret those policies as SVX runtime
features.

## 2. Ownership Boundary

SVX owns:

- embedded CPython startup, use, and deterministic shutdown;
- simulator-owned execution contexts, timing, and process delegation;
- DPI entry points and native simulator integration;
- Python export and test registration;
- named channel transport and blocking behavior;
- the cross-language inheritance manifest and its declaration front ends;
- mirror, proxy, dispatcher, and factory generation;
- foreign-object IDs, registries, lifecycle, and callback-cycle detection;
- hierarchical object lookup and read, write, force, and release operations;
- structured runtime errors, diagnostics, and compatibility checks.

SVX does not own:

- value normalization, schemas, codecs, encoding fingerprints, or data code
  generation provided by SvTypes;
- simulator time, event scheduling, or HDL process semantics;
- Python `asyncio`, thread, process, or subprocess scheduling;
- SystemVerilog interfaces, clocking blocks, drivers, monitors, or DUT binding;
- UVM factories, phases, objections, reporting, TLM, sequences, components, or
  configuration semantics; or
- APIs or adapters belonging to an independent UVMX project.

UVMX MUST be able to consume SVX through stable public Python, generated
SystemVerilog, and runtime contracts. SVX MUST NOT import UVMX or embed UVM
policy in its core runtime.

## 3. Current Baseline and Required Hardening

The preceding `0.1.0` implementation was the baseline; this release contract
defines the stable `1.0.0` behavior.

| Area | Current baseline | Required before `1.0.0` |
|---|---|---|
| Runtime | Embedded Python, DPI callbacks, execution contexts, shutdown entry point | One specified lifecycle/state machine, idempotent cleanup, capability handshake, ABI checks, and installed-artifact validation |
| Timing and processes | Delay and simulator-owned fork/join primitives | Frozen scheduling, cancellation, exception, handle, and teardown semantics with nested-callback coverage |
| Channels | Raw payloads and typed SvTypes object helpers | Wire-descriptor checks, complete type-family coverage claimed by SVX, operation-scoped codec contexts, and lifecycle/resource limits |
| Cross-language inheritance | Generated proxies in both directions, typed calls, factories, base calls, and cycle rejection | Public manifest schema, safe type references, generated request/response data classes, all supported parameter directions, `RemoteRef`, compatibility handshake, and full lifecycle/error qualification |
| Hierarchical access | Predeclared packed-object read, write, force, and release | Public capability contract, exact SvTypes mapping including four-state behavior, startup-wide validation, direct native VPI integration, and teardown qualification |
| Packaging | Python package, SV sources, and CMake native build | Reproducible sdist/wheel plus native/install artifacts, version agreement, clean consumer build, and supported-toolchain qualification |

Prototype milestone names and internal helper entry points are not themselves
public API. Every public symbol and generated contract MUST be deliberately
classified before release.

## 4. Runtime and Lifecycle Contract

### 4.1 Runtime states

The native runtime MUST expose one deterministic state machine equivalent to:

```text
uninitialized -> initializing -> ready -> shutting_down -> stopped
```

Initialization MUST:

1. load the embedded interpreter and public SVX runtime;
2. compare SVX Python, native, SystemVerilog, generator, manifest, and SvTypes
   capability versions;
3. create the simulation-scoped registries and SvTypes codec session;
4. load and validate all configured generated artifacts and declarations;
5. validate every predeclared hierarchical path; and
6. enter `ready` only after all checks succeed.

No user test, exported callback, channel transaction, inheritance factory, or
signal operation may run before initialization completes. A failed
initialization MUST roll back partial registries and report all actionable
compatibility or declaration failures available at that point.

Shutdown MUST reject new work, deterministically resolve or fail active work,
report leaked foreign instances and active forces, clear signal, inheritance,
channel, process, export, and SvTypes session state in a defined order, and
finalize Python only after Python-owned references have been released. Repeated
shutdown calls MUST be harmless. Handles retained after shutdown MUST fail as
stale and MUST NOT attach to a later session.

### 4.2 Execution context

An SVX execution context exists only while the simulator enters Python through
an SVX-managed path. Contexts MUST be stack-based so a legal nested callback
restores the outer context. Every simulator-facing Python API MUST reject calls
without an active context using `SVXContextError`.

Python threads, `asyncio`, multiprocessing workers, subprocesses, and native
host threads MAY perform host-only computation but MUST NOT call SVX timing,
process, channel, inheritance, or hierarchical-access APIs.

### 4.3 CPython and native boundary

SVX `1.0.0` uses one interpreter per simulator process. Every native entry to
Python MUST acquire and restore the correct interpreter/thread state, preserve
nested entry, and convert exceptions without leaking Python references. The GIL
does not provide simulation concurrency; simulator processes remain the only
source of simulator-visible parallelism.

The Python package, native library, and SystemVerilog runtime MUST expose
compatible version/capability constants. Initialization MUST reject a mixed
installation rather than continue with undefined ABI behavior.

## 5. Stable Python and SystemVerilog Core

### 5.1 Exports and tests

Python callables entered from SystemVerilog MUST be explicitly registered with
`@svx.export` or `@svx.test`. The stable identity is the qualified export name;
arbitrary import-path reflection is not a runtime dispatch mechanism.

The public contract MUST define duplicate registration, module reload, missing
export, signature validation, exception, and shutdown behavior. Test execution
MUST report the qualified test identity and full Python traceback. User test
discovery and simulator startup configuration MUST be usable from installed
packages rather than requiring a source checkout.

### 5.2 Timing primitives

SystemVerilog remains the sole owner of simulation time. `svx.delay()` MUST
delegate to a simulator task, use a documented unit and rounding contract, and
return only after the requested simulator delay completes. It MUST reject
invalid values, unsupported units, overflow, and use outside an execution
context.

SVX MUST NOT expose Python `async`/`await` as a timing model or silently use
wall-clock sleep for simulation behavior.

### 5.3 Process primitives

`fork_join`, `fork_join_any`, and `fork_join_none` MUST create
simulator-scheduled child callbacks, not Python threads. Their stable contract
MUST define:

- child start ordering and the point at which each call may return;
- completion and result ordering;
- exception propagation under every public error policy;
- remaining-child behavior after `fork_join_any`;
- process/group states and legal transitions;
- `await`, status, kill, repeated-kill, and stale-handle behavior; and
- shutdown behavior for active and completed children.

Each child callback receives its own stacked SVX execution context. Exceptions
and cancellation MUST NOT corrupt sibling or parent contexts.

### 5.4 Error policy and diagnostics

The public exception hierarchy MUST remain small and structured. Errors crossing
the native boundary MUST carry a stable error-domain/code plus relevant
qualified export, class, method, object, channel, or hierarchy identities.
Remote Python failures MUST preserve the traceback and call identity.

Fatal and report behavior MUST be deterministic. An operation returning a value
MUST never fabricate a default value after a remote failure. Generated adapters
MUST propagate a structured failure or terminate according to the configured
policy.

## 6. Typed Channels

SVX `1.0.0` MUST retain named blocking and nonblocking channel operations and
the request, response, monitor, configuration, and request/response role
helpers. The channel name is the runtime rendezvous identity; role wrappers do
not create a second queue or data model.

Typed channel values MUST be complete SvTypes payloads. Every payload metadata
record MUST carry the SvTypes unified type name, encoding fingerprint, and binary
format version from its public `EncodingDescriptor`. A receiver MUST use checked
decode and reject a mismatch before mutating a target value.

Packing and unpacking MUST use a new operation context inside the current
simulation-scoped SvTypes codec session. Nested channel use from a callback
MUST NOT clear or corrupt an active inheritance or channel codec operation.

The channel contract MUST define:

- creation and first-use rules for a name;
- type binding and conflicting-type diagnostics;
- `put`, `get`, `peek`, `try_put`, and `try_get` ownership semantics;
- behavior for null, graph, collection, and `RemoteRef` values where their
  declared SvTypes codec permits them;
- queue capacity/resource limits and shutdown cleanup; and
- ordering and wake-up behavior observable by simulator processes.

An opaque raw-byte payload API MAY remain public for untyped integration, but
it MUST be labeled untyped and MUST NOT masquerade as the argument/result
contract of a typed SVX API.

Payload movement across DPI is an SVX implementation detail. A bulk transfer
optimization MUST preserve the exact SvTypes bytes and descriptors and MUST NOT
change the user data contract.

## 7. Cross-Language Inheritance

Cross-language inheritance is a core `1.0.0` feature. It uses generated local
mirrors and proxies; it does not claim that one Python object and one
SystemVerilog class handle are physically the same object.

```text
foreign base <-> generated same-named local mirror <-> SVX dispatch <-> local derived instance
```

### 7.1 Manifest as the runtime contract

The versioned SVX inheritance manifest MUST be the only declaration contract
seen by the inheritance generator and runtime. Users MAY author it directly,
generate it from public Python decorators/declarations, or generate it from
explicit SystemVerilog declaration metadata. All front ends MUST normalize to
the same deterministic manifest and diagnostics.

The manifest MUST contain:

- its schema URI and semantic version;
- canonical class, method, constructor, and generated namespace identities;
- owning language, direct source base, and the complete root-to-parent linear
  `base_lineage` needed to validate a generated projection;
- ordered parameter names, directions, SvTypes unified type names, and encoding
  descriptors;
- method result type, timing classification, virtual/pure-virtual state, and
  callable visibility;
- constructor initiator and ownership policy; and
- generator/runtime capability requirements.

`base_lineage` contains full declarations for ancestors but is not itself a
generation request: only top-level `classes` are emitted. A parameterized SV class is a
distinct target only after all parameters are closed: its manifest carries an
ordered `specialization` whose type arguments are full concrete SvTypes type
bindings and whose value arguments are normalized JSON literals with their SV
type. Open type parameters, macro/localparam-dependent expressions, and two
different class IDs for the same normalized specialization are generation
errors.

A manifest that declares any projected field, including one in its expanded
lineage, MUST require `svtypes.external-field-storage.v1`. A methods-only
inheritance manifest does not acquire that capability requirement.

Manifests MUST refer to registered SvTypes schemas or unified type names. They
MUST NOT contain executable codec expressions. Unknown fields, unsupported
versions, duplicate identities, generated-name collisions, incompatible
overrides, unavailable types, or capability mismatches MUST fail generation.

Schema migration tooling MAY upgrade an older supported manifest, but runtime
dispatch MUST never silently reinterpret an incompatible major version.

### 7.2 Generated mirrors and naming

For an SV-owned class such as `XxxxClass`, SVX MUST be able to generate a
Python mirror also named `XxxxClass` in an isolated generated module. For a
Python-owned class, it MUST generate an SV mirror with the same simple name in
an isolated generated package. Runtime lookup always uses canonical IDs, never
the simple name.

A normal local subclass of the mirror MUST be able to:

- inherit non-overridden declared foreign methods;
- override any declared virtual method supported by the manifest;
- invoke the real foreign base implementation through the language's normal
  base-call form, including Python `super()`; and
- be passed locally through a reference of the generated/foreign base type.

Both directions are required: Python derived from an SV base and SV derived
from a Python base. The generated artifacts MUST use deterministic names,
contain provenance and compatibility metadata, and reject collisions before
compilation.

### 7.3 Typed call shape

Every constructor or method call transports:

```text
SVX call metadata + one SvTypes request value -> one SvTypes response value + structured SVX status
```

SVX call metadata contains only protocol version, call ID, foreign-object ID,
canonical class/method ID, lifecycle state, and structured error metadata. The
request and response data classes and their bytes are owned by SvTypes.

The generated request/response mapping MUST support declared `input`, `output`,
and `inout`, plus a function result. `output` and `inout` are completion-time
copy-out encoded through SvTypes. A manifest MUST reject `ref` and `const ref`:
the inheritance protocol does not transport SV lvalue aliases. A member that
requires SV ref semantics remains entirely in handwritten SystemVerilog.
Applications may define an explicit mutable protocol with SvTypes objects or
getter/setter methods, but it is not an SVX ref facility.

An SV source method declared as static MUST be represented by a generated
Python `@staticmethod` and a class-level SV dispatcher. The dispatcher MUST
not allocate a foreign object or require an object ID. Static and `virtual` are
mutually exclusive; Python name shadowing remains ordinary local Python lookup
and MUST NOT alter the SV static implementation.

Generated Python APIs MUST expose a documented response data class when
copy-out values exist; generated SV APIs retain declared SV directions and
perform checked post-call extraction.

Zero-data requests or responses use the SvTypes void contract. Primitive,
enum, string, collection, struct, object graph, and nullable values are
supported only when their declared SvTypes codec is supported by every
generated backend used by the call.

SVX consumes the public SvTypes record builder as
`RecordSchema(unified_type_name, fields, class_name=...)`, where `fields` is an
ordered tuple of `(name, codec)` pairs. `build()` returns the generated
`SvObject` type; its instances use the standard public field-value and
operation-context pack/unpack behavior. The same type supplies the generated
SystemVerilog declaration and encoding descriptor. SVX does not inspect a private
registry or generate an independent record serializer.

Generated record IDs are deterministic: the lowercase SHA-256 digest of the
complete canonical method ID is placed in
`svx.call.<digest>.request` or `svx.call.<digest>.response`. A void side has no
record. The generated artifact manifest records these IDs and the ordered
field mapping before compilation.

### 7.4 Foreign-object references

A foreign class instance passed as an argument or result MUST use the declared
`RemoteRef(target_type_name)` codec. SVX resolves its immutable 64-bit ID in the
current inheritance registry and verifies that the bound concrete class is the
declared target or a manifest-known derived class.

Object ID `0` represents null. Nonzero IDs are scoped to one initialized SVX
session and MUST NOT be reused while a stale reference can remain valid. A
`RemoteRef` carries no ownership; receiving one does not extend lifetime unless
the manifest/API explicitly creates a retained local proxy. Unknown, closed,
wrong-type, or previous-session IDs MUST fail before method dispatch.

SvTypes `SvObject` graph identity remains separate. A by-value data object that
contains a `RemoteRef` may be transported, but its graph registry does not own
the referenced foreign runtime object.

### 7.5 Dispatch and scheduling

Dispatch is generic over manifest-declared class and method IDs, not over
simulator reflection. Generated adapters perform direct typed method calls.
Only methods declared in the manifest are callable; arbitrary lookup or
invocation of an SV class method by hierarchy or string is not part of the
contract.

Methods classified as timing-capable MUST use simulator task transport and may
consume simulation time. Methods classified as functions MUST be nonblocking
and MUST be rejected if their generated path can suspend. A Python call into a
foreign method requires an active SVX execution context.

A Python callback entered from SystemVerilog is always a synchronous ordinary
Python call. It MUST NOT be an `async def`, return an awaitable, or use an
`asyncio` scheduling path. The dispatcher detects a coroutine function or
awaitable return, invalidates the active call frame, reports the call identity,
and terminates simulation under the fatal callback policy. SVX timing remains
driven only by its simulator-owned primitives and task transport.

Ordinary nested crossings and generated base calls MUST work. The runtime MUST
track the complete active call stack. Re-entry into an already active
foreign-object/method frame, directly or through multiple frames, MUST be
rejected as a callback cycle with the repeated path in the diagnostic. Cycle
rejection MUST unwind without leaking a call, codec operation, registry entry,
or execution context.

### 7.6 Construction and lifetime

Each constructible pair has one declared initiator. Construction follows
`ALLOCATED -> SV_CONSTRUCTED -> BOUND -> PY_INITIALIZED -> ACTIVE`; foreign
virtual calls before `ACTIVE` are illegal. A generated factory MUST allocate
the SVX object ID, construct both sides, bind both registry entries, and run
the Python initialization hook atomically. For an SV-originated construction,
the generated constructor/template performs ordinary SV construction and calls
`svx_post_construct()` at the explicit end of that construction path; SVX
cannot safely infer the end of an arbitrary handwritten `new C(...)`.
Failure before `ACTIVE` unbinds projected fields and both SVX registry entries,
marks the ID aborted, and invalidates all generated views. It does not claim to
destroy a user-owned SV handle for which SystemVerilog has no deterministic
destructor hook.

The initiating side owns explicit close. A Python-initiated pair owns its
Python object and its internal SV companion; an SV-originated `new C` remains
owned by the SV caller and has a borrowed Python companion. `RemoteRef` never
transfers ownership. An existing unbound SV handle may become a mirror only by
an explicit `svx.adopt_instance(target, handle)` operation, which binds an
uninitialized mirror view without calling Python `__init__`; automatic dynamic
type guessing is forbidden. Close MUST reject new calls, define the treatment
of in-flight calls, remove both bindings, release retained Python references,
and make all proxies stale. Python garbage collection MUST NOT be the
correctness mechanism for a live SV proxy. Shutdown performs deterministic
registry cleanup and reports unclosed pairs.

`1.0.0` supports a single linear inheritance chain with repeated alternating
language boundaries, for example `A(SV) -> B(Python) -> C(SV) -> D(Python)`.
It emits only required `AMirror`, `BProxy`, `CMirror`, and `DProxy` portions;
it never generates every ancestor just because it appears in lineage context.
Cross-language multiple inheritance, Python mixins in a generated lineage,
method overloads, undeclared members, field hiding, open parameterized classes,
and direct synchronization of arbitrary foreign attributes are rejected at
generation time.

## 8. Hierarchical Signal Access

SVX `1.0.0` MUST provide small-scale, temporary access to explicitly declared
whole packed HDL objects through `read`, `write`/deposit, `force`, and
`release`. This is a control and diagnostic facility, not a Python driver,
monitor, waveform, or bulk-access architecture.

Every possible path used by a test MUST be present in a static signal
declaration artifact or declaration module configured for initialization.
Initialization MUST register, resolve, type-check, and report all invalid paths
before any user test or export runs. The registry seals after successful
validation. Dynamic declaration, lazy first-use lookup, wildcards, and hierarchy
enumeration are not supported.

Each declaration binds one path to a public SvTypes encoding descriptor. SVX MUST
validate width, signedness, state domain, and supported VPI object kind. Reads
and writes MUST use the SvTypes codec without a parallel scalar format. If the
declared codec cannot represent an observed `X` or `Z`, the operation MUST fail;
it MUST NOT coerce the value to two-state data.

The Python binding calls the native C/C++ VPI service directly while already
inside a simulator-owned DPI context. The service is built as part of the
simulator-loadable SVX runtime configuration. It MUST NOT require a VPI system
task, a separately loaded VPI application, or a C-to-SV-to-DPI return bridge.

Operations are synchronous at the current simulator scheduling point and add no
user-visible time. Force ownership is explicit: garbage collection does not
release a force, and shutdown reports active forces without pretending to
restore external driver ownership.

Memories, unpacked/dynamic arrays, queues, class properties, events, background
watches, edge callbacks, polling, bulk reads, and vectorized high-rate access
are excluded. Large-scale or timing-intensive signal interaction remains in
raw SystemVerilog and communicates summarized or transactional data through
SVX channels.

## 9. Generation, CLI, and Installed Artifacts

SVX MUST provide public generation commands/APIs for inheritance artifacts,
SvTypes call data types, typed channel helpers, and static signal declarations
where generation is used. Generation MUST be deterministic, validate all
inputs before writing, and provide an atomic write/check mode plus a structured
result manifest.

Generated artifacts MUST record:

- SVX generator, manifest schema, and runtime ABI versions;
- the required SvTypes package, schema, binary format, object-envelope, and
  generator/runtime ABI versions;
- canonical class/method IDs, unified type names, and encoding fingerprints;
- source declaration provenance; and
- hashes of generated files needed for stale-output detection.

Generation MUST finish before SystemVerilog compilation. A normal user MUST
not handwrite or commit generated request/response types. Build-directory
artifacts are supported and MUST be reproducible from committed declarations.

The installed Python package MUST locate its installed SystemVerilog and native
runtime inputs through stable public CLI/API discovery. Source-checkout paths,
sibling repositories, and local simulator scripts MUST NOT be required by an
installed consumer.

## 10. Public API and Compatibility Policy

Before `1.0.0`, every name exported by `svx.__init__`, every CLI command, every
public SystemVerilog symbol, every manifest field, and every generated adapter
entry point MUST be classified as stable, experimental, migration-only, or
private. Stable behavior includes error types and lifecycle semantics, not only
function names.

After `1.0.0`:

- patch releases MUST preserve stable APIs, manifest interpretation, generated
  ABI, and behavior;
- minor releases MAY add backward-compatible APIs, manifest fields, and
  capabilities;
- incompatible public API, manifest, generated ABI, or runtime protocol changes
  require a new major version;
- deprecated stable APIs remain documented for at least one minor-release
  cycle; and
- incompatible generated artifacts or SvTypes capabilities MUST be rejected at
  initialization with both expected and actual versions.

Python and native version metadata MUST match package metadata. The supported
Python, C++, SystemVerilog, DPI, VPI, and simulator capability requirements
MUST be documented without promising an unqualified implementation.

## 11. Packaging and Release Artifacts

The release candidate MUST provide:

- an sdist and wheel containing the Python package and all public SV support
  sources;
- a reproducible native CMake build/install path for the simulator-loadable
  runtime and its direct VPI service;
- installed-resource discovery that works outside the source tree;
- license, changelog, migration guide, user manual, API reference, and complete
  examples;
- no generated simulator products, local paths, credentials, or internal test
  harnesses in release artifacts; and
- an explicit compatible SvTypes `1.x` dependency range whose release
  artifacts have passed the SVX compatibility gate.

A clean consumer environment MUST be able to install SvTypes and SVX, generate
required build artifacts, compile the runtime and SV sources, and run the
published examples without referring to either repository checkout.

## 12. Explicit Exclusions

The following are not part of SVX `1.0.0`:

- ownership of any UVM semantic layer;
- Python `async`/`await` or host-native concurrency as simulation concurrency;
- a Python simulator scheduler;
- generic reflective invocation of undeclared SystemVerilog tasks or class
  methods;
- cross-language multiple inheritance, non-linear language crossings, or an
  alternating chain whose complete lineage is not declared;
- automatic synchronization of Python attributes and SystemVerilog class
  fields;
- overload resolution for foreign methods;
- dynamic or bulk hierarchical object access;
- high-rate Python signal monitoring or driving;
- post-silicon execution; and
- runtime support claims for an unqualified simulator/toolchain.

These exclusions do not prevent independently versioned projects from building
higher-level behavior on stable SVX and SvTypes APIs.

## 13. Verification Requirements

### 13.1 Python and native tests

The release test suite MUST cover:

- initialization state transitions, rollback, repeated shutdown, and stale
  handles;
- nested execution contexts, context rejection, GIL/reference cleanup, and
  each public error policy;
- delay validation and every fork/join lifecycle transition;
- channel type binding, descriptor mismatch, nulls, collections, graphs,
  `RemoteRef`, resource limits, and nested codec operations;
- inheritance manifest parsing, declaration front ends, deterministic
  generation, migration, name collisions, and stale artifacts;
- both inheritance directions, local overrides, inherited methods, base calls,
  both constructor initiators, all parameter directions, results, exceptions,
  close, shutdown, legal nesting, and rejected cycles; and
- signal declaration sealing, batched startup errors, type/state mismatch,
  stale handles, and force tracking.

Native sanitizers or equivalent checks MUST cover owned payloads, process
handles, Python references, foreign registries, and shutdown paths where the
qualified toolchain supports them.

### 13.2 Simulator integration matrix

At least one qualified simulator configuration MUST verify the complete
release contract, not only compilation. The maintained matrix MUST cover:

- embedded Python startup, exports, exceptions, delay, and all fork/join modes;
- typed blocking/nonblocking channel exchange with canonical-byte parity;
- generated inheritance in both directions, typed request/response payloads,
  `RemoteRef`, timing-capable overrides, base dispatch, lifecycle, and the
  negative callback-cycle regression;
- startup validation and packed signal read, write, force, release, four-state
  behavior, invalid paths, and teardown; and
- deliberate mismatches of every SVX and SvTypes capability/version field.

The SystemVerilog and Python regression sources that define claimed behavior
MUST be versioned with the project.

### 13.3 Artifact and compatibility tests

The release candidate MUST pass:

- Python tests against every supported Python version;
- a clean native configure, build, install, and downstream consumer build;
- sdist and wheel inspection plus installation tests;
- deterministic regeneration and stale-output detection;
- compilation of generated SV and C++ data artifacts supplied by SvTypes;
- the complete simulator matrix from installed artifacts;
- cross-version rejection tests for Python/native/SV/generated components; and
- an integration gate against the intended released SvTypes version.

Performance measurements MUST record inheritance call overhead, object-bearing
payload transfer, channel transfer, and repeated signal access for regression
detection. They are not permission to use hierarchical access as a bulk data
path.

## 14. Required Implementation Sequence

### Stage 1: Contract and API audit

- Classify all current Python, SystemVerilog, CLI, native, manifest, and
  generated surfaces.
- Reconcile the project specification, user manual, milestone documents, and
  actual implementation.
- Freeze ownership, lifecycle, execution-context, scheduling, and error rules.

### Stage 2: SvTypes 1.0 integration

- Replace executable manifest codec expressions with canonical public schema
  references.
- Generate concrete request/response types through public SvTypes APIs.
- Adopt `EncodingDescriptor`, runtime capability, checked decode, `RemoteRef`, and
  operation-scoped codec sessions everywhere typed data crosses SVX.
- Add initialization-time SvTypes and generated-artifact compatibility checks.

### Stage 3: Core runtime and channel hardening

- Implement and test the runtime state machine and deterministic teardown.
- Complete execution-context, GIL, process, cancellation, and error behavior.
- Freeze channel binding, ownership, resource, descriptor, and shutdown rules.

### Stage 4: Inheritance completion

- Add manifest generation from supported Python and SV declaration front ends.
- Complete all parameter directions and generated response APIs.
- Add `RemoteRef` arguments/results and declared derived-type validation.
- Qualify construction rollback, base calls, timed calls, nested calls, cycles,
  close, and shutdown in both inheritance directions.

### Stage 5: Hierarchical access qualification

- Adopt the final public SvTypes width/signedness/state-domain descriptors.
- Integrate the native VPI translation unit into the installed runtime build.
- Qualify startup-wide path validation, direct native operations, four-state
  behavior, force lifetime, and teardown.

### Stage 6: Generation, packaging, and documentation

- Provide deterministic multi-artifact generation and stale-output checks.
- Test installed discovery and clean downstream builds.
- Update the specification, user manual, examples, migration guide, and API
  reference to the frozen contract.

### Stage 7: Release qualification

- Run the complete Python, native, artifact, compatibility, and simulator
  matrices from the release candidate.
- Run the SvTypes release-candidate compatibility gate in both repositories.
- Record performance baselines, resolve all release-blocking diagnostics, and
  verify the final source and binary artifacts.

## 15. Completion Criteria

SVX is ready for `1.0.0` only when all of the following are true:

1. A released SvTypes `1.x` satisfying the four prerequisites is available and
   the pinned compatibility range passes both projects' integration gates.
2. Python, native, SystemVerilog, manifest, generator, and SvTypes versions and
   capabilities are checked before user code runs.
3. All typed data paths use public SvTypes descriptors, checked decode, and
   operation-scoped codec state with no parallel SVX serialization format.
4. Runtime initialization, nested execution contexts, errors, and deterministic
   shutdown are specified and verified.
5. Delay and process primitives have complete simulator-owned scheduling,
   cancellation, failure, and stale-handle contracts.
6. Typed channels have stable type binding, ordering, ownership, resource, and
   shutdown behavior.
7. The manifest is the sole inheritance runtime contract and can be produced by
   the supported manual, Python, and SystemVerilog declaration front ends.
8. Same-named generated mirrors support local derivation, overrides, inherited
   methods, and real foreign base calls in both language directions.
9. Constructors and methods support their declared SvTypes request/response
   types, parameter directions, results, `RemoteRef` values, timing rules,
   errors, lifecycle, legal nesting, and cycle rejection.
10. Every declared hierarchical path is validated at initialization, and
    supported packed values pass read, write, force, release, four-state, and
    teardown tests through direct native VPI calls.
11. Public APIs, generated artifacts, compatibility policy, exclusions, user
    documentation, and examples agree with the implementation.
12. Clean installed-artifact, downstream-build, cross-version rejection, and
    complete simulator integration matrices pass from the release candidate.
13. No unresolved release-blocking defect, undocumented stable surface,
    simulator artifact, local-only path, or incompatible generated output
    remains in the release artifacts.
