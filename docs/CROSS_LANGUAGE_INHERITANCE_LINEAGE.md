# Cross-Language Inheritance Lineage

## Purpose

This document defines how a manifest describes an inheritance target without
causing SVX to generate every class in its ancestry. `classes` remains the
complete and exclusive set of code-generation targets. A target's
`base_lineage` is validation and generation context only.

When a class is both a top-level target and another target's lineage member,
its declaration is compared independently of its own `base_lineage` context.
An explicitly supplied top-level ancestry prefix must agree with the prefix
at that member's position. This permits multiple requested targets on the
same chain without treating their different context placement as conflicting
class definitions; genuine member/type/constructor differences still fail.
Parsing also checks repeated ancestor-only declarations across all targets.
One canonical class cannot have conflicting concrete ancestry prefixes, even
when that class is not a top-level generation target. Declaration conflicts
identify both targets and the differing declaration items; ancestry conflicts
identify both prefixes. An empty/omitted top-level lineage remains unspecified
context and does not erase a concrete ancestry supplied elsewhere. These
checks do not add ancestors to `classes` or trigger code generation.

### Constructor Routing

The manifest planner now selects natural constructor routing for Python
portions of SV-root chains and non-root Python portions of Python-root chains.
The root Python initializer runs after its SV Proxy's field initialization.
Each portion uses its own SvTypes constructor
record; ancestor constructors need not have matching parameter lists. The
original Python initializer runs once and pauses at the generated SV view's
`super().__init__()` boundary. Its evaluated arguments feed the corresponding
SV `super.new(...)`. After that SV portion and the proxy's field initializers
finish, SVX binds the complete receiver field map and resumes Python.

Existing dynamic target selection reserves one most-derived Python receiver
and paired object ID for the chain. Completed portions retire their constructor
reservation in lineage order. Python-local fields remain local unless selected
for that concrete target's SV projection. A selected SV target is constructed
through its generated SV Mirror or Python view; calling `new` on only the
original SV source class does not select that target's generated Python view.

The executable controls cover transformed Int/String/class-handle arguments,
an extra Python constructor parameter, one-time initialization, the SV-root
`A -> B -> C -> D -> E` chain, field residency and successful reservation cleanup.
SV-root Python initializer failures now unwind suspended portions and close
the paired receiver, invalidating projected storage and retiring both bindings.
The synchronous close path also clears that receiver's SV constructor caches
and context before the exception policy terminates simulation. Controls cover
inner B failure while D is suspended and later D failure, from both construction
origins, and retain the original Python error location. Python-root controls
also cover heterogeneous constructor prototypes, computed Python `super()`
arguments and both construction origins. Python-root root and later Python
initializer failure controls also verify paired binding retirement, projected
storage invalidation and constructor cache/context cleanup from both origins.
Root initializer failures perform synchronous cleanup inside the callback before
the exception policy terminates simulation; enclosing factory cleanup remains
idempotent. Broader constructor qualification remains unfinished.
Historical staged-construction controls below describe narrower
earlier evidence and do not establish those remaining behaviors.

**Status boundary.** This document contains both the agreed complete design
and implementation evidence. Current executable source classes use the generated
`svx_mirror` / `svx_py` types. Public `inheritance-gen --sv-integrated-dir` now
assembles mixed SV-root and Python-root alternating targets from an existing
manifest and ordered source inputs, including terminal SV target views and
their construction factories. Its combined runtime control qualifies both
construction origins, independent targets, fields, callbacks and cleanup.
The old single-file and manual-stage renderers retain their separate-package
and executable-lineage restrictions; those restrictions do not describe the
integrated output mode. Source-only discovery without import bootstrap,
source-declared executable mirror interfaces, canonical-class-keyed
heterogeneous ancestor constructor records and arbitrary source/build forms
remain incomplete. The detailed controls below establish individual behaviors,
not complete qualification of every inheritance shape.
An internal SV-root `A -> B -> C` staged-construction fixture now constructs
the terminal C view from either language with one receiver and initializes B
after A but before C's constructor body. It also checks the residency contrast:
direct B construction keeps B-only fields local, whereas C construction projects
A/B/C fields to its SV object. This qualifies zero-argument constructors,
not heterogeneous ancestor-record support or arbitrary target shapes.
The internal SV-root emitter now derives first-Python and subsequent initializer
stages from complete lineage and also qualifies `A -> B -> C -> D -> E`.
D-only targets do not manufacture DProxy or project D-only fields. An E target
materializes the required DProxy edge and binds D's fields to E's SV instance.
An internal receiver-scoped constructor context now exercises ordinary and
implicit zero-argument source constructors without adding bridge-ID formals.
Nested same-type construction has distinct IDs and restores the context stack.
Generated helpers now enter that context through an internal constructor
parameter's default expression, rather than a local initializer before
`super.new()`. Focused native/SV tests no longer emit the earlier constructor-order
warning. This is not full cross-tool construction qualification;
arbitrary early-callback shapes and source layouts remain work.
Internal staged emitters now
aggregate effective inherited virtual slots: a source C need not redeclare A's
virtual method for a later Python D override to be reached. The callback retains
the existing method's SvTypes contract and independently identifies the C mirror
boundary. This keeps C-to-D dispatch distinct from B's qualified return to A.
Focused native/SV qualification covers Python-origin D and both origins of E
with C omitting the declaration; it is not
qualification of every inherited signature, visibility, or constructor shape.
Internal SV-root construction also selects the first Python portion per dynamic
target instead of requiring a unique Python descendant of the shared SV root.
The root Python mirror registers itself, not an arbitrarily imported direct
subclass. A standalone SV root mirror therefore represents A; a natural Python
`B()` constructs its A mirror while keeping B-only fields local. Final C/C2
helpers choose B/B2 respectively. Focused native/SV tests cover two branches in
one manifest, both construction origins, base-handle virtual dispatch and close.
More complex shared prefixes, branch-specific constructor records and the
public consumer workflow remain unfinished.
Internal target helpers now also carry exposed fields and instance-method
gateways for ordinary SV portions between the preceding Python proxy and the
target SV class. For `A -> B -> Middle(SV) -> C`, a C-only request emits no
Middle mirror: the C Python view declares Middle's field surface, and its SV
helper uses Middle's canonical field/method IDs. Qualified method gateways
select Middle's implementation rather than accidentally selecting a C override.
Focused native/SV qualification covers both C construction origins, a protected
ancestor function, virtual/base dispatch, live field updates and retained-field
invalidation. Internal package emission also registers class-owned static
gateways for each required SV source and ordinary SV ancestor. The Python
target surface retains the declaring class ID for inherited static methods;
a target's same-name declaration takes precedence without making dispatch
virtual. A virtual gateway reaches protected static members, while the registry
owns a separate lightweight dispatcher, never an instance of the source class.
Focused native/SV tests cover root and ancestor static functions, a protected
ancestor static task advancing time, instance access, same-name selection and
calls before construction and after all receivers are closed. Multiple targets
sharing an ancestor emit its static registration once. This does not qualify
all static signatures or complete public generation.
Internal SV-root construction distinguishes the logical lineage root from its
first bridge root. For `Z(SV) -> A(SV) -> B(Python) -> C(SV)`, Z remains ancestry
context while A is the first required SV mirror. A's helper owns the receiver
ID and exposes Z's canonical field/method endpoints; its Python mirror carries
Z's inherited surface. Requesting only C adds no Z mirror, proxy or factory.
Focused native/SV qualification covers standalone A and B construction, both
origins of C, protected ancestor access, static dispatch, Z-typed virtual calls
to B, live field updates and close invalidation. A shared Z/A prefix also
qualifies per-target B/B2 selection under both construction origins. These
controls retain the existing zero-argument constructor scope and incomplete
cross-tool qualification; they do not qualify arbitrary prefix
constructors or source layouts. Heterogeneous prefix/ancestor records, deeper
member/type/policy shapes and arbitrary public consumer scenarios remain work.
Internal staged-construction fixtures now cover B/C/D/E, Python-origin F, and
lineage-derived Python artifacts loaded through the startup manifest; these are not a
complete consumer workflow. Additional qualification materializes root proxies and
later mirrors in their normal `svx_proxy_<module>::Class` and generated mirror
packages, with unmodified startup artifact metadata. Its C/D/E source anchors are
still supplied by a fixture: that control alone does not qualify the public CLI
or solve same-package source dependency cycles. The source-unit assembler
now integrates `A -> B -> C` with A and C in one SV package. It uses parser
source ranges to insert private bridge classes and rewrite the generated copy's
proxy references in the owning source package. This includes base names, member
and method handle types, and qualified static calls. Original files, comments
and literals remain untouched. References outside the owning package retain
public names when those aliases are ready; earlier consumers resolve to the
already-defined owner helper. Public helper/proxy packages publish type aliases with their existing
class names; no user package split is required. The generated Python module
retains A and lazily defines C, and startup finalizes deferred views after all
artifact modules load. C remains `svx_mirror.<package>.C`, including its Python
class name and qualified name. Native/SV qualification covers SV-first creation
before Python requests C, Python-origin C, direct B, static access, virtual
dispatch, field residency/updates and close. This experiment requires direct
source anchors in one source unit and is not complete cross-tool construction
qualification. Internal source-managed artifacts now also qualify a shared Python B/D
source module alongside A/C/E in one SV package. Later views and companions
are deferred, and reentrant source imports reuse any type already materialized
instead of rebuilding it. Earlier independently-owned boundary views are removed
from the generated copy so they cannot shadow the complete staged target view.
Fresh-process tests cover both source-first and artifact-first imports, repeated
loading, exact type identities and `D(CMirror, B)` ancestry. Native/SV tests cover
SV-first E and Python-origin D/E, ordered initialization once, virtual dispatch,
field residency and close invalidation. This qualifies the stated zero-argument
SV-root control, not arbitrary Python import-time execution or dependency graphs.
The corresponding internal Python-root source-unit control now covers
`Root(Python) -> Child(SV) -> Derived(Python) -> Grandchild(SV)`, with Root/Derived
in one Python module and Child/Grandchild in one SV package. Deferred loading
preserves exact type identities in either import order. The generated source copy
supplies receiver-scoped construction binding: user SV constructors retain normal
`super.new(seed)` calls without forwarding bridge IDs. Both-origin creation,
one-time initialization, root-typed virtual dispatch, local versus projected
fields and close invalidation are qualified for this scalar-constructor control.
Its constructor context is established through a generated default argument
before `super.new()`, without the previous local-initializer warning in the
tested configuration. It does not qualify cross-tool construction or arbitrary
ancestor constructor records or early constructor callbacks.
The explicit integrated CLI now consumes these source and Python assemblers;
the individual controls do not qualify arbitrary include/macro mapping or
cross-unit dependency graphs. These remain implementation requirements, not
requirements to split user code. Source-managed mirror methods and per-ancestor
constructor records remain design work, not interfaces users can invoke today.
An additional internal SV-root control accepts an ordered set of source files
belonging to one compilation unit. It emits one integrated copy without changing
those input files, preserving their shared preprocessing state and using `line`
directives to restore original file/line locations after private bridge insertion.
Public alias packages are emitted at their earliest complete declaration point,
so a consumer of an earlier root does not have to move behind unrelated later
targets. The real control requests only E and keeps A, C and E in three separate
source packages/files, with B/D in one Python module and an intervening SV
consumer. It verifies both creation origins, type identity, virtual dispatch,
field residency, close and a compiler error pointing to its original source
file and line. This is not independent compilation-unit/library support,
a general build-file frontend or public CLI qualification.
The opposite Python-root multi-input control now keeps Child and Grandchild in
two source packages/files, with Root/Derived in one Python module and an
intervening Child consumer. It qualifies both construction origins, exact public
types, field residency, close, outer Python initialization failure/cleanup/retry
and the staged-super mismatch negative. Fresh-process controls preserve one
type graph under both source-first and artifact-first imports.
Internal parsing also accepts explicit object-like macro predefinitions and
undefinitions. The original conditional source remains conditional in the output;
the generator does not insert definitions to hide a different build configuration.
A real SV-root control uses the same explicit macro in parsing and compilation,
and the omitted-macro compilation control fails rather than producing a different
working graph. This is not the complete compiler-option, include-path, library or
build-file contract; those inputs and their artifact provenance still need public
frontend integration.
The internal package qualification also covers a terminal SV target whose
constructor is explicitly SV-initiated: its paired view and startup metadata
are emitted. This origin metadata does not prohibit Python construction;
SV construction binds the existing receiver before initializing
the Python ancestor portions. This does not remove the old separate-renderer
generation gate or qualify arbitrary source integration.
The Python-owned root example instead
uses a generated typed implementation-selection factory.
This is not a requirement to add an artificial SV ancestor to a Python-root
chain. Such a manifest can be parsed and its logical projection plan inspected.
The separate renderers reject unsupported executable lineages before writing;
the integrated CLI selects helper/construction plans per logical root and
qualifies the combined Python-root control. Remaining complete-target shapes
and source-only discovery are implementation work, not a restriction of the
agreed design or a requirement to add an artificial SV root.

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

