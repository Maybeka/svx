# Cross-Language Inheritance Lineage

## Purpose

This document defines how a manifest describes an inheritance target without
causing SVX to generate every class in its ancestry. `classes` remains the
complete and exclusive set of code-generation targets. A target's
`base_lineage` is validation and generation context only.

## Manifest Shape

`base_lineage` is an optional, root-to-direct-parent array on a top-level class
object. Each entry is a complete class declaration: canonical identity,
language, source symbol, constructor, and declared methods. It excludes the
top-level class itself, is not nested recursively, and contains no duplicate
or self identity.

For a target `C`, the form is:

```json
{
  "canonical_id": "sv://drivers/C",
  "language": "sv",
  "symbol": "drivers::C",
  "methods": [],
  "base_lineage": [
    { "canonical_id": "sv://drivers/A", "language": "sv", "symbol": "drivers::A", "methods": [] },
    { "canonical_id": "py://checks/B", "language": "python", "symbol": "checks.B", "methods": [] },
    { "canonical_id": "sv://drivers/E", "language": "sv", "symbol": "drivers::E", "methods": [] }
  ]
}
```

This records `A -> B -> E -> C` as the logical lineage. It does **not** ask
the generator to emit `A`, `B`, or `E`. If the same class appears as a
top-level target and inside another target's lineage, both full descriptions
must be identical.

## Projection Stack

For one SV-to-Python boundary, an SV base `A` and Python child `B` need a
paired mirror on each side:

```text
SV:      A <- AMirror
Python:  AMirror <- B
```

The two `AMirror` names occur in separate language namespaces. The generated
SV `AMirror extends A`; the Python `AMirror` is B's executable base view and
creates that SV mirror. The Python B instance and the SV AMirror dynamic object
share one object ID. The SV mirror contains A's normal base portion; the Python
mirror is a base portion of B, not a separately allocated Python object. There
is no `BProxy` for a direct `B()` construction.

The SV AMirror overrides each explicitly exposed A virtual member and dispatches
it to the Python object registered under the shared object ID. Its generated
qualified base gateway calls `super.method(...)` to reach A's implementation;
Python `AMirror.super()` uses that gateway. Thus both Python-initiated calls and
ordinary SV virtual calls on the SV AMirror can reach B's Python override
without changing the user's A implementation.

`BProxy extends SV::AMirror` is created only when a later Python-to-SV edge
needs B to be an SV base, for example `A(SV) -> B(Python) -> C(SV)`. The C dynamic object
then contains a BProxy portion, which provides B's SV-visible virtual dispatch,
qualified base gateways, and selected projected state. More precisely, BProxy
extends the generated SV AMirror, preserving A's callback-dispatch layer.

For a complete alternating chain, each class-specific projection must be
preserved:

```text
SV:      A <- AMirror <- BProxy <- C <- DProxy
Python:  AMirror <- B <- CMirror <- D
```

The cross-language links are object bindings, not native `extends` relations.
For a direct B instance, Python AMirror holds SV AMirror's object ID and its
base-call path targets the A base portion. For C and D instances, BProxy makes
B visible as an SV base for C and carries B's additional SV-visible contract.

## Member Invocation Semantics

Every manifest-exposed A member has a generated Python AMirror access endpoint.
SV `local` members are never exposed; an exposed `protected` member is reached
only through a legal gateway emitted inside `SV::AMirror extends A`.

- A `virtual` member has an SV AMirror override that dispatches by object ID to
  the bound Python object. Its qualified base gateway invokes `super.method()`
  in SV, so Python `super()` reaches A without re-entering the callback.
- A non-virtual instance member has a Python AMirror wrapper that calls A's
  qualified endpoint. If B defines a Python member of the same name, normal
  Python lookup selects B's member; B's inherited AMirror wrapper remains the
  explicit path to A. An SV call compiled against A remains A's ordinary
  non-virtual call and never dispatches to B.
- A static member is handled the same way as a non-virtual member, except its
  generated endpoint calls `A::method` and has no object ID. A Python subclass
  may define its own static member under normal Python rules; it does not alter
  the A static member or introduce a class-level cross-language dispatcher.

