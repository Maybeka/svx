# Cross-Language Handle Adapters

## Status

SVX generates these adapters as dependencies of a declared cross-language
method, constructor parameter, or native handle field. They complement, rather than replace, the mirror/proxy registry used
by generated inheritance objects.

## One Wire Contract

SvTypes `RemoteRef[target_type_name]` is the only value transferred across a
cross-language call for every foreign handle. Its payload is a nullable,
session-scoped `uint64` object ID. SVX does not introduce a parallel handle
serializer, expose a raw simulator pointer, or encode a VPI handle as data.

The ID is useful only together with its static target type. `0` means null.
Every non-null ID is resolved in SV immediately before a generated typed call;
an unknown, stale, or wrong-kind ID is a call failure.

Constructors reuse these typed endpoints: SV input formals retain their native
class/VIF types, private SvTypes request records encode RemoteRef values, and
generated factories resolve the native handles before invoking new. SV-initiated
Python initialization receives ordinary class RemoteRef values or generated VIF
views, not private request records. A VIF view with no declared operations can
be retained and passed onward but has no signal or method accessors.

## Unmapped SystemVerilog Class Handles

An SV class used only as a method/constructor parameter or return value need not be a
top-level cross-language inheritance target. The manifest generator discovers
that use and emits internal metadata plus one typed adapter for the static
SV type.

For a native SV class/VIF member, a manifest field includes `handle` metadata
with the same static target and SV type used for parameters. Python reads and
writes a SvTypes RemoteRef field; generated SV endpoints encode the actual
member on read and resolve the typed reference before assigning it on write.
Null references are supported, and invalid references leave the member unchanged.
VIF fields retain reference-value semantics rather than automatically replacing
the SvTypes field with a Python view. A plain RemoteRef field without `handle`
metadata remains an encoded value, not a native SV handle lvalue. Addressing
paths below a handle is rejected; referenced object members require their own
declared mapping.

```text
SV Packet handle
  -> generated Packet endpoint registry
  -> RemoteRef["sv://packet_pkg/Packet"]
  -> Python
```

The generated endpoint retains the actual `packet_pkg::Packet` handle, not a
numeric reinterpretation. Resolving the `RemoteRef` returns that declared
base handle, so a derived `SpecialPacket` remains legal through ordinary SV
polymorphism. A returned value is checked with `$cast` by the generated typed
adapter.

Python receives the normal SvTypes `RemoteRefValue`. It may retain it,
transport it through other supported SvTypes values, pass it back to a
compatible formal, or return it. It may not construct the SV object, invoke
its methods, or inspect its fields. Those require the class to be an explicit
cross-language generation target.

The adapter holds a simulator handle strongly until the SVX session is
cleared. This is deliberate: SV has no general portable destructor callback
that would let a non-owning registry detect that an arbitrary handwritten
object became unreachable. Generated resolution is therefore safe rather than
silently dereferencing a stale handle. A later explicit release API may reduce
retention, but it must never invalidate a handle in an active call.

## Collections Of Handles

Method parameters and results may use queues, dynamic arrays, fixed arrays,
and associative arrays of native SV class handles, including nested containers.
Their Python type is the corresponding SvTypes collection of
`RemoteRef["sv://package/Class"]`. The referenced class does not become an
additional generation target.

The generated boundary retains the native SV container type and converts each
element through the same scalar endpoint registry. Null elements, repeated
references to one object, empty containers, and associative keys are preserved.
`output` and `inout` use these same conversions; user method parameters are not
removed or reordered. No raw pointer or second container wire format is used.

The manifest's `handle` metadata describes the leaf target, while the SvTypes
type describes the complete container shape. Source typedefs remain the native
method types. A typedef is not required for a formal such as
`input Item values[$]`, `output Item result[string]`, or
`inout Item changed[]`; generated native aliases preserve its dimensions and
leaf class type, and source validation compares that native shape.
Internal call records do not generate coverage for reference
collections; this does not change coverage policy of user-declared fields.

