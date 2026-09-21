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

For one direct boundary, an SV base `A` and Python child `B` need two local
views:

```text
SV:      A <- BProxy
Python:  AMirror <- B
```

`AMirror` is the Python base view used by `B` and supplies its `super()` path.
`BProxy extends A` is the SV projection of B and dispatches A's virtual
contract to B. The Python `B` instance and the SV `BProxy` dynamic object share
one object ID; `AMirror` is the base portion of that same Python instance, not
a separately allocated Python object.

`AMirror` sends a qualified A base-call request to BProxy. BProxy implements
the corresponding typed task or function gateway with `super.method(...)`, so
no separate AProxy object or class is necessary. A free helper receiving only
an A handle cannot provide this gateway because a normal virtual call would
dispatch back to B.

For a complete alternating chain, each class-specific projection must be
preserved:

```text
SV:      A <- BProxy <- C <- DProxy
Python:  AMirror <- B <- CMirror <- D
```

The cross-language links are object bindings, not native `extends` relations.
For a `B` instance, AMirror holds BProxy's object ID and its base-call path
targets BProxy's A base portion. BProxy makes B visible as an SV base for C and
carries any B-specific virtual contract.

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
semantics. SVX's generated binding redirects a projected field's value access
to its bound SV projection; it must not retain an independently writable Python
copy that can become stale after SV code changes the field.

### Initialization and Access Semantics

Projected state follows normal SystemVerilog class semantics. Creating the SV
projection constructs `BProxy` in SV, runs inherited A construction and field
initialization, then runs BProxy's own field initialization in normal SV order.
SVX does not add a second field-default protocol and does not copy Python
declaration-time values over an already initialized SV object. After the
object binding exists, assignments made by Python construction or ordinary
Python code are normal writes to that SV-owned state.

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
`SVMirror` attaches that backend recursively to its direct and inherited
projected fields only after successful object binding. Before that point a
projected field raises `CrossLanguageConstructionError` on access.

The minimum public SvTypes protocol is deliberately byte-oriented and uses an
opaque storage key, so it remains usable by non-SVX backends:

```python
class ExternalFieldStorage(Protocol):
    def read(self, key: object, descriptor: FieldDescriptor,
             path: FieldPath) -> bytes: ...

    def write(self, key: object, descriptor: FieldDescriptor,
              path: FieldPath, operation: FieldOperation,
              payload: bytes | None) -> bytes | None: ...

class TypeBase:
    def bind_external_storage(
        self, storage: ExternalFieldStorage, key: object,
        path: FieldPath = (),
    ) -> None: ...

    def unbind_external_storage(self) -> None: ...
```

`FieldOperation` includes `set`, `insert`, `delete`, `append`, `pop`, and
`resize`; an implementation rejects operations not valid for its descriptor.
The method is invoked only on an instance-owned field produced by normal
SvTypes field access, never on the class-level declaration template. SvTypes
owns normalization, packing, unpacking, container views, and recursive path
binding. An `Array`, `Queue`, mapping, or nested SvTypes object overrides the
method to bind its children to derived paths. It never interprets `key`. SVX
supplies an opaque key containing its object ID and manifest field ID, then
translates these calls to its native object-operation ABI.

Implementing this only in SVX is possible by replacing each field with an SVX
facade. It is intentionally rejected as the primary design: the value exposed
to B would no longer be the declared SvTypes concrete field, and SVX would have
to duplicate SvTypes container, nested-object, normalization, and serialization
semantics. A façade may exist only as an internal adapter used by SvTypes'
public storage binding, never as a second user-facing field system.

### SVXFieldStorage Lifecycle

`SVXFieldStorage` is SVX's implementation of SvTypes'
`ExternalFieldStorage` protocol. It is one internal service per active SVX
runtime session, not a user-facing type and not a field-value cache. Its opaque
binding key identifies the pair `(svx_object_id, manifest_field_id)`; path and
operation data are supplied by the bound SvTypes field instance.