Method parameters, function returns, `output` parameters, and `inout`
parameters use SvTypes exclusively. A call encodes each input once. Its result
record contains the optional function return plus named encoded updates for all
`output` and `inout` parameters; the generated SV wrapper assigns those updates
before returning to its caller. This is ordinary copy-in/copy-out behavior, so
`inout` requires no alias protocol.

For a **Python-to-SV task** call with a declared `const ref T` parameter,
Python supplies an ordinary SvTypes value. The generated wrapper uses a typed
temporary lvalue as the actual and does not copy a value back. A readwrite
`ref T` instead requires `svx.Ref[T]`, not a bare Python value. `Ref.value` is
its only public access surface. The generated SV wrapper constructs one temporary
`svx_ref_argument#(T)` per distinct Python Ref object, initializes its `value`
from the SvTypes request, and invokes the target with `ref_arg.value` as the
SV `ref` actual:

```systemverilog
svx_ref_argument#(T) ref_arg = new();
ref_arg.value = decoded_request.value;
target.method(ref_arg.value);  // formal direction is ref T
response.value = ref_arg.value;
```

While the target call is active, the Ref is bound to the helper and every
`Ref.value` read/write synchronously reads/writes `ref_arg.value` through the
generated native ABI. The final value is encoded into the response and retained
by the Python Ref after the call. Reusing the same Python Ref for two `ref`
formals must reuse one temporary helper, preserving aliasing between those
formals during the SV call. This is a real SV `ref` call to the target, while
necessarily being a call-scoped temporary from Python's perspective: ordinary
Python values are not SV lvalues. A Python caller needing an existing SV member
as the actual uses a separate manifest-exposed member-reference capability.

Generated `output` and `inout` calls use the same helper shape. An `output`
helper is left at the SV type's normal default before the call, whereas an
`inout` helper is initialized from its request value. Both are packed only after
the target returns. This keeps post-call handling explicit and ensures that
every returned value follows its declared SvTypes descriptor.

For an **SV-to-Python task** callback with `const ref T value`, Python receives
a read-only `svx.Ref[T]`: `.value` reads the live formal and assignment raises
`SVXReadonlyRefError`. For a readwrite `ref T value`, the helper remains one
internal `svx_ref_argument#(T)` object but has portal mode rather than copied
container mode. The generated SV gateway starts its service task with the real
lexical formal, `serve(ref value)`, before dispatching Python. The portal
receives synchronous read/write requests for its call ID and directly accesses
that formal. Python receives a bound `svx.Ref[T]`, so ordinary code is simply:

```python
def update(self, value: svx.Ref[Int]) -> None:
    value.value += 1
```

There is no cached Python copy and no notification protocol: every `.value`
read observes the current SV formal and every write changes it. On normal
return, exception, `kill`, `disable`, or shutdown, SVX closes the portal,
invalidates its generation, and rejects all later Ref access. The service task
is an SV implementation necessity--a class data member cannot permanently
alias a task `ref` formal--not a second public `Ref` or session API.

Each `.value` read or write is one synchronous operation at the current SV
scheduling point. A compound Python expression such as `value.value += 1` is a
read followed by a write, not an atomic transaction; normal SystemVerilog race
rules apply. Ref identity is call-scoped. If two SV `ref` formals happen to name
the same lvalue, their portals must preserve the lvalue's read/write behavior,
but object identity between the two Python Ref wrappers is not part of the API.

SystemVerilog functions may legally declare `ref` parameters, but that does
not make the formal persistable by a `fork...join_none` child after function
return. A class member cannot retain the formal as an alias either. Therefore,
for a cross-language function SVX emits `SVXW_FUNCTION_REF_AS_INOUT` for a
readwrite ref and degrades that boundary formal explicitly to `inout`: it
encodes the initial value, invokes Python with an ordinary SvTypes value rather
than `Ref`, and assigns the returned value to the original formal after the
callback completes. A `const ref` emits `SVXW_FUNCTION_CONST_REF_AS_INPUT` and
degrades to `input`, with no copy-out. If several readwrite degraded formals
alias the same SV actual, copy-out occurs in their manifest declaration order;
callers must not rely on true ref alias behavior in this warned form. The SV
declaration remains `ref` or `const ref`; the warning is a transport
limitation, not a SystemVerilog syntax restriction.