Constructor inputs use the same per-element conversion. Native declarations
such as `new(input Item items[$], input Item groups[string][$])` retain their
ordered inputs when passed to a Python initializer or supplied by Python
construction. Invalid element IDs are rejected before the SV constructor body
runs; copying a container does not copy its referenced SV objects.

Native handle collection fields support whole-value read/set and addressed
index/key read/set, including a nested associative-array queue. An addressed
write converts only the selected native element or subcontainer, preserves
siblings, and rejects unknown IDs before assigning it. These fields retain
their SvTypes `RemoteRef` value representation; interface method views are not
substituted for stored field values.

Queue and dynamic-array fields also support addressed append, insert, deletion,
pop, and resize, including nested handle containers. New elements or entire
subcontainers are decoded before insertion; an unknown element ID leaves the
selected container unchanged. Resize preserves existing elements and grows
with native SV defaults (null handle or empty subcontainer). Negative lengths
are rejected. Associative deletion removes only the selected key. Fixed arrays
retain their fixed length; these structural operations do not make them queues.

SvTypes reference payloads contain only object numbers. An untagged reference
record created by SV collection unpacking obtains its static target from the
generated endpoint; the registry still rejects IDs belonging to another target.
An explicitly mismatched target label is also rejected.

VIF containers use the same element conversion. Python receives the generated
restricted view for each non-null element; null elements remain null references.
Nested lists, tuples, and associative values retain their shape when views are
encoded or decoded. `input`, `output`, and `inout` VIF containers preserve the
original interface instances.

A function returning an array of virtual interfaces requires backend support
for that SystemVerilog construct. SVX retains the declared return prototype;
it does not silently replace it with an output parameter. This requirement is
separate from the supported output/inout container path.

## Native Source Owners

Direct source export also handles native class references declared outside a
package: compilation-unit classes and classes owned by concrete module,
interface, program, or active generate instances. Select the API class with the
ordinary --class selector; a class used only as a handle remains unmapped.
For example, exporting tb.agent.Owner does not also export tb.agent.Item merely
because Owner has an Item member or an echo(Item) method.

The native class stays in its original scope. Generated endpoints retain that
actual native type; Python receives the same SvTypes RemoteRef values used for
package handles. Each concrete owner has its own target identity, including
distinct instances with equal parameters. Constructor inputs, static factories,
function/task parameters and returns, scalar fields, queues, and nested
string-keyed associative-array queues are qualified in these owner layouts.
Whole-value and addressed field updates preserve nulls, repeated references,
empty subcontainers, and sibling values. Unknown nested element IDs fail before
the native field is assigned. Python virtual overrides may receive and return
the same references through an original SV base handle.