**Naming convention.** Earlier design notes in this document used `AMirror`,
`BProxy`, `CMirror`, and `DProxy` as role labels. They are no longer generated
public type names. An SV `pkg::A` is exposed in Python as
`svx_mirror.pkg.A`; a Python `module.B` is exposed in SV as
`svx_proxy_module::B`. The role labels below describe bridge portions only.

For one SV-to-Python boundary, an SV base `A` and Python child `B` need a
paired mirror on each side:

```text
SV:      A <- svx_mirror_sv_<pkg>_A::A
Python:  svx_mirror.<pkg>.A <- B
```

The generated SV `A` bridge extends the source `A`; the Python
`svx_mirror.<pkg>.A` is B's executable base view and creates that SV bridge.
The Python B instance and the SV bridge dynamic object
share one object ID. The SV mirror contains A's normal base portion; the Python
mirror is a base portion of B, not a separately allocated Python object. There
is no SV proxy for a direct `B()` construction.

The SV AMirror overrides each explicitly exposed A virtual member and dispatches
it to the Python object registered under the shared object ID. Its generated
qualified base gateway calls `super.method(...)` to reach A's implementation;
Python `AMirror.super()` uses that gateway. Thus both Python-initiated calls and
ordinary SV virtual calls on the SV AMirror can reach B's Python override
without changing the user's A implementation.

`svx_proxy_<module>::B` is created only when a later Python-to-SV edge
needs B to be an SV base, for example `A(SV) -> B(Python) -> C(SV)`. The C dynamic object
then contains that B projection, which provides B's SV-visible virtual dispatch,
qualified base gateways, and selected projected state. It extends the generated
SV A bridge, preserving A's callback-dispatch layer.

An inherited virtual method reuses the existing SV mirror callback, even when
B declares its Python override in the manifest. BProxy must not generate a
second override for that same virtual slot. Only B's newly introduced
SV-visible virtual methods require new proxy bridges. Inherited explicit base
calls delegate to the ancestor gateway rather than calling a callback override
through `super`. The preceding Python mirror module registers the projected
Python methods' SvTypes contracts without manufacturing another source class.

For a complete alternating chain, each class-specific projection must be
preserved:

```text
SV:      A <- bridge(A) <- svx_proxy_<B_module>::B <- C <- bridge(C)
Python:  svx_mirror.<A_pkg>.A <- B <- svx_mirror.<C_pkg>.C <- D
```

The cross-language links are object bindings, not native `extends` relations.
For a direct B instance, Python AMirror holds SV AMirror's object ID and its
base-call path targets the A base portion. For C and D instances, BProxy makes
B visible as an SV base for C and carries B's additional SV-visible contract.

## Experimental Published-Object Handoff

When Python constructs an instance derived from an SV base, the paired SV
bridge is a real instance of that base class. Existing SV code may consume it,
but only after Python explicitly publishes that one instance:

```python
driver = PythonDriver()
svx.publish_object("env.driver", driver)
```

SV retrieves it with a declared expected type:

```systemverilog
example_driver_pkg::BaseDriver driver;
`SVX_GET_OBJECT(example_driver_pkg::BaseDriver, "env.driver", driver)
driver.drive();
```

`publish_object` is experimental. It accepts only a currently bound SVX
cross-language instance, and its name is an application-defined capability
name, not a general Python-object lookup key. `SVX_GET_OBJECT` first resolves
the published live object and then uses `$cast` to check both the explicit
expected type and the destination variable type. A broad destination such as
`svx_dispatchable` does not bypass the declared expected type. A missing, retired, or
incompatible object terminates simulation. Publishing the same name again
replaces the previous publication. Releasing the paired object or shutting
down SVX removes every publication for that object. Publication does not
transfer ownership or extend the object's lifetime.

## Member Invocation Semantics

Every manifest-exposed A member has a generated Python AMirror access endpoint.
SV `local` members are never exposed; an exposed `protected` member is reached
only through a legal gateway emitted inside `SV::AMirror extends A`.

- A `virtual` member has an SV AMirror override that dispatches by object ID to
  the bound Python object. Its qualified base gateway invokes `super.method()`
  in SV, so Python `super()` reaches A without re-entering the callback.
- A `pure_virtual` member still has a concrete callback override in SV AMirror,
  allowing an SV base-typed handle to invoke the Python implementation. Its
  qualified base gateway has no implementation: Python `super()` raises
  `SVXRemoteError` (an `SVXInheritanceError`) with code `pure_virtual_base` and
  the receiver/method IDs. This applies to function and task calls; failure
  produces no return value or output/inout copy-out. An uncaught callback error
  follows normal SVX callback error handling rather than returning a fabricated
  base result.
- A non-virtual instance member has a Python AMirror wrapper that calls A's
  qualified endpoint. If B defines a Python member of the same name, normal
  Python lookup selects B's member; B's inherited AMirror wrapper remains the
  explicit path to A. An SV call compiled against A remains A's ordinary
  non-virtual call and never dispatches to B.
- A static member is handled the same way as a non-virtual member, except its
  generated endpoint calls `A::method` and has no object ID. The generated SV
  AMirror package registers one class-level dispatcher for A; it carries no A
  instance and only decodes the SvTypes request, calls the qualified static SV
  implementation, and encodes the response. A Python subclass may define its
  own static member under normal Python rules; that does not alter A's static
  implementation or turn static dispatch into virtual dispatch.

Method parameters, function returns, `output` parameters, and `inout`
parameters use SvTypes exclusively. A call encodes each input once. Its result
record contains the optional function return plus named encoded updates for all
`output` and `inout` parameters; the generated SV wrapper assigns those updates
before returning to its caller. This is ordinary copy-in/copy-out behavior, so
`inout` requires no alias protocol.

Python preserves every SV formal in its original order. `input` is decoded as a
value; `inout` and `output` are mutable `svx.Inout` / `svx.Output` carriers.
The override reads or assigns carrier `.value` and returns only its ordinary
function result. Conversely, Python callers supply the same carriers to a
generated Python-to-SV mirror and observe their updated `.value` after the
call. Generated SvTypes request and response records stay private.

Cross-language inheritance methods accept only `input`, `output`, and `inout`
parameters. A manifest with `ref` or `const ref` is rejected during generation.
`inout` is ordinary SvTypes copy-in/copy-out, not an SV lvalue alias. A member
requiring SV ref semantics must remain wholly in user SystemVerilog. An
application may instead define an explicit mutable protocol with SvTypes
objects or getter/setter methods; that protocol is application-owned and is not
an SVX ref facility.

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

Member declaration initializers are rendered through the public SvTypes
`sv_declaration(..., include_initializer=True)` interface. The codec's declared
initializer is distinct from its current mutable value; four-state `Logic`
initializers retain X/Z. String, real, shortreal and enum declaration defaults
use the same interface. Packed struct member defaults become a nested field
assignment pattern, not initializers inside the struct typedef. Unspecified
four-state struct members retain X. Fixed arrays repeat their element template's
declared defaults, recursively for multiple dimensions; dynamic containers remain
empty at declaration. Later mutations of a descriptor instance or individual
array elements do not replace declared defaults. This interface is required in the development dependency
and must be included in the published dependency before release qualification.

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

Source discovery also resolves unnamed closed ancestors, such as
`class Child extends Base#(byte, 4)`. Their lineage entries retain the template
symbol, evaluated specialization arguments, and specialized member types.
Discovery assigns a readable specialization-qualified canonical ID, using the
actual type rather than an intermediate type-parameter alias. Repeated concrete
specializations share that identity. These entries remain ancestry context:
they do not request additional generated classes. A selected Mirror includes
the accessible members inherited through ordinary SV ancestors, and its paired
SV helper supplies the corresponding field and method gateways.
Inherited static methods keep their declaring specialization's canonical ID.
When several closed specializations share a template, the internal static
package contains a separate dispatcher for each specialization. A same-name
static declaration in the selected SV class hides the ancestor method normally.
Static gateway classes are virtual and never instantiated; if their source
constructor requires arguments, they declare a forwarding constructor only to
make the SV inheritance declaration legal. Static calls do not construct source
objects, including when accessing protected static methods.

