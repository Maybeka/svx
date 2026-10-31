# Cross-Language Inheritance

This is the current semantic contract for target selection, projections,
construction, state residency and dispatch. It contains no historical staging
experiments or proposed public APIs. Signatures and accepted manifest fields
are owned by the [API reference](SVX_API_REFERENCE.md); concrete build/refresh
commands belong to [Generation Workflow](SVX_GENERATION_WORKFLOW.md).

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

## Manifest Shape

The top-level classes array is the exclusive list of requested targets.
base_lineage contains expanded ancestor objects, without the target itself or
nested base_lineage keys. Source metadata records each ancestor's own members,
constructor and static identity. Validation reconstructs the same validated
linear lineage; ancestry context alone never selects additional output classes.

Use [the manifest inventory](SVX_API_REFERENCE.md#manifest-field-inventory) for
the exact schema, accepted keys, direction and specialization rules. SvTypes is
the sole value and encoding contract. Source discovery checks declared SV facts
with supplied semantic source context; it does not infer arbitrary projects.

## Public Generated Type Names
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
Python `super().method(...)` uses that gateway. Thus both Python-initiated calls and
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

## Source-Managed Mirrors

The supported source declaration is an empty named Mirror binding:

```python
import svx

@svx.sv_mirror("sv://drivers/A")
class AMirror(svx.SVMirror):
    pass
```

It is a declaration and actual Python base, not a foreign allocation or an extra
target. Loading the matching generated mirror installs its executable surface
while preserving already defined subclasses and ordinary super() calls.
Construction before that implementation is loaded fails. The declaration alone
does not provide a complete static type-checking surface for all foreign members;
use the generated types for their concrete interface. There is no public
`mirror_method`, `parameter` or `_svx_call_base` API.

SV source can mark a Python-to-SV edge using `SVX_PY_PROXY`. Discovery uses a temporary
member scaffold for semantic checks; integrated generation supplies the real
projection. The scaffold is not a runtime class or an additional logical ancestor.
Choose [a complete example](../examples/cross_language_inheritance/README.md)
rather than inventing transport helpers or copying an old construction sketch.

## Constructor Routing

Constructible declarations record an initiator and ordered SvTypes arguments;
origin metadata is not an exclusive permission to construct from one language.
The selected generated entry determines ownership. Source-integrated generation
supports independent ancestor constructor arguments. Each Python initializer
executes once and suspends at its generated SV mirror's `super().__init__` boundary.
Evaluated arguments feed the corresponding SV `super.new(...)` call. After the
required SV portion and its field initialization complete, the bound Python
initializer resumes. Distinct portions may use different scalar, string or handle
prototypes; initializers are not replayed to recover argument values.

Continuation and per-owner constructor records are private runtime machinery,
implemented with synchronous internal continuations, not async user constructors.
Each Python portion runs at its assigned ancestor stage; it need not wait until
every later SV descendant constructor has returned. Constructor capture context
and object identity are retained across those stages.

There is no public post-bind hook API. Generated entries allocate one paired
identity, establish the required owner/field binding, then run the corresponding
Python initializer. Failure unwinds suspended portions and retires partial paired
bindings and constructor caches. A later Python initializer failing after its
factory returned also closes a newly created pair; reinitializing an already-bound
receiver does not allocate a second SV object or silently transfer ownership.
Callbacks attempted before their relevant binding completes fail, rather than
calling an arbitrary base or manufacturing another companion.

The source Python root retains its initializer and normal super() behavior.
Generated owner initialization runs once before projected field access and does
not reset earlier storage bindings. A plain Python-root source instance remains
local. Constructor metadata does not provide reflection over arbitrary handwritten
SV new expressions: cross-language construction must use the generated path.

## One Receiver And One Field Entity

Class portions are inheritance portions, not separately allocated companion
objects. An alternating target has one most-derived Python receiver and one SV
dynamic object under a shared simulation-scoped identity. Calls, inherited state
and explicit base gateways refer to those same physical objects.

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

### Initialization And Access
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
array elements do not replace declared defaults. The dependency contract is recorded in the release document.

SvTypes remains the sole public type, normalization and encoding contract.
Generated typed SV member endpoints implement projected access; this does not
use reflective VPI class-member lookup or expose a second user message protocol.

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

## Projected Storage And Lifetime

Fields keep their actual SvTypes types and .value/container interfaces. SVX uses
the public SvTypes owner-level external-storage binding; it does not replace
descriptors with a second field DSL or cache mutable Python copies of SV state.
Only selected resident fields are bound. Unselected fields stay Python-local.

SVXFieldStorage maps an opaque owner key to the object/member identity and sends
typed read/write/path/operation requests through generated endpoints. SvTypes
owns normalization, codec bytes, nested owner/path propagation and live container
views. Its protocol definitions belong to SvTypes, not a copied SVX specification.
Whole-value assignment is a whole-field transfer. Child/key/index mutations use
addressed operations; slices are composed from element operations, not hidden
whole-container writeback. Queues/dynamic arrays and associative keys support the
applicable set/insert/append/delete/pop/resize operations. Invalid paths, indices,
keys and lengths fail without silently updating another member or sibling.

Projected values use public `sv_declaration(..., include_initializer=True)` for SV
declarations. The current manifest field shape is name/type with optional handle
metadata; a canonical layout identity alone does not reconstruct source defaults
or every declaration policy. Concrete codec declarations and the selected
SvTypes capability set remain essential. Unknown field_descriptor keys are not
an alternative schema.

Close, rollback and shutdown close selected external storage before retiring
paired bindings. Retained child views remain invalid: removing their backend and
falling back to old local values would be incorrect. Unprojected local fields
remain usable. A constructorless registered-ID view can wrap an existing SVX
dispatchable endpoint, not an arbitrary raw class handle. Failed attachment
retires only the new Python binding when the endpoint is caller-owned.

Malformed codec bytes and an SV fatal are not recoverable transactions. A concrete
unpacker may already have changed values before detecting trailing data. Container
slice operations are not atomic batches either. Do not infer general rollback from
ordinary path/type validation. Explicit lifecycle and cancellation API behavior
is defined in [the API reference](SVX_API_REFERENCE.md#stable-python-api).

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

## Experimental Published-Object Handoff

The experimental publish_object / SVX_GET_OBJECT capability lets SV retrieve an
explicitly published live Python-created mirror using an expected SV base type.
It is not arbitrary access to all Python objects or an ownership transfer. The
exact operations and lifetime are defined once in the
[experimental API](SVX_API_REFERENCE.md#experimental-python-api); use the
[Python-led driver example](../examples/cross_language_inheritance/README.md).

## Executable Scope

The logical ancestry is one linear chain, including repeated language crossings.
Multiple Python bases may reconcile generated views of that same validated
lineage; they do not authorize unrelated logical multiple inheritance. Unrelated
base chains, mixins in a generated lineage, method overloads, field hiding and
undeclared foreign-member access are outside the supported contract. Fields are
identified by their declaring class and declaration, not just a guessed name.

Integrated generation supports the documented mixed SV-root and Python-root
linear controls and ordered source inputs, including same-package source copies.
Standalone/staged modes retain their own declaration-order constraints. Concrete
parameterized SV types must have resolved arguments; unresolved templates and
arbitrary inheritance graphs are not promised by accepted ancestor metadata.
Protected members use legal derived gateways; local members are not exposed.

Ancestors need not share the target class's package. For an unqualified base
introduced by a package import, discovery uses semantic name lookup, including
explicit imports, wildcard imports and package re-exports. Named class typedefs
retain their own declared identities. Supply the complete source dependency
context; an unresolved or ambiguous import is not resolved by guessing a package.

Closed specializations keep one canonical class identity across all targets and
ancestor entries. Ordered type arguments carry concrete SvTypes bindings; value
arguments carry an SV type and normalized literal. Source expressions can be
evaluated by discovery, but open parameters and unevaluated expressions cannot
remain in the manifest. An unnamed closed ancestor can remain context without
requesting another generated target. Generating from JSON alone cannot verify
the actual source parameter list; compile with that source as well.

A generated specialization keeps the source simple name. Public naming
collisions between specializations reject rather than acquiring hashes. Static
members keep their declaring specialization's identity and distinct dispatcher.
Static gateway classes are virtual and not instantiated; required forwarding
constructors only make the derived declaration legal. Accessing a protected
static member does not construct a source object. Source-discovery selection
details belong to [the generation workflow](SVX_GENERATION_WORKFLOW.md#selected-source-declarations).

Function legality is enforced at SVX's recognized task/wait boundary. SVX does
not require static analysis of arbitrary Python call graphs. Static/nonvirtual
members retain their own language dispatch rules; virtual members use the
declared dynamic chain. Ref aliases are not transported. Native class handles
and restricted interface views follow the separate
[handle adapter contract](CROSS_LANGUAGE_HANDLE_ADAPTERS.md).

Callback-cycle detection is per actual SV process and receiver/method path.
Independent processes may call the same receiver/method and finish in non-LIFO
order. Nested callbacks inherit their causal context, not whichever callback ran
last on the host thread. A repeated active pair on one process is rejected;
this is not a general cross-process wait-for-graph detector. Evaluator-state
isolation is specified in [CPython state management](architecture/gil_management.md).

Applications use the generated public types and factories, never private bind,
dispatcher, constructor-record or object-ID APIs. General SV reflection, arbitrary
early constructor callbacks, custom metaclass construction and every possible
source/container/policy combination are not implied by the qualified examples.