Users retain responsibility for choosing `task` versus `function` consistently
with their implementation. SVX records the calling context; while executing a
function callback, its own recognized time-advancing primitives (`delay`, task
waits, channel waits, and process waits) fail immediately. This guard cannot
prove that arbitrary user Python or foreign code has no time-related effect.
Every callback is a synchronous ordinary `def`: `async def`, an awaitable
return, and `asyncio` scheduling are invalid and terminate simulation through
the fatal callback policy.

Python exceptions are not converted into recoverable SV return values. The
native dispatcher captures receiver, method, and traceback diagnostics, then
the generated SV gateway reports them and terminates simulation with `$fatal`.
It invalidates the active SVX call frame before termination so that cleanup does
not retain a live cross-language context.

## Projected State Fields

A Python class at a language boundary uses the normal SvTypes class-field
notation; SVX introduces no competing `state` or `inheritance_field` DSL:

```python
from svtypes import Bit, Int, String

class B(AMirror):
    retry_count = Int()
    enabled = Bit(1)
    label = String()
```

As in SvTypes generally, Python reads and writes values through `.value` (for
example, `b.retry_count.value = 3`). `AMirror` must participate in the public
SvTypes field-owner lifecycle so these ordinary declarations have per-instance
semantics. Declaring a field does not by itself move its storage to SV.

### Field Residency

The declaring language owns a field by default. Thus B's direct SvTypes class
fields are Python-owned for the single-boundary lineage `A(SV) -> B(Python)`.
SVX does not construct BProxy merely because B inherits Python AMirror. Direct
B instances use the generic SV AMirror and are SV-polymorphic as A without
acquiring a B-specific SV class or B's Python-declared state.

Field residency is selected per **instantiated most-derived target**, not merely
because another class exists in the same generated project. For a B instance in
`A(SV) -> B(Python)`, B's fields are Python-owned. For a C instance in
`A(SV) -> B(Python) -> C(SV)`, the same B base portion is materialized in
BProxy so C has a real SV base portion in which B's state resides and is
inherited. The resolved manifest records the residency decision for each target
separately from the source field declaration. Python access is redirected to a
BProxy member only for an instance target that selected the field; otherwise it
remains ordinary local SvTypes state.

Accordingly, a Python field does not gain a simulator-storage dependency merely
because its class inherits an SV class. The dependency appears only when that
field is projected across a later Python-to-SV inheritance edge.

### Initialization and Access Semantics

For fields selected for SV residency, projected state follows normal
SystemVerilog class semantics. Creating the selected SV projection constructs
BProxy in SV, runs inherited A construction and field initialization, then runs
BProxy's own selected-field initialization in normal SV order. SVX does not add
a second field-default protocol and does not copy Python declaration-time values
over an already initialized SV object. Unselected B fields retain normal local
Python SvTypes initialization and storage.

SvTypes remains the sole public type, normalization, and encoding contract for
each state transfer. It is not a separate user-visible message router. The
generated native binding may use specialized fixed-size buffers and direct VPI
member operations rather than allocating a generic call envelope for every
field operation, but it must preserve exactly the public SvTypes value
semantics and encoding descriptor.

Mutable SvTypes containers support both operation granularities:

- assigning a complete field transfers the complete SvTypes value in one
  operation;
- assigning an element, slice, keyed entry, or nested declared component
  transfers only that addressed component through a generated typed member
  operation.

The source operation determines the transfer granularity. SVX must not silently
turn a localized assignment into an implicit whole-container writeback, nor
keep a mutable Python cache that can conceal an intervening SV-side update.
Generated typed operations and caller-selected whole-value operations provide
the performance path; large or intensive HDL state manipulation remains native
SV code.

### Parameterized SV Classes

SVX supports a parameterized class only as a concrete, closed specialization.
For example, `drivers::Packet#(int, 16)` is a target distinct from
`drivers::Packet#(int, 32)`. The manifest stores the source symbol and an
ordered `specialization` object: every type argument is a complete concrete
SvTypes type binding; every value argument has an explicit SV type and a
normalized JSON literal value. The same specialization must have one canonical
class ID across all targets and lineage entries.