`SVXFieldStorage.read()` calls the native `read_field` operation and returns
SvTypes bytes. `SVXFieldStorage.write()` calls native `write_field` with the
same descriptor/path/operation semantics. The native layer owns VPI scope,
temporary buffers, and conversion to structured SVX errors. On construction
rollback, `kill`, `disable`, or shutdown, SVX first calls
`unbind_external_storage()` on every bound mirror field, invalidates the
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

For every such B field, generation must:

1. use the declared public SvTypes type as the only type contract;
2. emit an equivalent typed member in `BProxy`, with the declared construction
   initializer;
3. expose typed Python access through `B`/`AMirror` field descriptors that
   read and write the member owned by its bound `BProxy` instance; and
4. make the member naturally available to downstream SV subclasses such as
   `C extends BProxy`.

Thus the durable state is owned by the SV dynamic object when B has an SV
projection. A Python-local attribute that is not declared as a projected state
field remains Python-only and is neither visible to SV nor serialized by SVX.
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

For `class BProxy extends A`, the BProxy dynamic object contains both A's
inherited instance state and B's directly declared projected fields. It does
not duplicate A's storage. The generated `AMirror` provides B with access to
every A field that A explicitly exposes as a SvTypes projected field; B then
inherits that complete A field view through ordinary Python inheritance.

Consequently, the state model at this boundary is:

```text
SV BProxy instance: A state + B projected state
Python B instance:  AMirror view of A projected state + B field view
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
Python override. It does not yet generate the class-specific `BProxy` and
`CMirror` stack, projected state fields, or lineage-aware qualified base calls
across every boundary. The remote regression covers the narrower path only.

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
class fields have normal per-instance `.value` semantics after binding, while
their authoritative storage remains the matching BProxy member. Projected-field
access before binding raises a construction error; SVX does not create a
separate writable Python setup copy and later merge it into SV state.

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
that defines the complete `class BProxy extends A`: B's SvTypes fields, typed
field operations, virtual overrides, qualified base-call gateways, and the
factory. Normal SV compilation includes that generated file before compiling
classes such as C. A discovery/lint command may materialize the same generated
include in a temporary output directory; an empty handwritten BProxy stub is
not a supported source form because it cannot provide valid member types or
virtual method bodies.

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

Constructing `B()` first requests construction of its BProxy projection. The
SV factory executes normal SV construction; only after it returns an object ID
does SVX bind that ID to the Python B instance and enable mirror field access.
If any later Python initialization fails, SVX destroys the just-created
projection and removes both bindings. Conversely, SV-origin construction binds
the Python instance before the first virtual callback.

For an alternating chain, projection base classes and mirror base classes are
class portions, never separately allocated companion objects. For example:

```text
SV:      A <- BProxy <- C <- DProxy
Python:  AMirror <- B <- CMirror <- D
```

Creating `D()` produces exactly one `DProxy` SV object and one `D` Python
object, under one SVX object ID. The DProxy object contains its inherited C,
BProxy, and A portions; the D Python object contains its CMirror, B, and
AMirror portions. In particular, it does not allocate a separate A, BProxy,
B, C, or CMirror object. A `B.super()` base call targets the BProxy/A portion
of this same DProxy; a `D.super()` base call targets its DProxy/C portion.

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

Each cross-language invocation carries a monotonic call ID and a logical
receiver/method stack. Entering a receiver/method pair already active on that
stack fails with a structured `CrossLanguageRecursionError`; it never waits for
a circular synchronous call. `kill`, `disable`, and shutdown invalidate the
associated call frames and bindings before releasing the Python/SV objects.

### Alternating Lineage Generation

The frontend scans declared Python mirrors/classes and marked SV proxy/classes,
then resolves the complete logical lineage before output. For
`A(SV) -> B(Python) -> C(SV) -> D(Python)`, it emits only the projections named
by top-level manifest targets, such as BProxy and DProxy, plus the generated
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