When SV source is supplied to manifest discovery, the scanner checks the
declared argument count, kind, and order against that source. Generating from
JSON alone checks manifest validity but does not independently verify the
source parameter list; compile the generated SV with the actual source as well.
A generated specialization keeps the source simple class
name, such as `Packet`; its closed parameter list remains on the SV source
reference. Two distinct specializations that would occupy one public generated
package/module are rejected rather than receiving a hash suffix. Open
parameters (`T`) and unevaluated expressions (`f(N)`) are rejected because they
cannot give the generated artifact a stable type or name. Source discovery may
evaluate expressions, including ancestor arguments such as `W+1`; the resulting
manifest must contain concrete types and literal values, not those expressions.

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
unselected Python-owned fields, which remain locally usable. Generated construction
binds selected fields before running the Python initializer. A source declaration
stub by itself does not allocate foreign storage; it is not a live mirror instance.

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
`FieldIdentity` values, and binds them to an SVX object ID. For an
`A(SV) -> B(Python) -> C(SV)` target, generated `AMirror`/`BProxy` code binds
B's selected fields before `B.__init__`; its integration regression verifies that a
Python initialization write is immediately observed through the BProxy field.
The generated SV helpers implement empty-path whole-field `read` and `set`,
plus typed paths through the existing inheritance dispatcher. Deep `read`/`set`
generation walks public SvTypes descriptors to concrete member/index/key SV
lvalues, validating each path step without whole-field read/modify/write.
Queues and dynamic arrays support one-level indexed `read`/`set`, `insert`,
`append`, `delete`, and `pop`; associative arrays support keyed `read`/`set`,
`delete`, and `pop`. The field-projection regression exercises queue and
associative operations without a whole-field writeback. The typed deep resolver
also implements queue/dynamic-array insertion, append, deletion, pop and resize
at the addressed container, plus associative-key creation and deletion. Resize
preserves the surviving prefix and uses normal SV element defaults for growth;
fixed arrays cannot change length. Invalid lengths, indices and missing keys
are rejected without changing the existing container.
Sequence slice assignment/deletion is composed by SvTypes from local element
`set` and, for variable-length containers, `insert`/`delete` operations; it does
not write back the whole container. Extended slices preserve normal Python
length rules. This is not a transactional batch if a backend operation fails.
Directly requested SV
field targets with a declared constructor use the same Python SVMirror field
owner as alternating targets, for both Python- and SV-initiated construction.
SV initiation binds the existing ID and fields before running Python initialization;
it does not allocate another SV object. A failed existing-ID companion initializer
closes its field storage and removes its Python binding, without releasing the
caller-owned SV endpoint. A later wrapper can bind that surviving object again.
A constructorless standalone field view instead accepts a registered endpoint ID;
it exposes the selected fields without allocating an SV instance or changing the
construction selector. The endpoint must already be dispatchable. This is not an
automatic wrapper for an arbitrary raw SV handle.
For both standalone fields and SV-to-Python boundary mirrors, SV-origin
constructor metadata does not prohibit an unbound Python call through the
generated construction path. Its formal parameter names and order are retained.
An already-bound SV receiver
may enter that initializer normally, without requesting a second instance.

Release removes the native Python registry entry before invoking cleanup, so a
failed or reentrant user hook cannot retain that registry reference. The SV
endpoint remains registered while projected storage is retired. Python
`close_instance` uses the nonblocking `svx_release_object_function` gateway;
it retires the SV registry before reporting a cleanup failure. Arbitrary user
hook success is not guaranteed; inherited/generated cleanup closes projected
storage so retained views cannot fall back to Python-local values. Full runtime
qualification of all nested field shapes and the direct native
object-operation ABI endpoints remain implementation work. They are design
requirements, not claims about the current executable surface.

Nested collection packer arguments and local temporaries use the public SvTypes
`sv_codegen_context()` rendering interface and its dependency-ordered local
typedefs. A nested queue field has passed actual whole-field reads/writes and
one-level child updates and two-level indexed reads/writes. The latter use only
the local-operation endpoint; invalid indices leave the stored field unchanged.
Member/key/index combinations also have actual runtime controls, including a
registered SvTypes object with an associative array of queues. Nested queue and
dynamic-array mutation controls cover insertion at the end and into an empty
container, append/pop/delete, growing/shrinking resize, unchanged siblings,
negative-length rejection and missing-key rejection. Object references resolve
their target schema through the codec's type registry, while each nested
container uses the public local typedef rendering context.
This qualified shape does not establish all
nested-field operations or all container combinations.

`SVXFieldStorage` is SVX's implementation of SvTypes'
`ExternalFieldStorage` protocol. A bound owner holds an internal backend for its
selected fields, not a user-facing type or a field-value cache. Its opaque
binding key identifies the pair `(svx_object_id, manifest_field_id)`; path and
operation data are supplied by the owner-resolved SvTypes field instance.
Object IDs must be integers in `1..2**64-1`; booleans are not object IDs.
Indexed path segments use unsigned 64-bit framing and reject larger indices
before transport. This framing range does not imply that an index exists in
the selected SV container. Closed storage rejects reads and writes, including
through retained child views, without falling back to Python-local values.
Generated field endpoints explicitly qualify instance members with `this.` so
user fields do not bind to same-named dispatcher parameters or local variables.
Field names and their manifest identities remain unchanged.
Fixed-array addressed operations use `$size(member)` for bounds checks;
dynamic-array and queue operations use their `.size()` methods.

Malformed value bytes are not a recoverable field transaction. The generated
root write currently invokes the concrete SvTypes unpacker before checking full
consumption; that unpacker can modify values, and trailing bytes terminate the
simulation through `svx_require_unpacked_all`. Object decoding can also reuse
live identities in the SvTypes registry. There is no general rollback guarantee
for these failures; an exception-reporting policy does not turn the SV-side
`$fatal` into a resumable Python exception. Descriptor mismatch checks and
ordinary unsupported-path failures must not be described as transactional
validation of all value bytes.

`SVXFieldStorage.read()` calls the native `read_field` operation and returns
SvTypes bytes. `SVXFieldStorage.write()` calls native `write_field` with the
same descriptor/path/operation semantics through generated typed SV endpoints.
The native layer owns DPI scope, temporary buffers, and error conversion.
On construction rollback, explicit close, or shutdown, SVX closes the owner backend
before releasing the Python/SV object bindings. Selected fields retain their closed
backend binding; detaching it would incorrectly restore Python-local values. Any
subsequent field access fails deterministically instead of reading stale Python
state.
SvTypes reports backend access failures as `ExternalStorageError`; the chained
SVX cause identifies the closed backend.

Internal complete-target SV views also guard cooperative Python descendant
initializers. If the outer Python body fails after its SV target factory has
returned successfully, the newly created pair is closed automatically; callers
do not need a manual `close_instance()` in their constructor exception path.
Nested `super().__init__()` calls share that initialization scope. The wrapper
preserves the source initializer's reflection signature and propagates the
original exception, adding notes for returning cleanup failures. It does not
close an already-bound receiver merely because its initializer is called again.
Factory-stage rollback remains separate. Independent SV-root and Python-root
native/SV tests exercise two successive outer failures, retained-field
invalidation, published-handle removal, and a subsequent successful construction.
The Python-root control also reinitializes an existing pair, catches its failure,
then invokes it through an SV base handle before explicitly closing it.
Custom `__new__`, non-cooperative
metaclasses/subclass hooks, and the complete public-generator workflow remain
unqualified; this internal control is not blanket lifecycle certification.

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

The implementation now emits the class-specific AMirror/BProxy stack for each
selected alternating lineage. A BProxy shares its AMirror object ID rather than
manufacturing a second companion object; downstream SV subclasses therefore
inherit both the SV base state and B's projected state. Its generated base
gateway keeps Python `super()` on the qualified SV base path, while virtual
calls continue through the bound Python override. The integration suite covers both
inheritance directions, intermediate SV subclasses, qualified `super()`,
projected scalar fields, queue paths, associative-key paths, construction and
explicit release.

The field-storage adapter uses the existing object dispatcher with a versioned
field-operation envelope. It binds selected mirror owners before Python
initialization, rejects stale accesses after release, and never maintains a
second mutable Python cache. Direct and one-level collection operations are
implemented as described in the lifecycle section. Deep reads/writes address
concrete leaves. Nested queue/dynamic-array structural operations and mixed
member/key/index paths have executable controls; broader shape qualification
remains implementation work rather than a hidden whole-field fallback.

## Construction

For an executable SV-to-Python boundary or directly requested SV class with
constructor metadata, an unbound
Python mirror calls `inheritance_create_sv(class_id, encoded_constructor)`.
An `initiator: "sv"` declaration on this mirror does not prohibit creating
its Python subclass normally. An already bound SV-origin receiver is reused;
its Python initializer must not allocate a second SV object.
The generated SV mirror factory decodes that SvTypes request, constructs the
mirror, and registers the instance under the returned object ID. The user must
register that generated factory before creating the Python object. All
constructor parameters, method parameters, results, errors, and object handles
use SvTypes codecs; source parsing never infers a competing codec.

Python-origin construction binds only fields physically resident in the
selected SV target. Thus B's new fields remain Python-local when B constructs
its A mirror, while a C mirror binds fields inherited through B's SV proxy.
The residency map does not redeclare ancestor descriptors in a Python
multiple-inheritance view. Local SvTypes collection `.value` reads are
snapshots: assign modified values back. Projected collection values are live
views and retain addressed operations without implicit whole-field writeback.
For SV-origin construction through a BProxy, the paired ID is registered in
the SV base mirror, but Python initialization runs after BProxy's own SV field
initializers. Those initializers must not overwrite Python constructor writes.
This does not wait for every later SV descendant constructor to return.
This construction path also covers standalone mirrors with no projected fields;
absence of fields does not select a different constructor policy. A declaration
without constructor metadata remains an existing-handle view rather than an
implicit factory. An SV mirror within a Python-root staged chain uses the same
rule: unbound construction invokes its selected SV factory, while a bound
receiver validates the staged constructor arguments without reallocating. The
SV factory initializes the preceding Python portions in their existing order;
the mirror's constructor origin does not disable Python allocation.

## Source-Backed Manifest Frontend