The [shared SV test declarations](../tests/integration/scoped_handle_types.sv)
cover Owner and Consumer APIs without making Item a generation target.
Use the generated compile order/source replacements and the same explicit
svx_exports.initialize() startup described in the
[source export workflow](SVX_GENERATION_WORKFLOW.md#compilation-unit-classes).
Internal adapter names reversibly escape separators and underscores so distinct
types such as a_b::C and a::b_C cannot alias each other. Container deduplication
uses the target and SvTypes type identity, never that generated identifier.
Names also omit the duplicate leaf target inside the container suffix to keep
identifiers compact. These helpers are not public type names; regenerate them
with the CLI rather than hardcoding their spellings. Public mirror names,
target IDs, and wire schemas are unaffected.

Cross-owner native class type bindings and alternating cross-language owner
lineages still need additional placement support. Owner-local VIF support is
described below; package handle/VIF support is unchanged.
This handle-binding boundary is distinct from the supported
[lexically visible SV base classes](SVX_GENERATION_WORKFLOW.md#lexically-visible-sv-ancestors).

## Owner-Local Virtual Interfaces

Compilation-unit/module/interface/program/generate-owned API classes may also
declare native VIF constructor parameters, fields, function/task parameters,
returns, and output/inout formals. The interface type and modport come from the
original SV declaration; no separate mapping list or bind name is needed.
Selecting the class uses the same CLI/source replacement/startup workflow.

One generic typed endpoint registry is shared per static VIF type, even when
different owner instances or API classes return or consume the handle. Passing
the same interface through another owner therefore preserves its RemoteRef
identity. It never allocates a replacement interface instance. Native fields
still store their actual VIF values; Python field access uses RemoteRef values,
while method results decode to the existing restricted views. Queue fields
support whole-value and addressed reference updates with validation before
assignment. Modport directions and imported methods remain the sole authority:
for the [test interface](../tests/integration/scoped_bus_if.sv), read_ready and
write_data are available, while write_ready and read_data are not.

VIF dispatch records are emitted independently of consumer-class records, so a
class may retain its own native enum fields in qualified named-value layouts.
Generate-owned scalar enum fields also have native qualification, including
their combination with structural-typedef VIF operations. Local typed enum
conversion delegates to the public SvTypes bit packer without passing the
generate-local enum as an external generic type argument. Original field storage
and wire identity remain unchanged. Same-owner enum/packed-struct containers
also have native qualification in the separate
[generate runtime project](../examples/sv_scoped/README.md#generate-runtime-values).
VIF source generation alone is not evidence for every type combination. Native
value types used by the interface's own operations have the separate scope below.
Shared records precede generic
endpoint definitions; nested class types used as bind type arguments receive
source-local aliases without moving the original type or changing its identity.
Repeated instances of one source definition share identical generated aliases.

Owner-local VIF operations accept supported builtin/structural value signatures,
including typedefs resolved from the original interface's semantic scope. This
includes supported bit/logic, signed integer, real/string and fixed/dynamic/
queue/associative-array layouts. Imported aliases do not require another export
target or handwritten type metadata. Shared adapters use equivalent structural
temporaries, retaining the original VIF static type, SvTypes type identity and
encoding, parameter order/direction and modport restrictions. They do not move
the original typedef or replace its native storage. See the
[typedef operation fixture](../tests/integration/scoped_alias_bus_if.sv).

Package-defined enum and packed-struct types in VIF signals and operations are
also discovered automatically, including enum queues and packed-struct fixed/
dynamic arrays and string-keyed maps. Function/task calls preserve input,
output and inout parameters, native enum identity and struct X/Z data. A caller
uses the discovered public types and the ordinary output holders, for example:

```python
import svx
from svx_mirror.scoped_nominal_bus_types_pkg import Mode

bus = Owner.get_bus(0)  # Owner is the previously imported API mirror.
previous, changed = svx.Output(), svx.Inout(Mode.IDLE)
result = bus.echo_mode(Mode.ACTIVE, previous, changed)
assert result == changed.value == Mode.ACTIVE
```

The shared endpoint and its call-record class carry explicit native type
parameters. Records retain SvTypes packers and descriptors; they do not replace
the enum/struct with a different public wire type or infer native types from a
runtime VIF value. The same static VIF retains one endpoint specialization when
passed among different API classes or owners. See the
[nominal operation fixture](../tests/integration/scoped_nominal_bus_if.sv).

Interface-local nominal types and native class/VIF handle arguments of these
operations still need additional owner-aware binding and are diagnosed rather
than silently omitted or encoded as ordinary values. This restriction concerns
the interface's own operations, not enum fields in its consuming API class.
See the
[SV class fixture](../tests/integration/scoped_vif_classes.svh) for the native
field/constructor/call declarations.

## Virtual Interface Handles

A VIF uses the same identity transport, but has a generated Python view after
decode:

```text
virtual bus_if.master
  -> generated bus_if.master endpoint registry
  -> RemoteRef["sv-vif://bus_if/master"]
  -> generated restricted Python view
```

The static VIF declaration is the complete access authority. For
`virtual bus_if.master`, generated Python members are exactly the signals,
tasks, and functions visible through `bus_if.master`; for `virtual bus_if`,
they are the interface's full public surface. Users do not supply a second
bind name or an independent member whitelist.

The generator obtains interface/modport visibility from the SystemVerilog source
using pyslang, then resolves exposed member value types in the static native
interface scope through the same handle-type analysis used for class exports.
The same path applies when only a package callable carries the VIF, and when
generation enriches a handwritten manifest. Member value types remain SvTypes
contracts: a generated VIF member is emitted only when its formal or signal
type has a concrete supported SvTypes mapping. Unsupported member types fail
generation with the source member and type in the diagnostic; SVX never
guesses a wire encoding from SV spelling.
Packed and unpacked dimensions are retained independently for each declarator.
An unpacked array or queue must not be silently treated as its scalar element
type; where no supported VIF mapping exists, generation fails rather than
emitting a scalar adapter. This concerns collections in interface-member value
signatures, not collections of VIF handles described above; unsupported member
value shapes remain explicit generation errors.

Python cannot construct a VIF. A VIF view is obtained from a declared
parameter, result, or field. Supplying an environment VIF without one of
those data paths is a separate explicit handoff concern and is not implicit
global lookup.

The generated module name is deterministic:
`svx_vif.<interface>.<modport>.<ModportClass>`. The runtime lazily imports that
module when an inbound VIF `RemoteRef` is decoded, so user endpoint code does
not need a separate registration import before using its declared parameter.

## Manifest and Generation Rules

`classes` remains the complete list of requested inheritance generation
targets. Handle adapters are discovered dependencies, not new class targets:
they never cause mirrors, proxies, factories, or every ancestor in a lineage
to be generated.

For each formal or result using a foreign handle, generator metadata
contains:

- the SvTypes `RemoteRef` target type name and descriptor;
- the static SV formal type;
- the handle kind: `sv_class` or `virtual_interface`;
- for a VIF, the interface and optional modport source identity.

The generated record continues to contain `svtypes_pkg::remote_ref`. Only at
the generated call boundary does the typed adapter convert between that record
field and the actual SV class/VIF handle. Thus the record codec and the SV
formal declaration are intentionally distinct.

Python declaration front ends use `svx.sv_class_handle(target, sv_type)` or
`svx.virtual_interface_handle(target, sv_type)` together with a concrete
`svtypes.RemoteRef[target]`. Pass the resulting metadata to
`svx.inheritance_parameter(..., handle=...)` and, for a result, to
`svx.inheritance_method(..., return_handle=...)`. When VIF views are needed,
run `inheritance-manifest` or `inheritance-gen` with `--sv-source` for the
interface declaration. The scanner derives the VIF operations automatically.

For selected SV-owned fields, include the owning class source with `--sv-source`
as well. The scanner can fill `handle` metadata from a directly declared native
class type found in the scanned packages, or a concrete virtual-interface type.
The field still needs its SvTypes RemoteRef contract; discovery does not select
additional members or generate a referenced class. Explicit metadata is checked
against the discovered native type. Static/local members and unpacked arrays
are not scalar instance-handle projections. Typedef aliases, imported unqualified
class names, and closed parameterized member types still require explicit handle
metadata; their semantic resolution is not implemented by this source scanner.

VIF functions may return a value or `void`; either form may have `output` and
`inout` parameters. Python keeps every formal in its original position and uses
the ordinary `svx.Output`/`svx.Inout` holders for copy-out. SV source directions
follow SV rules, including an omitted direction inheriting the previous formal's
direction. An explicit SV direction starts a new type
group: without an explicit type, that formal uses `logic`, not the preceding
group's type. For example, `input int a, output b, c` makes b and c one-bit
logic outputs. This does not change Python annotation rules: an unmarked Python
formal is independently `Input`. A function callback may use function VIF
operations, but cannot call a task operation even if its body happens not to
advance simulation time.

## Failure and Lifetime Rules

- Null references round-trip as null SV handles.
- A `RemoteRef` target mismatch fails before the foreign method executes.
- A class endpoint may return a dynamic subtype through its declared base.
- A VIF endpoint may only be used through the original interface/modport
  static type; it cannot be cast into a different modport capability.
- Registry cleanup occurs during `svx_shutdown`; old handles fail after cleanup.
  Shutdown is terminal in that simulator process. Do not persist opaque IDs
  across simulator runs: their session identity is not a globally durable ID.
- The adapter registry does not transfer ownership of a user-created SV
  object. It only retains a handle to keep a transported reference safe for
  the active SVX session.
