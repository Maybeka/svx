# Cross-Language Handle Adapters

## Status

SVX generates these adapters as dependencies of a declared cross-language
method. They complement, rather than replace, the mirror/proxy registry used
by generated inheritance objects.

## One Wire Contract

SvTypes `RemoteRef[target_type_name]` is the only value transferred across a
cross-language call for every foreign handle. Its payload is a nullable,
session-scoped `uint64` object ID. SVX does not introduce a parallel handle
serializer, expose a raw simulator pointer, or encode a VPI handle as data.

The ID is useful only together with its static target type. `0` means null.
Every non-null ID is resolved in SV immediately before a generated typed call;
an unknown, stale, or wrong-kind ID is a call failure.

## Unmapped SystemVerilog Class Handles

An SV class used only as a parameter, return value, or field need not be a
top-level cross-language inheritance target. The manifest generator discovers
that use and emits internal metadata plus one typed adapter for the static
SV type.

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

The generator obtains the interface, modport, and member facts from the
SystemVerilog source using pyslang. Member value types remain SvTypes
contracts: a generated VIF member is emitted only when its formal or signal
type has a concrete supported SvTypes mapping. Unsupported member types fail
generation with the source member and type in the diagnostic; SVX never
guesses a wire encoding from SV spelling.

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

## Failure and Lifetime Rules

- Null references round-trip as null SV handles.
- A `RemoteRef` target mismatch fails before the foreign method executes.
- A class endpoint may return a dynamic subtype through its declared base.
- A VIF endpoint may only be used through the original interface/modport
  static type; it cannot be cast into a different modport capability.
- Registry cleanup occurs during `svx_shutdown`; no stale handle becomes valid
  in a later SVX session.
- The adapter registry does not transfer ownership of a user-created SV
  object. It only retains a handle to keep a transported reference safe for
  the active SVX session.