Python declarations are opt-in through `@inheritance_class` and
`@inheritance_method`; only decorated classes are top-level generation targets.
The decorator collects direct SvTypes field descriptors from the class body,
including concrete nested collection descriptors, into its declaration
metadata. It is declaration metadata, not a Python inheritance mechanism.
When `constructor_parameters` is omitted, a directly declared `__init__` with
complete SvTypes parameter annotations supplies its ordered input parameter
bindings. `Input[T]` is optional, as for methods. Partial annotations and
`Output`/`Inout` constructor annotations are rejected. Current automatic
discovery requires fixed positional parameters; keyword-only and variadic
signatures are not yet supported by this discovery path. An explicit parameter
list takes precedence, including `constructor_parameters=()`; an unannotated
initializer retains the existing empty-parameter declaration behavior. Discovery
does not rewrite the Python initializer or serialize its default expressions.
Inferred parameter types alone do not establish complete natural-constructor
runtime support or propagation of Python defaults into generated SV signatures.
For an empty `sv_mirror` base without matching explicit SV declaration metadata,
supplying `--sv-source` now discovers that class and its ordinary SV ancestors
as lineage context. This does not add them to the top-level generation requests.
The source compiler supplies effective method qualifiers, constructor parameters,
and accessible fields; `local` members are excluded. Supported scalar types and
their typedef aliases use public SvTypes bindings. Integral discovery preserves
width, signedness and two-state/four-state semantics: `int`/`longint` retain
`Int`/`LongInt`, other two-state integral forms use `Bit`, and `integer`/`time`
use `Logic` (including X/Z). `shortreal` and `realtime` use the corresponding
public floating-point types. Native scalar SV spellings are preserved in bridge
prototypes, separately from their SvTypes wire representation. Field discovery also maps
ordinary queues, dynamic arrays, zero-based fixed arrays, associative arrays
with concrete index types, and conventional packed dimensions through the
compiler's structured type information. Public SvTypes declarations preserve
unpacked dimensions during semantic signature validation. The same collection
mapping applies to method/constructor formals and function returns. Generated
call interfaces use internal SvTypes-derived typedefs so collection parameters,
local call values and return types retain their complete dimensions. An explicit
source collection typedef remains unchanged, including automatically discovered
typedefs: their qualified source names are retained in native method prototypes
and call locals, while their element codecs remain public SvTypes declarations.
This matters for collections of predefined integral types such as `byte`,
`integer` and `time`; wire-equivalent packed types need not be interchangeable
in a source virtual-method return prototype. Method `output` and `inout` parameters retain
the normal carrier and copy-out contract; collection types do not change it.
For a source-discovered alternating chain, generated callback routing preserves
each Python segment. In `A(SV) -> B(Python) -> C(SV) -> D(Python)`, C's qualified
base call through BProxy executes B's implementation, not D's override. Calls
through C's callback-capable mirror can still select D. Consecutive Python
subclasses in the same segment follow their normal Python method resolution;
the route does not jump across an intervening SV class.
Scalar ordinary class handles and concrete, unparameterized virtual-interface
handles are also inferred for fields, constructor parameters and method
parameters/returns. Their wire types remain public SvTypes `RemoteRef` types:
`RemoteRef["sv://package/Class"]` and
`RemoteRef["sv-vif://interface/modport"]` (`full` for no modport). Python
declarations using these annotations acquire native handle metadata from the
supplied SV sources, without separate handle declarations. Referencing an
unmapped class does not request generation of its mirror: its reference remains
opaque and preserves object identity. A VIF reference receives the existing
restricted view inferred from its declared interface/modport. Closed generic
class-handle specializations still need explicit target metadata; source discovery
does not invent a shared identity for distinct specializations. This scalar
discovery support does not establish containers of native handles.
Bounded queues,
noncanonical index ranges, unsupported automatic type mappings and open
parameterized classes require explicit declaration metadata; this is not yet
the complete source-only frontend for arbitrary field types and specializations.
`base_lineage=` accepts the explicit expanded ancestor objects; the resolved
lineage determines which generated foreign mirror is the actual Python base.

SV source is validated with the optional `pyslang` dependency, supplied by the
Slang project. The frontend reads actual package/class declarations, direct
`extends` names, and method declarations. Selected methods must agree with the
compiler's effective `virtual`, `static` and `pure_virtual` state, including
overrides that inherit virtual behavior without repeating the keyword. A manifest
cannot turn a virtual source method into a non-virtual bridge or invent a pure
implementation. Exposing `local` methods/fields is rejected; `protected` members
remain accessible through legal derived gateways. It also rejects an absent SV
class. For example:

```sh
python -m svx inheritance-manifest \
  --sv-declarations declarations.json \
  --sv-source drivers.sv \
  --out inheritance.json
```

Install this frontend with `pip install 'svx[manifest]'`. The declaration file
continues to supply the SvTypes codec contract; `pyslang` supplies source facts.
No regex-based SV fallback is permitted.

Conditional source can use repeatable `--sv-define NAME[=VALUE]` and
`--sv-undefine NAME` options on both `inheritance-manifest` and
`inheritance-gen --sv-source`. For example, add `--sv-define DRIVER_ENABLED=1`
when that macro selects the source declaration. Undefinitions override initial
definitions; conflicting repeated definitions are rejected. These options require
`--sv-source` and affect class discovery, semantic member checks and class/VIF
handle inference consistently. The Python declaration APIs accept the equivalent
`sv_predefines` mapping and `sv_undefines` sequence. Names must be ASCII
identifiers and replacement text must fit on one line.

Use the same initial macro configuration when compiling the SV sources and
generated bridges. SVX does not inject those definitions into generated code.
The CLI artifact manifest records `generation_inputs`: the original manifest
digest, ordered explicit SV source paths, digests of source/include files actually
read by the parser, and normalized initial macro configuration. Paths are relative
to the artifact manifest. `--check` rejects changed inputs even if generated code
is unchanged, and never updates those records during a check. Regeneration refreshes
them. Add repeatable `inheritance-gen --python-source FILE` arguments for Python
declaration, implementation or codec-factory files that your generation workflow
depends on. Their digests are recorded as `python_sources`; duplicates are folded
into a dependency set. They are also protected from output overwrite and obsolete
output cleanup, even if a file carries a generated marker. Missing files are
rejected before output writes. This option records inputs without importing or
executing them. It does not automatically discover transitive Python imports or
refresh the input manifest: rerun declaration discovery when that manifest changes.
Inactive include branches are not dependencies until selected; unlisted Python
source files and external build scripts are not covered by this record. Runtime startup
does not require these source files to be deployed or validate their digests.
Separately, ordinary source modules newly imported during generation's codec
materialization are compiled from current source and revalidated before the
command returns a check result or writes outputs. They receive input overwrite
and pruning protection even without an explicit audit argument, including files
with an old generated marker. This per-invocation protection neither persists a
complete dependency graph nor changes cached modules or custom import loaders.

By default, source files are separate parse inputs. Add `--sv-compilation-unit`
to either inheritance command to parse all repeated `--sv-source` files, in their
given order, as one shared compilation unit. The equivalent Python API option is
`sv_compilation_unit=True`. This preserves source-defined macros between files
and applies the same unit grouping to class/VIF discovery, semantic checks,
handle inference and include dependency protection. A definitions-only file can
precede the package files without requiring an artificial package declaration.
Use the same source ordering and unit grouping for actual compilation.

The artifact input record identifies the selected mode; switching it makes
`--check` stale even when the generated code is identical. Parse errors retain
the actual source filename and line, including later files in the unit.
`--check` does not certify the compiler command or record complete build-option
provenance. This is one ordered unit, not a general build-file/library frontend.
Libraries and multiple independently configured unit groups are not added by
these options.

Use repeatable `--sv-include-dir DIRECTORY` options on either inheritance command
for additional include search directories; the API accepts `sv_include_dirs`.
Directories are passed to the same parser configuration used by all discovery,
semantic validation and dependency passes, in the specified order. Relative
directories are interpreted from the command's working directory. Include names
in the source are not rewritten. Match the actual compiler search paths/order,
especially when different directories contain headers with the same name.

The artifact input record stores the ordered directories relative to its location
and records only the selected header dependencies. Changing search order makes
`--check` stale even if the resulting code is unchanged. A selected header also
receives the input-file overwrite/pruning protection below. Additional include
directories are also consumed by the integrated source assembler. It copies
parser-selected active physical includes into the
generated source unit before integrating declaration anchors, without modifying
the original headers. Include filenames may use object-like, nested or
function-like macros; their physical invocation ranges are obtained from the
parser rather than by modifying macro definitions. The public integrated output
mode uses this backend; this does not qualify arbitrary source macros. It also supports an object-like,
nested or function-like macro used only for a proxy base type: it rewrites that
physical invocation, not the macro definition or other uses. A macro that also
emits a declaration delimiter or another member is rejected rather than having
that syntax silently removed. Macro-generated whole-class declaration anchors
remain unfinished.

Generation refuses to overwrite or prune its input files, even when an input
has an older SVX-generated marker. For `inheritance-gen`, this protects the
manifest and supplied SV sources plus active include dependencies, including
hardlink aliases. Protection covers both current output paths and obsolete
files selected for cleanup, and runs before any generated file is written.
`inheritance-manifest` also refuses to replace its declaration files, supplied
SV/include sources or directly requested Python modules with the output JSON.
Keep source inputs and generated outputs distinct; an existing generated-file
marker is not permission to destroy a file currently used as an input.

## Frozen Generator and Runtime Contract

The following choices are normative for the complete implementation.

### Field Manifest

Every class object has a `fields` array, defaulting to `[]`. In the current
manifest, each item contains `name` and `type`; `type` is the same validated
SvTypes type binding used by method parameters, including a public codec
identity and encoding descriptor. The frontend discovers directly declared
Python SvTypes fields and renders their SV declarations through public
SvTypes APIs. There is no accepted `field_descriptor` key today.

The complete design additionally requires preserving source field construction
values and declaration policies in a public field descriptor. That descriptor
transport is not implemented by the current `{name, type}` representation;
do not assume a Python descriptor's default/randomization policy is thereby
copied into a generated SV member.

There is a narrower implemented exception: a concrete source codec factory
retains a two-state packed declaration value. For `Bit`-derived codecs (including
`Int`), the generator uses the public `sv_repr()` expression for nonzero member
initializers; zero keeps the native two-state default. Tests cover signed and
unsigned values, and runtime validation observes an SV-resident `Int(17)` before
the Python initializer body runs. A canonical type identity describes layout,
not the source declaration's initial value or policies, and cannot reconstruct
them on its own. This does not establish complete declaration preservation:
four-state `Logic` initializers, container/object defaults, and randomization or
coverage policies still require the complete public field descriptor contract.

Only direct source fields are emitted in a class's `fields` array. The same
normalization is applied to Python source fields and to SV fields explicitly
annotated as SvTypes fields. The generator reconstructs and validates the
descriptor through public SvTypes APIs before generating code. A raw SV type
string, handwritten binary layout, or SVX-local field codec is not an
alternative contract.

### Planned Source-Managed Mirror Interface