The generator checks the declared argument count, kind, and order against the
parsed SV source, and emits a digest-qualified helper name such as
`Packet__svx_a1b2c3_mirror`. It rejects open parameters (`T`), unevaluated
expressions (`f(N)`), and macro/localparam-dependent values: those cannot give
the generated artifact a stable type or name. Concrete specializations remain
ordinary SV inheritance; only their generated helper names are qualified.

### Projected Field Storage Binding

SVX must not implement projection by intercepting `SVMirror.__getattribute__`
and returning untyped Python values. That would replace the user's declared
SvTypes `Int`, `Array`, `Queue`, `SvObject`, or `RemoteRef` field object and
break its public `.value`, normalization, packing, and nested-member behavior.

Instead, SvTypes provides a public, simulator-independent external field-storage
protocol. A bound SvTypes field object retains its normal concrete type but
delegates reads and writes through an attached storage backend:

```text
field.value read  -> backend.read(field descriptor, field path) -> SvTypes unpack
field.value write -> SvTypes normalize + pack -> backend.write(field descriptor, field path)
```

The protocol belongs to SvTypes because it is a generic storage abstraction;
it contains no SVX, VPI, simulator, or object-ID knowledge. SVX provides one
backend implementation holding the bound object ID and manifest member ID.
`SVMirror` binds its owner instance only for fields selected for SV residency,
including inherited A fields already owned by SV. The binding map omits
unselected Python-owned fields, which remain locally usable. Before construction
has selected and bound a projected field, its access raises
`CrossLanguageConstructionError`.

The minimum public SvTypes protocol is deliberately byte-oriented and uses an
opaque storage key, so it remains usable by non-SVX backends:

```python
class ExternalFieldStorage(Protocol):
    def read(self, key: object, descriptor: FieldDescriptor,
             path: FieldPath) -> bytes: ...

    def write(self, key: object, descriptor: FieldDescriptor,
              path: FieldPath, operation: FieldOperation,
              payload: bytes | None) -> bytes | None: ...

@dataclass(frozen=True)
class FieldIdentity:
    declaring_type: type
    name: str

class SvObject:
    def bind_external_storage(
        self, storage: ExternalFieldStorage,
        field_keys: Mapping[FieldIdentity, object],
    ) -> None: ...

    def unbind_external_storage(self) -> None: ...
```

`field_keys` names only the external fields of one `SvObject` instance. A
normal SvTypes field resolves its owner, `FieldIdentity`, and derived path at
each access: an absent mapping is local; a present mapping calls the backend.
`FieldOperation` includes `set`, `insert`, `delete`, `append`, `pop`, and
`resize`; an implementation rejects operations not valid for its descriptor.
SvTypes owns normalization, packing, unpacking, container views, and recursive
owner/path propagation. An `Array`, `Queue`, mapping, or nested SvTypes object
propagates its owner context to derived paths. It never interprets `key`. SVX
supplies an opaque key containing its object ID and manifest field ID, then
translates these calls to its native object-operation ABI.

Implementing this only in SVX is possible by replacing each field with an SVX
facade. It is intentionally rejected as the primary design: the value exposed
to B would no longer be the declared SvTypes concrete field, and SVX would have
to duplicate SvTypes container, nested-object, normalization, and serialization
semantics. A façade may exist only as an internal adapter used by SvTypes'
public storage binding, never as a second user-facing field system.

### SVXFieldStorage Lifecycle

**Implementation status (current branch).** The public SvTypes owner binding
is now integrated: `SVXFieldStorage` uses the public
`ExternalFieldStorage` protocol, resolves selected fields to public
`FieldIdentity` values, and binds them to an SVX object ID. The generated SV
helpers currently implement empty-path whole-field `read` and `set` endpoints
through the existing inheritance dispatcher. Container paths and operations
(`insert`, `delete`, `append`, `pop`, and `resize`), native object-operation
ABI endpoints, automatic generated-Python AMirror construction, and teardown
integration remain implementation work in the order recorded below. They are
design requirements, not claims about the current executable surface.