The following source-managed executable interface is an agreed design target,
not the current public API. `mirror_method`, `parameter`, and `_svx_call_base`
in this sketch do not exist. Current `sv_mirror` supports empty source declarations:
loading the matching generated mirror installs it as the declaration's base,
preserving already defined user subclasses and their ordinary `super()` calls.
Generated modules can be loaded through the artifact configuration or imported
directly. Importing or decorating a source declaration does not allocate an SV
object; attempting construction before its implementation loads raises an error.
The full explicit method/field declaration validation in the sketch and automatic
source-only discovery for arbitrary types remain unfinished frontend requirements.
Scalar SV ancestor discovery and named SV Proxy edge discovery are available as
described below. Python-introduced members use the existing SvTypes field and
method declaration renderers in the temporary discovery scaffold; arbitrary
complex source-type discovery still needs further qualification.

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

### Public Generated Type Names

Generated bridge types are public at the language boundary and retain the
foreign source class's simple name. For SV `drivers_pkg::A`, Python imports
`svx_mirror.drivers_pkg.A`. For Python `uvmx.env.agent.B`, SV derives from
`svx_proxy_agent::B`; the package stem is the final Python module component.

The SV subclass that must override an SV source's virtual members remains an
implementation artifact because SV needs a real derived dynamic type. It is
named `svx_mirror_sv_drivers_pkg_A::A`, not `AMirror`. The generated Python
`svx_mirror.drivers_pkg.A` class and the generated SV
`svx_proxy_agent::B` class directly own their bridge behavior; no extra public
facade or `*Mirror`/`*Proxy` type is emitted. The artifact manifest records
these public full names by canonical class ID.

Two Python source classes with the same simple class name and final module
component would request the same SV full name. That is a generation error; it
is never resolved with a hash or an order-dependent suffix.

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

When `inheritance-manifest` receives SV source files, declaration checks include
method kind, formal order/direction, and semantic parameter/return types for
the supplied SvTypes bindings. Expanded SV ancestor declarations are checked
too. Declared constructor formals are checked for count, order, direction and
matching type; an implicit constructor does not inherit its parent's formals.

Python declaration discovery also expands an annotated direct Python parent's
complete `base_lineage`, followed by that parent's own declaration. The parent
may come from an imported module that was not selected for discovery: it supplies
ancestor context but is not added to the top-level generation targets. Source
decorator metadata is not mutated. A direct `sv_mirror` base instead selects its
matching SV declaration; an older mirror reached through another Python base's
MRO is not mistaken for an additional direct mirror. In `D(CMirror, B)`, CMirror
therefore selects C's declared lineage, which must describe the logical B portion.
Discovery itself does not install executable forwarding behavior into a source
mirror; generated mirror loading performs that separate runtime operation.

Selected fields are checked against their actual source member types, including
inherited fields. This validates type compatibility, not source initializers,
randomization policies or packer implementation bodies.
The frontend resolves typedefs, imports, inherited methods and closed
specialization arguments with pyslang, then applies SV matching-type rules;
assignment compatibility alone is not enough. For selected RemoteRef fields,
source discovery resolves typedefs, imports, inherited members and closed type
parameters before adding class/VIF handle metadata. When supplied sources resolve
a native handle type, equivalent aliases and default specializations are normalized
across fields, constructor parameters, method parameters/returns and Python-origin
metadata, including expanded ancestors. A shared handle target must have one matching
static SV type. Explicit opaque types whose definitions are absent remain unchanged;
they have not been source-validated. JSON-only input requires consistent explicit
static types. No additional class is
selected merely because a field refers to it; by-value SvTypes object fields
are not reclassified as native handles. Native handle metadata supplies the actual
SV class/interface type rather than the RemoteRef wire carrier.
Missing type dependencies produce a diagnostic instead of an unchecked match.
JSON-only input cannot provide this source validation, and this does not yet
constitute a complete build-file, conditional-compilation or source-managed
projection frontend. A body-only source edit leaves an unchanged generated
manifest untouched; a type mismatch fails before replacing that manifest.

A standalone SV field view without constructor metadata preserves its existing-ID
wrapping contract. It initializes the SvTypes owner, binds the registered endpoint
and selected fields, and retires only its own Python binding on initialization
failure. It neither allocates a second SV object nor registers its Python subclasses
as SV construction targets. The existing endpoint must already implement the
declared dispatch gateways; this is not reflection-based wrapping of a raw SV handle.

Generated call and constructor contracts can be registered repeatedly after use.
Compiler/codec caches are not part of the declaration's identity, and equivalent
registration preserves those caches. Changes to parameters, wire types or timing
still conflict; this is not a mechanism for changing live call signatures.

The SV source contains a named proxy declaration marker, not a handwritten
duplicate implementation:

```systemverilog
`SVX_PY_PROXY(BProxy, "py://checks/B", A)
class C extends BProxy;
  // ordinary user SV implementation
endclass
```

During source discovery the marker supplies the B-to-C projection edge: its
Python canonical ID resolves an imported annotated Python ancestor, and its SV
base must match that ancestor's Mirror base. The parser uses a temporary class
scaffold, respecting includes and conditional compilation. The scaffold is not
a logical ancestor or a requested generation target. Combined with Python Mirror
stubs, this discovers A(SV), B(Python), C(SV), D(Python) while retaining only D
as the selected top-level target. Integrated generation accepts the marker name
as C's base and supplies a typedef to the generated local B helper; users do not
need to rewrite C's base to an internal helper name. The helper is inserted at
the marker declaration, including when that declaration belongs to a separate
package. That package must follow the SV base's package and precede its consumers.
Invalid declaration order is reported rather than repaired by moving user code.

The semantic scaffold includes B's declared SvTypes fields and exposed method
signatures, including inherited Python portions since the preceding SV boundary.
Consequently, C's overrides of B-introduced virtual methods retain their effective
virtual status even when C does not repeat the `virtual` keyword. Source facts,
signature checks and native-handle type resolution use this same member context.
The scaffold has empty method bodies and no construction behavior; it is neither
compiled as the runtime Proxy nor added to the generation target list. This does
not remove the separately documented limits of complex automatic source-type
discovery.

With the normal runtime macro definition the marker expands to no class at
compilation time; the manifest
generator remains the authority that emits the complete
`class BProxy extends AMirror`: selected B SvTypes fields, typed field
operations, bridges for newly introduced virtual methods, delegation to
inherited explicit base-call gateways, and the factory.
It is emitted only when B has a downstream SV inheritor. A one-boundary chain
may use one generated include. An alternating chain instead uses source-order
includes from `inheritance-gen --sv-stage-dir`: `common.svh` is included once,
an `after_*A*.svh` file follows A, a `before_*C*.svh` file precedes
`class C extends BProxy`, and an `after_*C*.svh` file follows C to define
`CMirror extends C`. This is required because SystemVerilog does not allow a
class to extend a not-yet-declared base. Current fragments define separate
packages and must be included at compilation-unit scope, outside user packages.
A and C in the same user package cannot be integrated by inserting these
fragments between their class declarations. Distinct helper names do not remove
that dependency cycle. Public generation checks package ordering before writing
output and reports involved packages and target IDs. The public
`inheritance-gen --sv-integrated-dir DIR --sv-source FILE` path instead assembles
an ordered source copy with local helpers and public aliases. Multiple files
require `--sv-compilation-unit`; compile `DIR/source.sv` instead of those originals.
It supports the qualified same-package and mixed-root controls without requiring
users to split packages or Python modules. Arbitrary source forms and natural
constructor routing remain incomplete, as described in the status boundary.
The manual stage filenames carry a stable
canonical-ID hash and are covered by the generated-artifact manifest. An empty
handwritten BProxy stub is not supported because it cannot provide valid member
types or virtual method bodies.

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

### Generated Object Operations

SVX provides generated object operations through construction functions,
function/task dispatchers, and versioned field-operation envelopes. The operations
are `construct`, `invoke`, `read_field`, and `write_field`; each
names an SVX object ID, a manifest member ID, and where relevant an addressed
SvTypes field path. `write_field` additionally carries a collection operation
code when the path addresses a mutable container. Payload and result bytes
always use the member's validated SvTypes descriptor.

Generated BProxy code provides typed SV endpoints for these operations. The
native layer routes object/member IDs to generated SV dispatchers and owns DPI scope,
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

The complete construction design calls for one SvTypes `ConstructionRequest` record for the
dynamic target. It contains an ordered, canonical-class-ID-keyed constructor
argument record for every constructor in the resolved lineage. This removes
ambiguous flattened parameter names and lets generated BProxy/DProxy factories
forward exactly the argument record belonging to each SV or Python base. A
generated user-facing constructor may offer convenience keyword arguments, but
it would serialize them into this single record before crossing the boundary.
An internal transport foundation now builds this request from the resolved
lineage. The outer SvTypes record contains the dynamic target ID and an ordered
pair of canonical owner ID and argument-record octets for each portion, including
zero-parameter portions. Each inner record uses that owner's own SvTypes field
types; repeated parameter names in different portions cannot alias. Decoding
checks the target and every owner ID before decoding the inner records. A real
Python-to-SV-to-Python transport control covers independent integer values, an
additional string parameter, a zero-parameter stage and an SV-side update.
This is not yet wired into generated construction. `register_constructor` /
`encode_constructor` and current factories still use one ordered parameter
record for a class ID. In particular, a later Python Proxy currently forwards
its own constructor arguments into the preceding SV helper rather than selecting
an independent ancestor record. Earlier alternating object regressions use
compatible arguments; they do not prove general heterogeneous ancestor construction.
An additional actual-object control now covers constructor arities 1, 2, 2 and 0
in a Python-root alternating chain: Root takes an integer, Child and Derived take
an integer/string, and Grandchild takes no arguments. Child's source constructor
computes `super.new(child_seed + 10)`; Grandchild supplies its own fixed
`super.new(7, "abc")`. Both construction origins preserve these source calculations,
initialize each Python portion once on the same receiver, dispatch through a root
handle and clean up the paired objects. This qualifies that concrete source-managed
shape, not arbitrary independent argument routing or portable constructor ordering.

Direct Python `Derived(23, "hello")` can also transform its `super()` argument
to 24: at that point the SV Child is not constructed yet, so it is created with
24 and Root observes 34. The unresolved case is a more-derived dynamic target:
its SV chain has already constructed Child with 7 before the later Python Derived
initializer requests 8. The staged guard rejects that mismatch rather than silently
discarding it. These cases require different execution ordering, not merely different
record field names. Full routing must obtain arguments from the source Python
`super()` execution before the corresponding SV ancestor is constructed, without
replaying initializers or duplicating their side effects. It must retain synchronous
user construction; this is not permission to introduce async user constructors.
An internal constructor-continuation component now retains separate suspended
segments for each receiver and language boundary, preserves the original Python
initializer stack, and can cooperatively unwind a failed receiver's segments.
It uses greenlet internally, without changing the user's synchronous API. A
complete alternating-chain experiment validates the ordering, but the component
has not yet been wired into the production generator, native registration and
projected field lifecycle. Existing generated staged constructors therefore do
not yet gain arbitrary natural argument routing from this component alone.
The internal request codec is not exported as a user API and is not a substitute
for preserving natural user constructor signatures or source `super()` behavior.
The internal staged path now records the actual argument values used by each
completed SV helper constructor. During a later Python initializer stage, a
bound Mirror's `super().__init__(...)` checks those values rather than silently
discarding the supplied arguments. A mismatch fails construction through the
existing error/rollback path; ordinary later reinitialization is not classified
as this staged base call. The real negative control changes a seed from 19 to
20 and confirms failure instead of an apparently successful object initialized
with 19. This check exposes an implementation gap; it does not make parameter
transformations illegal in the intended model. Complete routing must respect
source `super.new(...)` and `super().__init__(...)` computations, and must not
overwrite them merely because the request contains separate ancestor records.

Cross-language virtual dispatch is unavailable until the relevant binding has
completed. A virtual boundary call attempted during an unbound construction
phase fails through the inheritance error path (`SVXInheritanceError` or a generated
SV fatal diagnostic); SVX must not silently call a
wrong base implementation or manufacture a partial companion object.

### Python-Root Owner Initialization

This is a construction design requirement, not an executable Python-root
generator interface today. A root such as `B(SvObject)` must keep its natural
initializer, including `super().__init__()`. A plain `B()` remains Python-local.
An SV-derived target needs a generated companion initialization portion that
participates in that normal `super()` chain: complete the SvTypes owner
initialization, bind the selected target-resident fields, then return to the
user initializer. The source class, its signature, and its field declarations
must not be rewritten or monkeypatched. This portion does not add a logical
class or a code-generation target to the manifest.

Simply pre-binding and then running `B.__init__()` is insufficient: owner
initialization can reset the external-storage mapping. Conversely, directly
calling `SvObject.__init__()` outside the source initializer can violate
coverage-group construction rules. Generated construction must preserve both
storage routing and the normal host-initializer context for coverage. Owner
initialization must occur once per physical Python instance; later mirror
portions must not reset earlier bindings or allocate a second companion.

The private owner runtime portion verifies that the initialization portion can
preserve the first user field read/write and leave independent plain instances
local. Tests also cover the existing constructor codec/factory entry, duplicate
binding rejection, exactly-once owner initialization, failed-init cleanup, and
constructor wait rejection. These owner-runtime tests use an in-memory
transport and registry substitute, not an SV constructor, so they do not
prove root-proxy object-ID registration, full dynamic-target construction,
heterogeneous ancestor arguments, or complete alternating chains. Those remain
required integration work; source constructors that access fields before
their required owner initialization are not made valid by this prototype.

The internal SV projection emitter now also has a Python-root constructor mode:
the root proxy implements the SVX dispatch interfaces directly, with no invented
SV ancestor and no `super.new()` call. A focused native/SV fixture verifies
SV-origin object-ID registration, a bound Python-root companion, constructor
field reads/writes through real SV storage, a virtual function callback, local
plain-Python instances, and stale field rejection after release. That fixture
uses internal emitters; it does not use a completed public
lineage generator. Public companion/factory integration, later D/E portions,
and heterogeneous ancestor arguments still require integration. The internal
child, explicit-base, static and Python-origin paths described below do not
yet constitute the public full-lineage workflow. Public emitters
continue to reject the incomplete full Python-root chain rather than treating
this constructor foundation as complete inheritance support.

The focused fixture now obtains its companion class and registrations from the
internal companion emitter rather than maintaining them by hand. The emitter
imports the unchanged source root, adds the owner-init portion, preserves its
simple name and reflection signature, and emits the SvTypes call/constructor
contracts and selected field map. Actual initialization failure also verifies
native unbinding and invalidated projected storage without rolling back SV
writes already performed. That initial probe explicitly loaded the generated
module; subsequent artifact-based loading is described below. Public target
selection, complete SV helper layout, full factories and
later lineage portions are not yet integrated.

For a source root that does not derive from `SvObject`, the generated companion
provides an initializer adapter: initialize the paired owner, then invoke the
unchanged source initializer with its original arguments. The adapter executes
within normal SvTypes host-construction context. A cooperative source `super()`
can reach the common owner again without resetting it; a source that does not
call `super()` needs no bridge-specific change. Ordinary source instances are
not modified and remain Python-local. Focused native/SV evidence covers a plain
root with no projected fields, SV-origin construction, virtual function dispatch
and registry retirement; unit tests also cover cooperative initialization and
failure cleanup. This does not prove all plain-root field/coverage combinations
or enable public complete Python-root lineage generation.

The internal root fixture now also verifies an actual SV child of the generated
Python-root proxy. A root-typed SV handle dispatches virtually to the child's
override; the child's `super` call enters the original Python root portion.
Both handles and the bound Python companion retain one object ID, and the
inherited projected field is shared. The root callback carries internal
explicit-base routing metadata so a competing method on the Python receiver
does not redirect this `super` call into a later mirror or override. Ordinary
callbacks remain dynamically dispatched. Routing metadata does not change the
canonical SvTypes request/response schema, user arguments or return values.
The generated companion identifies the actual source class for the root
portion, and a missing portion is rejected rather than dynamically guessed.
This is focused SV-origin root-to-child evidence. The additional internal
Python-origin child path below does not complete public factory integration,
static artifact loading or subsequent D/E portions.

The internal root emitter also provides Python-source static function and task
bridges. A static callback selects the declared source `@staticmethod` without
constructing or looking up a companion; its registered source is cleared at
session shutdown. Function callbacks retain the no-wait rule, while task
callbacks use the normal synchronous blocking context. Static and nonvirtual
source members are emitted with their actual SV qualifiers: a root-typed SV
handle selects the root nonvirtual implementation even when a child hides its
name, and qualified root/child static calls select their respective class
implementations. Focused native/SV evidence includes static calls before any
instance exists and after all instances are released, and timed static tasks.
Python static declarations are valid logical manifest data. Standalone Python
source proxies now use public emission: the generated Python import registers
the source static methods, SV callbacks use receiver ID 0, and a separate
non-inheriting static gateway serves generated Python static views without
constructing a source object. The public CLI/native regression verifies both
directions, timed tasks and function no-wait rejection. SV-root projected Python
portions also generate static members and declare their exact source symbol for
lazy class resolution. Qualified B/C static calls and Python D shadowing retain
source ownership; timed inherited static tasks have public staged-generation
regression evidence without requiring an instance first. Complete Python-root
projection generation remains unfinished for the separate construction/layout
reasons described above.
This does not replace the
complete lineage, factory, layout and loading requirements above.

The internal child-view emitter now generates a Python C view derived from the
generated root companion, preserving C's simple name and constructor formal
names. Its Python-origin constructor reuses the existing SV factory and stages
the root initializer on that same Python receiver. The supplied-ID root SV
constructor binds the receiver before decoding root arguments and runs the
root initializer synchronously, before control returns to the C constructor
body. A pending-construction context is restored after nested construction;
it does not create a second companion. Without a pending Python construction,
the supplied-ID path remains registration-only.

Focused native/SV evidence verifies that C observes the root's initialized
field in its constructor, the root initializer runs once on the caller's
receiver, root and C fields share one storage backend, method calls reach C,
and both retained field views become stale on close. It also exercises nested
C construction during root initialization with separate object IDs. Root
`seed` and C `child_seed` records follow the actual SV `super.new()` arguments;
this is not proof of the planned heterogeneous ancestor-record protocol.
The initial fixture explicitly generated and loaded these internal modules;
the current Python artifacts and loading are derived automatically below. The
public integrated CLI now derives target artifacts and consumes the qualified
Python-root source layout, including both construction origins. That combined
control does not prove arbitrary dynamic-companion selection, D/E constructor
shapes or the planned heterogeneous ancestor-record protocol.

The focused fixture also exercises a later user-defined Python portion
`D(CMirror, B)`, with B the original Python root. Python construction initializes
the root once on D's receiver; D's initializer resumes after the C constructor.
An emitted C helper bridges its virtual method back to D. Both root-typed and
C-typed SV handles reach D's override, whose `super()` uses the explicit C
gateway and then the original root portion without a callback cycle. Nonvirtual
methods still follow SV static-type selection. A new D SvTypes field remains
Python-local and usable after close, while the selected root/C fields become
stale. The fixture now derives callback requirements from complete manifest
lineages and shares one C helper/factory for direct C and later D/E receivers,
instead of manually switching duplicate factories. Complete public target
SV layout and helper/factory selection remain integration
work; users are not expected to reproduce this internal fixture glue.

For the internal SV-origin B/C/D case, the root proxy now queries a generated
virtual constructor selector. D's proxy overrides that selector with constant
root/target metadata, allowing the root constructor to allocate the final D
companion once. It binds that receiver before decoding and executing B's root
initializer; C's SV constructor body then runs; D's proxy finally executes D's
unchanged initializer on that same receiver. A generated target companion
combines the selected ancestor/own field map and original Python base portions.
Root, C and D selected fields share SV storage in this SV-origin case, unlike
D-only Python construction where D's own fields remain Python-local.

Focused native/SV evidence verifies root initialization before C's constructor,
D initialization afterward, one receiver/ID, base-handle virtual calls, shared
field mutation, and stale storage after release. Unit negatives reject invalid
targets, duplicate binding, repeated/reentrant portions and malformed records;
root/later initializer failure retires its acquired Python binding and closes
projected storage. A real automatic later-initializer failure also preserves the
original Python exception and terminates simulation through the FATAL policy.
The internal runtime now separates final receiver identity from an ordered
Python initializer list. Generated targets carry their exact portion plan;
the runtime validates ordered ancestry, consumes each stage before entering
user code, and rejects skipping, duplicate execution or reentry while another
portion is running. Python-origin factories must complete all planned stages.

The internal B/C/D/E fixture verifies both construction origins. E's generated
view derives from the D companion, and E's SV helper selects that view as the
final receiver while retaining D as a Python initialization stage. B initializes
before C's constructor body, D initializes before E's body, and E observes D's
initialized field. E virtual calls reach the original D implementation through
the preceding companion rather than recursively invoking E's Python wrapper.
Root/C/D/E selected fields remain on one SV storage backend and become stale
together. An additional Python-origin F derived from E is now verified with
native/SV calls through inherited base handles. Its F-only field remains local
to Python; closing the pair invalidates the projected Root/C/D/E fields without
invalidating that local field. This does not qualify SV-origin F construction.
Callback routing uses the full method ID's SV owner: C's callback selects the
original D portion, while E's callback retains dynamic dispatch to F. An
explicit Python-base call still selects the original base implementation.
Adding F must not change the result for a plain E receiver. Ordered-runtime
unit tests also cover a further Python initialization stage, but that stage is
not yet qualified through an additional native/SV constructor chain.
Public target selection/loading,
heterogeneous ancestor constructor records, complete method/type/default
matrices and failure/lifetime qualification still remain pending.

The fixture now declares D's actual `check` override instead of omitting it
from the manifest. DProxy reuses C's existing callback bridge, preserving E's
`super()` path without a duplicate D callback cycle. The public SV-root
alternating fixture likewise declares B's override, executes its explicit A
base call, and verifies a newly introduced B virtual method through both
Python-created D and SV-created C. These focused cases do not qualify every
method signature, inherited visibility or deeper construction/lifetime shape.

Internal planned emitters now derive the logical root, preceding Python
companion, selected ancestor fields and ordered Python initializer portions
from the full target lineage. They can also recover an ancestor source's
prefix from a target-only manifest without promoting it to a top-level target.
Each individual emitter still emits only its requested class portion; it does
not reproduce user ancestor definitions. Companion module locations are now
derived from the established naming rules; SV source ordering and helper
layout are still supplied by the integration fixture, not a finished public
artifact path. The same shared C helper is verified with
direct SV-origin C construction as well as the D/E chains.

Internal module assembly now groups requested portions without duplicating
their ancestors. One shared module reserves every public class name before
choosing helper import aliases and emits a single future-import preamble.
Plain Python companion initialization uses local imports instead of depending
on global aliases that a later class could overwrite. Collision tests cover
public class names matching source aliases, registration functions and owner
helpers, while preserving original constructor signatures and source behavior.
The native fixture places C and E together at
`svx_mirror.python_root_probe_pkg`, with unchanged `Child`/`Grandchild` class
names; D and F import these qualified types directly. Both construction origins,
virtual/base routing and stale-field checks still pass, and a runtime namespace
check verifies signatures and that legacy per-class modules were not imported.
Python-root companions and SV mirror views carry the same ancestor callback
boundary routing. A fresh runtime regression exposed missing routing on the
SV-origin companion: a later Python portion could be constructed but then fail
when an ancestor's generated callback gateway invoked it. Both generated
surfaces now map each SV ancestor boundary to the following Python portion.
The internal fixture verifies SV- and Python-origin descendants through the
later Python and SV portions, including initialization failure rollback. This
does not open the public full-lineage generation gate or qualify arbitrary
constructor shapes.

Python-root artifact assembly now selects the companion and mirror portions
from complete projection edges, groups them by the existing `svx_py.<module>`
and `svx_mirror.<package>` rules, and generates package initializers. It does not
generate an F companion or FProxy merely because F occurs as the final Python
target. The startup artifact manifest supplies import paths and loads modules;
the native fixture no longer has hand-written companion maps, generated Python
search paths or `svx_load` calls. Startup does not execute hosted or plain-root
user constructors. A corrupted artifact hash fails before importing the user
source module. Existing construction, virtual/base/static dispatch, field
residency and initializer-failure checks remain in the same native regression.
The fixture's SV helper types still use its internal single-package layout,
reported truthfully in that fixture's artifact metadata. Public Python-root
CLI generation, formal SV helper/package selection, heterogeneous constructor
records/defaults and complete source-discovery integration remain unfinished;
the public generation guard is retained.

For the SV-root construction path, Python-origin construction allocates the ID,
constructs the final SV projection, registers and binds it, then runs the
Python initializer.
SV-origin construction uses the generated AMirror constructor path to allocate
and bind the receiver when `new C(...)` omits its optional internal object-ID
argument. In the internal source-managed SV-root path, AMirror only reserves
that receiver; the first Python proxy invokes B's initializer after its own
SV field declaration initializers have taken effect, before C's constructor
body resumes. Binding is not permission to run user initialization early.
Earlier internal fixtures passed that optional ID through a marked C constructor.
The current internal SV-root experiment instead carries it in a receiver-scoped
context, leaving ordinary C/E source constructors unchanged. Generated helpers
for the same receiver borrow a frame; a nested receiver owns a separate frame.
Frame entry now uses a generated hidden constructor parameter's default
expression. This preserves the receiver during source-base construction without
executing a constructor local initializer before `super.new()`. The bookkeeping
parameter is not a user manifest formal and does not require modifying ordinary
source constructors. The context type is bound through a class-scoped typedef
whose generated name avoids declared fields, methods and parameter names.
Constructor expressions use that alias: a user parameter named `svx_pkg` or
`svx_construction_context` must not redirect the context type lookup or require
renaming the user's parameter. Focused two-root regressions cover normal, early-callback,
literal and nested construction with no prior constructor-order warning. Complete
source-managed generation, natural heterogeneous argument routing and cross-tool
qualification remain prerequisites for opening the public entry point.
An early-callback failure was reproduced with a real receiver: an SV source-base
constructor called a virtual method overridden by its Python portion, but the
internal path dispatched with object ID zero before Python receiver binding.
The internal source-managed SV-root path now reserves a receiver on that early
callback, registers the same SV/Python identity and binds projected fields without
running the Python user initializer. Its first Python proxy initialization stage then
resumes that reserved receiver without reconstructing its SvTypes owner or
invalidating field views. A focused `A(SV) -> B(Python) -> C(SV)` test qualifies
both SV- and Python-origin `C`: early virtual dispatch observes A's value 11 and
zero-valued later SV portions; final dispatch observes 135 after initialization,
and close retires the unique receiver. Existing ordinary construction still passes.
An additional nonzero-default regression covers both construction origins:
B's projected field declares 17, B's initializer reads 17 and writes 23, and
C's constructor observes 23. The final virtual call returns 135. Both receivers
are closed and retained projected field views become stale. Running B's initializer
inside AMirror was incorrect: it observed zero and its write was subsequently
overwritten by BProxy's declaration initializer. The corrected stage order does
not remove declaration defaults or relocate projected fields into Python storage.
Reservation is also retired by the normal projected-storage release hook. A
receiver released during an early callback must not remain in the Python
reservation table or resume user initialization. The internal regression covers
both origins: close removes the native binding and reservation reference, then
the next constructor stage reports the retired receiver and terminates simulation.
Cleanup errors do not retain a reservation; closing inside a user initializer
also prevents that stage from completing successfully. These focused cases do
not qualify the full early-error, cancellation or custom lifecycle-hook matrix.
The internal SV-root generator now also preserves the original receiver for a
direct Python `B()` extending the generated A mirror. Before allocating the SV
base, its constructor records that Python receiver. The early callback binds
that same instance and only A's SV-owned fields; it does not create another B,
run B's initializer again, or project B's new fields into a BProxy. The original
Python constructor stack resumes after A returns. A real direct-B regression
observes 11 during A's constructor and 35 after B completes; close invalidates
A's projected fields while B's local fields remain usable. The pending context
is reset on success and failure, and a mismatched returned ID triggers rollback.
This internal path is not enabled by the public simple-boundary generator; the
existing public complete-target generation guard still applies.
The same internal generator records the mirror's own physical SV field map so
that an SV-origin A helper can reserve an A receiver without a pending Python
factory. This is an exact generated-type selection, not a request to manufacture
B or another descendant. A focused regression qualifies both Python `A()` and
SV helper `new A()`: early and final dispatch observe 11, field writes are visible,
two distinct Python owners are used, and close leaves the registries and context
frames empty. A second regression closes each origin during the early callback;
the next constructor stage fails explicitly rather than silently accepting a
retired literal receiver. A further runtime matrix creates an inner SV A mirror
before the outer receiver's first callback, with outer Python A, Python B, SV A
mirror and SV C. All four cases restore the outer frame and preserve distinct
receiver identities, initialization stages and field residency. Eight receivers
are fully released before shutdown, with no remaining native binding or Python
reservation and with stale projected views. This proves those four shapes,
not every nested target, allocation hook or initializer combination.
The reservation hook now also applies to later SV-root bridge portions. A
five-portion `A(SV) -> B(Python) -> C(SV) -> D(Python) -> E(SV)` test observes
11 during A's constructor and 135 during C's constructor, before D initialization;
final E dispatch returns 1535. It covers SV-origin E, Python-origin E and terminal
Python D, including D's Python-local fields versus E's projected fields.

Internal source-managed factories announce the allocated SV object ID before
entering user constructors. The pending Python construction matches that ID,
not just the class: an SV constructor may create an independent nested receiver
before its own first virtual callback. Real tests cover both different and same
target types (outer E and inner E), restore the outer construction context, and
close all receivers without stealing the pending Python owner. The announcement
uses the existing internal DPI function protocol and does not execute user init.
The nested runtime checks explicitly inspect native/Python bindings and projected
view invalidation before shutdown. Earlier nested fixtures removed only an SV
registry entry; that did not prove paired release, because the Python binding
survived until shutdown. Those fixtures now use the complete internal release
gateway and require the stronger checks. Private registry removal is not a
substitute for `close_instance()` in application lifecycle code.

This is not full early-callback qualification: additional direct-mirror shapes,
arbitrary branching/defaults, custom allocation hooks and early exceptions still
need separate proof. The public generation guard remains, and
cross-tool qualification of constructor context entry is incomplete. Construction-time callbacks
must preserve the SV stage order: dispatch can reach the derived implementation
before that portion's declaration initializers or constructor body have run.
Binding a receiver must not be conflated with running its Python initializer early.
A failure unbinds external field storage first and removes registry entries.
When Python initialization fails, generated SV mirrors and Python-root
companions attempt storage closure and Python unbinding independently. A
returning cleanup error is added to the original initialization exception as
a note; it must not prevent the subsequent unbind attempt or replace that
exception. Native cleanup remains subject to the configured exception policy:
the default fatal policy can terminate simulation instead of returning to
Python. A user hook that fails before closing storage cannot be taken as proof
that retained field views were invalidated.

Native Python registry retirement removes the binding before invoking its
projected-storage cleanup hook. A missing hook is allowed; another error during
hook lookup or execution is reported under the configured exception policy,
without restoring the binding. Cleanup can reenter the registry without
invalidating the retiring entry. A failed user cleanup hook does not guarantee
that all retained field views have been invalidated: registry retirement and
successful storage cleanup are distinct guarantees. This lifecycle behavior
does not enable the pending Python-root construction paths above.

Python-origin pairs own the Python object and their internal SV companion.
An SV caller that writes generated `new C(...)` owns that actual SV object;
SVX owns only the borrowed companion binding. `RemoteRef` is non-owning. SVX
does not convert arbitrary pre-existing SV objects into mirrors: it has no
general SV object reflection or destructor hook, and every cross-language
instance must enter through a generated construction path.

Native Python callbacks maintain a receiver/method stack. Re-entering an active
pair is rejected with a callback-cycle diagnostic; Python-to-SV dispatch reports
it through `SVXRemoteError(code="dispatch_failed")`. No public call-ID protocol
or separate recursion exception class is exposed. Normal return and exception
unwinding remove callback frames; shutdown clears remaining bindings. Stopping
a process does not by itself close every independently owned mirror object.

### Alternating Lineage Generation

**Implementation status (current branch).** Manifest parsing validates complete
flat lineage and computes the minimal projection plan. The separate renderers
emit ordered SV `AMirror`/`BProxy`/`CMirror` helper packages. Each mirror helper owns a distinct
mirror package to avoid name collisions; public proxies use the prescribed
Python-module-derived package. Separate-package fragments require an acyclic
package declaration order and compilation-unit include anchors. Two SV portions
in one user package, or two required Python proxies in one shared package at
incompatible source anchors, can form a cycle. The parser accepts these logical
lineages, but the separate renderers reject such layouts before writing artifacts.
The public integrated output mode instead uses the parsed source-copy assembler
for inline/deferred integration, including a same-package SV-root A/C control,
while preserving public namespaces.
It also integrates declarations from physical includes: parser-selected headers
are copied recursively, preserving header guards, macro state, comments and
source-location directives. Focused SV-root and Python-root runtime controls
cover included class/package anchors, both construction origins, fields,
dispatch and paired close. The SV-root control also checks unchanged `__FILE__`
and `__LINE__` values. Proxy base-name macros now have focused source-copy
checks for object-like, nested and function-like expansions, including unchanged
definitions and unrelated uses. An internal Python-root runtime control uses
function-like base macros at both boundaries and exercises construction from
both languages, fields, static/virtual dispatch and paired close. Whole-class
macro anchors and the complete public source-only workflow remain unqualified.
The internal source-copy entry also selects construction/helper plans by each
logical root, rather than requiring the caller to choose one root language for
the entire manifest. A mixed-root control places both inheritance families in
one SV package and qualifies compilation, public proxy type resolution and no
user-base allocation during registration. The internal Python artifact assembler
now groups both logical root families into shared modules with one deferred
lookup/finalization entry and deterministic output. Independent processes check
both source-first and generated-module-first imports, correct MRO and stable
class identities.
The internal assembler also retains independently requested targets beside
alternating chains. Standalone SV helper packages and Python proxy/factory
members reuse the public renderer; shared public packages are merged rather
than redeclared, with one common record set and one owner per external endpoint.
Shared Python companion modules defer independent source-class imports as well
as alternating classes, avoiding eager circular imports. A combined control
constructs an independent Python root through its typed SV implementation factory
and an independent SV mirror through its matching constructor protocol, checks
calls, projected-field writes and close, alongside both alternating families.
When an original source-package member references an independently requested
Python proxy, the internal assembler places its auxiliary class before the
earliest consuming member and rewrites owning-package references to that local
class. The public package still exposes the original class name through a type
alias and retains its typed implementation factory. Auxiliary names avoid source
declarations; the original source file is not modified. A runtime control places
the implementation subclass inside the original SV package and checks factory
construction, its override calling the Python base implementation, and close.
Later source packages can reference that same proxy before its merged public
package is emitted: the assembler resolves such references to the existing
owning-package class, without generating another proxy. References whose public
alias is already available are preserved, including their macro invocations.
The runtime control also constructs an implementation declared in a later source
package through the public typed factory. References preceding their concrete
owning package are rejected rather than emitted unresolved. These controls do
not qualify arbitrary declaration forms. The explicit public CLI integrated
output now reuses this assembler and the existing artifact/inventory/check/input
protection pipeline. A combined control consumes its output in place of the
original units and exercises both roots, independent targets, fields, handles,
factories, callbacks and cleanup; a multi-package variant also checks an early
endpoint consumer. Full arbitrary-source/build integration remains unqualified.

The combined runtime control additionally exercises both
families in one simulation: Python/SV-origin construction, base-handle virtual
dispatch, static function/task bridges, projected-field updates, local-field
retention and paired close. It distinguishes closed receiver objects from live
session-scoped endpoints, checks empty construction contexts, then verifies
shutdown clears the remaining endpoints. The public integrated CLI control
consumes the same path, but does not qualify arbitrary source declarations.
The separate public renderers retain their existing restrictions.
Restricted Python virtual-interface views are assembled from the complete
manifest independently of root family, including handles declared only in a
Python-root lineage. Both internal artifact assemblers preserve the views and
their operation contracts. The combined control now also exercises opaque class
and restricted VIF handles in both root families' fields and method arguments/
returns. In the Python-root chain, Child declares these members, Derived and
Grandchild inherit them, and both construction origins exercise their access
and calls. Python preserves the opaque reference and VIF operations act on the
original interface instance. Closing the receiver invalidates inherited field
storage while session endpoints remain until shutdown. These checks also pass
with an earlier endpoint owner package and an existing forward class declaration.
Other endpoint shapes still require qualification; availability of the explicit
integrated CLI is not proof of arbitrary endpoint support.
A separate source-package endpoint control now places the sole typed class/VIF
adapters beside the concrete source class and exports only typedef aliases in
the normal endpoint package. Encoding through either alias shares object IDs;
decoding preserves the concrete handle and clearing the session invalidates
references and empties endpoint storage. The internal source parser now schedules
single-owner endpoint bodies after concrete class/static typedef declarations,
or at the first consumer package header for globally available types. It exports
one public alias package and qualifies generated calls to the allocated owner
type. Unit checks cover name conflicts, typedef ordering and full generated
syntax. A multi-file control places the concrete class in an earlier package,
an endpoint consumer module next, and the mixed inheritance package last.
Parser-selected public endpoint references in the generated source copy resolve
directly to their already-defined owner, avoiding dependence on a later alias
package. Plain and type-macro references preserve comments, literals and macro
definitions. Actual mixed calls and cleanup pass in both single-package and
this multi-package control. An existing `typedef class` declaration also makes
a concrete handle type available for endpoint placement before its complete
class definition. The combined runtime control qualifies that ordering; a later
definition without an earlier declaration is still rejected. The generator does
not invent forward declarations to repair otherwise invalid user type uses.
This does not qualify arbitrary forward endpoint
dependencies, macro-generated type anchors or every multi-package endpoint shape.
The same runtime control also verifies a projected proxy handle used as a source
member, parameter and return value, and an explicit proxy static call inside the
source package. Those references resolve to local helpers in the integrated copy
because the public alias packages are declared after their source package.
When a proxy handle is referenced before its helper definition, the integrated
package adds a conditional forward class typedef at its header. The control
checks a source helper class declared before A and its proxy, storing and
returning the same handle. Packages without early references do not receive
extra forward declarations. This does not reorder source constructors or claim
support for arbitrary forward inheritance or whole-class macro declarations.
Source locations are also restored after helper insertion for plain single-text
inputs, not only included or ordered multi-file inputs. Otherwise `__LINE__` in
user code would observe the inserted helper lines. Named source-unit inputs
retain their supplied logical filenames; an unnamed text input uses the parser's
logical filename rather than inferring a caller's filesystem path.
Ordered named source-unit inputs are first preprocessed as separate physical
buffers in one shared compilation unit. Relative includes resolve from each
source's supplied filesystem directory, not from the directory of an anonymous
concatenated buffer. This permits two source directories to contain different
headers with the same name without adding every source directory to a shared
include search list. Selected headers are then expanded into the integrated
copy with source-location mappings; macro state still follows source order.
Broader source/build integration remains required; splitting user packages is
not the final solution. The separate renderers retain their package preflight,
while the explicit integrated CLI handles the qualified same-package source
controls without requiring those splits.
BProxy and a downstream CMirror
reuse the AMirror object ID; CMirror delegates inherited BProxy operations to
its base gateway. Generated Python mirrors bind projected B fields before D
initialization and register only direct projection subclasses, so
`class D(CMirror, B)` does not replace B as the constructor target for an
ordinary A instance. The remote integration suite qualifies both Python-created
D and directly SV-created C for `A -> B -> C -> D`, including B field storage,
Python-to-C calls, and C-to-B virtual dispatch.

A complete lineage starting at a Python class is accepted by the parser and
handled in the qualified integrated CLI control. Separate SV helper rendering
still rejects unsupported alternating lineages. An SV ancestor is not a
requirement of the design. These Python-root controls are distinct from the
separate-package SV-root alternating regression. The public
Python-owned root factory selects a concrete implementation through its base
contract without claiming full descendant lineage generation.

The source-managed frontend is intended to scan declared Python mirrors/classes
and marked SV proxy/classes, then resolve the complete logical lineage before
output. Complete source-only discovery without pre-generated import bootstrap
is not yet qualified. Given a validated manifest for
`A(SV) -> B(Python) -> C(SV) -> D(Python)`, it emits the A-paired SV AMirror,
emits BProxy only because C needs it, and emits DProxy only because D is
followed by an SV projection in a target lineage. It also emits the generated
mirror metadata needed by those targets. It never emits A, B, C, or D merely
because they occur in another class's lineage. Planning checks logical lineage
and preflight checks separate-package ordering. These checks do not certify
every generated member/type or source-managed integration scenario. The remote
alternating regression covers the stated separate-package A/B/C/D scenario.

## Explicit Field Randomization And Sampling

SvTypes operations remain explicit Python operations. A bound owner's
`randomize()` or `randomize_with()` evaluates its SvTypes constraints against
a detached value snapshot and publishes successful results through the existing
field-storage adapter. A failed solve leaves the SV-resident values unchanged.
The trial snapshot does not rerun user constructors or allocate another SV
companion. Local and projected fields retain their individual randomization
modes.
Successful projected-field solves retain the owner's `randc` cycle history;
pausing a field preserves that history, and an unsatisfiable solve does not
consume the next value.
Randomization callbacks run on the original bound Python receiver, not its
trial copy. `pre_randomize()` runs before the snapshot; `post_randomize()` runs
only after successful publication. Hooks can access current fields and invoke
ordinary supported foreign methods. Layered hooks retain the current active
flag and priority. Explicit hook writes are user side effects and are not rolled
back when a later solve is unsatisfiable.

Coverage sampling reads the owner's current values through the same adapter;
it does not sample a stale field cache. Automatic value-domain coverage of
nested dynamic or associative containers samples leaf values, not keys or
subcontainers. SVX does not implicitly randomize or sample on method calls or
field assignments.
Fixed-array dimensions retain distinct indexed coverage points. If a selected
fixed or `cov_slots` slot contains a dynamic/associative child, that point samples
the child's leaf values from the current storage view; empty children and missing
outer slots do not produce samples.

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
5. Qualify with Python and native/SV regressions for A/B/C/D chains, inherited and
   direct fields, whole/container-path updates, construction rollback, virtual
   `super`, recursion rejection, and lifecycle interruption.