`SVXFieldStorage` is SVX's implementation of SvTypes'
`ExternalFieldStorage` protocol. It is one internal service per active SVX
runtime session, not a user-facing type and not a field-value cache. Its opaque
binding key identifies the pair `(svx_object_id, manifest_field_id)`; path and
operation data are supplied by the owner-resolved SvTypes field instance.

`SVXFieldStorage.read()` calls the native `read_field` operation and returns
SvTypes bytes. `SVXFieldStorage.write()` calls native `write_field` with the
same descriptor/path/operation semantics. The native layer owns VPI scope,
temporary buffers, and conversion to structured SVX errors. On construction
rollback, `kill`, `disable`, or shutdown, SVX first calls
`unbind_external_storage()` on every bound mirror owner, invalidates the
corresponding keys, and only then releases the Python/SV object bindings. Any
subsequent field access fails deterministically instead of reading stale Python
state.

For a projected collection, the same binding is path-aware. `field[index]`
returns the normal SvTypes element type bound to `path=[index]`; a nested
SvTypes object field binds its named children in the same way. Collection
`.value` returns a live SvTypes-compatible sequence or mapping view rather
than a detached mutable list/dict, so `field.value[index] = value`,
`append`, keyed assignment, deletion, and nested writes emit their matching
addressed operation. A whole `.value = value` is an empty-path whole-field
write. Reads do not use a hidden coherence cache.

The native `write_field` operation therefore includes an operation code in
addition to the path: `set`, `insert`, `delete`, `append`, `pop`, and `resize`
as applicable to the declared SvTypes collection. The generated typed SV
endpoint validates that operation against the collection type. This keeps
element-level work element-level, while retaining one whole-value codec transfer
for a complete assignment.

A field is a named, schema-backed cross-language declaration, not a best-effort
synchronization of arbitrary Python attributes. It is compiled into the class's
manifest object. A class records only fields declared directly in its source;
its ancestors retain their own field declarations in their corresponding
`base_lineage` objects. This preserves both the source inheritance structure
and the rule that `classes` contains only requested generation targets.

For every B field selected by the instantiated target's later SV inheritance
edge, generation must:

1. use the declared public SvTypes type as the only type contract;
2. emit an equivalent typed member in `BProxy`, with the declared construction
   initializer;
3. expose typed Python access through `B`/`AMirror` field descriptors that
   read and write the member owned by its bound `BProxy` instance; and
4. make the member naturally available to downstream SV subclasses such as
   `C extends BProxy`.

Thus the durable state is owned by the SV dynamic object only when the resolved
lineage selects the field for an SV projection. An unselected B field remains
Python-owned; a direct B instance has no BProxy at all. A Python-local
attribute that is not declared as a projected state field remains Python-only
and is neither visible to SV nor serialized by SVX.
SVX's default compatibility promise is the complete public SvTypes field family,
not a hand-maintained scalar subset. A field is rejected only when the selected
SvTypes/SVX runtime capability set explicitly does not support its legal SV
member, initializer, or addressed access operation. Object handles use the
SvTypes remote-reference contract; they are handles, not embedded foreign
object storage.

The generator must also reject a projected-field name that conflicts with an
inherited SV member unless the declaration explicitly models the intended SV
language rule. A descendant may add a new field, but it must not silently hide
or duplicate an inherited field across the language boundary.

### Inherited State Visibility

For `class BProxy extends SV::AMirror`, the BProxy dynamic object contains the
SV AMirror/A inherited instance state. It contains B fields only when the
instantiated target continues past B into SV and selects those fields for
projection. It does not duplicate A's storage. The generated Python `AMirror`
provides B with access to every A field that A explicitly exposes as a SvTypes
projected field; B then inherits that complete A field view through ordinary
Python inheritance.

Consequently, the state model at this boundary is:

```text
instance B: SV AMirror contains A state; B fields stay Python-owned
instance C: C/BProxy/SV AMirror contains A + B + C declared state in SV
instance D: DProxy contains A + B + C state in SV; D fields stay Python-owned
```

An A member that has not been declared as a projected SvTypes field remains SV
implementation state. In particular, an SV `local` member cannot be reached by
a BProxy-generated accessor under SystemVerilog visibility rules. It may become
available only if A itself supplies an explicit legal accessor and declares the
corresponding SvTypes contract. SVX must reject a manifest that claims direct
projection of such an inaccessible member rather than generating an invalid or
implicitly privileged access path.

The current implementation verifies a narrower path: an A-derived SV proxy can
have ordinary intermediate SV subclasses and still dispatch calls to a bound
Python override. The manifest parser and declaration frontend now retain
`ref_access`, closed concrete specializations, and a target-only projection
plan. The runtime does not yet generate the class-specific `BProxy` and
`CMirror` stack, projected state fields, live `Ref` portals, or lineage-aware
qualified base calls across every boundary. The remote regression covers the
narrower path only; the remaining pieces are implementation work, not existing
behavior.

The first field-storage adapter is now present in Python and uses the existing
generic object dispatcher for manifest-declared root-field reads and `set`
writes. Path-aware container operations, automatic mirror-owner binding during
construction, and BProxy/CMirror projection emission remain incomplete; they
must fail explicitly rather than fall back to cached Python state.

## Construction

For an SV-owned class with `constructor.initiator: "python"`, the generated
Python mirror calls `inheritance_create_sv(class_id, encoded_constructor)`.
The generated SV proxy factory decodes that SvTypes request, constructs the
proxy, and registers the instance under the returned object ID. The user must
register that generated factory before creating the Python object. All
constructor parameters, method parameters, results, errors, and object handles
use SvTypes codecs; source parsing never infers a competing codec.

## Source-Backed Manifest Frontend

Python declarations are opt-in through `@inheritance_class` and
`@inheritance_method`; only decorated classes are top-level generation targets.
The decorator is declaration metadata, not a Python inheritance mechanism.
`base_lineage=` accepts the explicit expanded ancestor objects; the resolved
lineage determines which generated foreign mirror is the actual Python base.

SV source is validated with the optional `pyslang` dependency, supplied by the
Slang project. The frontend reads actual package/class declarations, direct
`extends` names, and `virtual` method declarations. It rejects a manifest that
names an absent SV class or marks a non-virtual source method as virtual:

```sh
python -m svx inheritance-manifest \
  --sv-declarations declarations.json \
  --sv-source drivers.sv \
  --out inheritance.json
```

Install this frontend with `pip install 'svx[manifest]'`. The declaration file
continues to supply the SvTypes codec contract; `pyslang` supplies source facts.
No regex-based SV fallback is permitted.

## Frozen Generator and Runtime Contract

The following choices are normative for the complete implementation.

### Field Manifest

Every class object has a `fields` array, defaulting to `[]`. Each item contains
exactly a legal identifier `name` and a normalized public SvTypes
`field_descriptor`. The descriptor is produced from the actual SvTypes field
object declared in source; it carries the field's public type identity,
encoding descriptor, construction value/declaration semantics, and legal SV
declaration form. The manifest is a frozen product of source declarations, not
a second user-authored type declaration.

Only direct source fields are emitted in a class's `fields` array. The same
normalization is applied to Python source fields and to SV fields explicitly
annotated as SvTypes fields. The generator reconstructs and validates the
descriptor through public SvTypes APIs before generating code. A raw SV type
string, handwritten binary layout, or SVX-local field codec is not an
alternative contract.

### User Declarations and Generated Artifacts

An SV-origin base is represented in Python by a source-managed, executable
mirror declaration:

```python
@svx.sv_mirror("sv://drivers/A")
class AMirror(svx.SVMirror):
    retries = Int()

    @svx.mirror_method(
        parameters=[svx.parameter("value", Int())],
        return_type=Int(),
    )
    def check(self, value: int) -> int:
        return self._svx_call_base("check", value)

@svx.inheritance_class(canonical_id="py://checks/B")
class B(AMirror):
    retry_count = Int()
```

`SVMirror` is a public SvTypes field owner. Consequently B's ordinary SvTypes
class fields have normal per-instance `.value` semantics. A B field selected
for a later SV projection is bound to its matching BProxy member after binding;
an unselected B field remains local Python SvTypes state. Access to an
SV-resident field before binding raises a construction error; SVX does not
create a separate writable Python setup copy and later merge it into SV state.

`@svx.sv_mirror("sv://drivers/A")` has one purpose: it binds the source Python
class name `AMirror` to the canonical SV class A during discovery and gives that
class the executable mirror behavior. It does not allocate an A object, emit an
SV class, make AMirror a top-level code-generation target, or imply that every
A instance has a Python companion. The generated AMirror implementation gains
only the A methods and fields explicitly exposed by A's manifest declaration,
including qualified typed base-call operations.

### Static Interface Contract

The AMirror source body is the Python static interface for the exposed A
surface. Its fields use ordinary SvTypes declarations and its methods have
ordinary Python signatures, so a Python type checker can validate B code such
as `self.retries.value` and `self.check(value)` without running SVX or reading a
manifest at analysis time. The mirror method body is executable: it forwards to
the generated qualified base-call operation at runtime. A `pass`-only AMirror
is insufficient for this purpose.

`@svx.mirror_method` supplies the precise SvTypes parameter/result binding for
that executable wrapper; it does not invent a second value type system. During
manifest generation SVX compares every exposed AMirror field and method against
the declared SV A surface. A missing, extra, incompatible, or non-virtual
overridable method is a generation error. Thus the source mirror is both usable
by static tooling and checked against the real SV contract rather than being an
unchecked duplicate declaration.

The SV source contains a named proxy declaration marker, not a handwritten
duplicate implementation:

```systemverilog
`SVX_PY_PROXY(BProxy, "py://checks/B", A)
class C extends BProxy;
  // ordinary user SV implementation
endclass
```

The marker is resolved by the manifest generator into one generated include
that defines the complete `class BProxy extends AMirror`: selected B SvTypes
fields, typed field operations, virtual overrides, qualified base-call gateways,
and the factory. It is emitted only when B has a downstream SV inheritor.
Normal SV compilation includes that generated file before compiling classes such
as C. A discovery/lint command may materialize the same generated include in a
temporary output directory; an empty handwritten BProxy stub is not a supported
source form because it cannot provide valid member types or virtual method
bodies.

The two declaration forms have different lifecycles:

- `AMirror` is not a disposable stub. It remains imported source code at
  runtime, is the actual Python base in B's MRO, and receives generated mirror
  binding metadata when a matching SV object is bound.
- `SVX_PY_PROXY(...)` remains in user SV source as a regeneration and discovery
  marker. During normal compilation its macro expansion emits no duplicate
  class; the generated include supplies the real BProxy definition.
- A lint-only generated include is temporary and may be discarded after lint.
  The normal generated include is compiled into the simulation and its BProxy
  class is the only SV proxy implementation used at runtime.

### Native Object Operation ABI

SVX exposes a single versioned native object-operation service to Python. Its
operations are `construct`, `invoke`, `read_field`, and `write_field`; each
names an SVX object ID, a manifest member ID, and where relevant an addressed
SvTypes field path. `write_field` additionally carries a collection operation
code when the path addresses a mutable container. Payload and result bytes
always use the member's validated SvTypes descriptor.

Generated BProxy code provides typed SV endpoints for these operations. The
native layer resolves object/member IDs, invokes VPI directly, and owns scope,
buffer lifetime, and error conversion. Python does not call ad hoc generated
symbols. This gives one stable native ABI while retaining type-specialized SV
implementations and permits fixed-size fast paths without changing data
semantics.

### Construction, Lifetime, and Calls

Constructing `B()` first creates the generated SV AMirror through Python
AMirror. SVX then binds that object ID to the Python B instance and enables A
mirror field access. B's own fields are Python-resident and do not require a
BProxy. If later Python initialization fails, SVX releases the SV AMirror
binding according to its ownership policy. Conversely, SV-origin construction
binds the Python instance before the first supported callback.

For an alternating chain, projection base classes and mirror base classes are
class portions, never separately allocated companion objects. For example:

```text
SV:      A <- AMirror <- BProxy <- C <- DProxy
Python:  AMirror <- B <- CMirror <- D
```

Creating `D()` produces exactly one `DProxy` SV object and one `D` Python
object, under one SVX object ID. The DProxy object contains its inherited C,
BProxy, SV AMirror, and A portions; the D Python object contains its CMirror,
B, and Python AMirror portions. In particular, it does not allocate a separate
A, SV AMirror, BProxy, B, C, or CMirror object. A `B.super()` base call targets
the SV AMirror/A portion of this same DProxy; a `D.super()` base call targets
its DProxy/C portion.

The converse follows the same rule. Constructing `new C(...)` from SV produces
one C object and binds one generated CMirror companion (whose B and AMirror
parts are ordinary Python base portions), not a second Python B object. An A
instance that is never constructed through or bound to a cross-language
projection remains only an A instance.

Construction uses one generated SvTypes `ConstructionRequest` record for the
dynamic target. It contains an ordered, canonical-class-ID-keyed constructor
argument record for every constructor in the resolved lineage. This removes
ambiguous flattened parameter names and lets generated BProxy/DProxy factories
forward exactly the argument record belonging to each SV or Python base. A
generated user-facing constructor may offer convenience keyword arguments, but
it serializes them into this single record before crossing the boundary.

Cross-language virtual dispatch is unavailable until the relevant binding has
completed. A virtual boundary call attempted during an unbound construction
phase fails with `CrossLanguageConstructionError`; SVX must not silently call a
wrong base implementation or manufacture a partial companion object.

The runtime records this as `ALLOCATED`, `SV_CONSTRUCTED`, `BOUND`,
`PY_INITIALIZED`, and `ACTIVE`. Python-origin construction allocates the ID,
constructs the final SV projection, binds it, then runs the Python initializer.
SV-origin construction uses an explicit generated `svx_post_construct()` call
at the end of the marked construction path to bind and initialize the Python
companion; there is no portable way to intercept completion of arbitrary
handwritten `new C(...)`. A failure unbinds external field storage first,
removes registry entries, and marks the ID `ABORTED`.

Python-origin pairs own the Python object and their internal SV companion.
An SV caller that writes `new C(...)` owns that actual SV object; SVX owns only
the borrowed companion binding. `RemoteRef` is non-owning. An already existing
SV object is never silently converted according to guessed dynamic type:
`svx.adopt_instance(target, handle)` is the only supported opt-in, creates an
uninitialized mirror view, and does not invoke Python `__init__`.

Each cross-language invocation carries a monotonic call ID and a logical
receiver/method stack. Entering a receiver/method pair already active on that
stack fails with a structured `CrossLanguageRecursionError`; it never waits for
a circular synchronous call. `kill`, `disable`, and shutdown invalidate the
associated call frames and bindings before releasing the Python/SV objects.

### Alternating Lineage Generation

**Implementation status (current branch).** Manifest parsing validates complete
flat lineage, computes the minimal projection plan, and emits ordered SV
`AMirror`/`BProxy` helper packages. The BProxy base gateway delegates to the
AMirror gateway so a Python `super()` call reaches A's SV implementation rather
than recursively dispatching into the Python override. The emitted helpers and
root field endpoints have Python regression coverage. Full generated Python
AMirror lifecycle code, factory registration for alternating constructors, and
end-to-end A/B/C/D runtime qualification are still pending.

The frontend scans declared Python mirrors/classes and marked SV proxy/classes,
then resolves the complete logical lineage before output. For
`A(SV) -> B(Python) -> C(SV) -> D(Python)`, it emits the A-paired SV AMirror,
emits BProxy only because C needs it, and emits DProxy only because D is
followed by an SV projection in a target lineage. It also emits the generated
mirror metadata needed by those targets. It never emits A, B, C, or D merely
because they occur in another class's lineage. Every emitted projected `extends`
edge and every qualified `super` gateway is checked against the complete
resolved chain before SV compilation.

## Implementation Order

1. Extend the manifest parser and Python declaration frontend with normalized
   direct `fields`, backed only by public SvTypes field descriptors.
2. Add `SVMirror`, `@svx.sv_mirror`, and `SVX_PY_PROXY`; implement generated
   include materialization for compile and lint flows.
3. Implement the versioned native object-operation ABI and generated typed
   endpoints for fields, construction, virtual dispatch, and qualified base
   calls.
4. Resolve complete mixed-language lineage before generation and materialize
   only target projections.
5. Qualify with Python and VCS regressions for A/B/C/D chains, inherited and
   direct fields, whole/container-path updates, construction rollback, virtual
   `super`, recursion rejection, and lifecycle interruption.
