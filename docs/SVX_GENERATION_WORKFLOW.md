# Generation And Incremental Builds

This is the operational authority for discovery, generation, freshness and
generated-file ownership. Command names and manifest keys are catalogued in the
[API reference](SVX_API_REFERENCE.md); importing existing project inputs is
specified in [Build Inputs](SVX_BUILD_INPUTS.md). Keep project-specific command
arguments in the project's build script, not in several copied check recipes.

## Choose The Operation

| Change | Required refresh | SV/native rebuild |
|---|---|---|
| Tracked Python implementation only | Discovery, then generation; matching bridges keep their timestamps | No |
| Python method direction, type, result or timing | Discovery and affected adapters | Affected SV adapters |
| SvTypes schema or projected field declaration | Types and affected adapters | Affected generated SV |
| SV method body | Refresh recorded inputs and integrated copies, if used | Changed original or integrated SV |
| SV interface, modport, method signature or closed specialization | Discovery and affected views/adapters | Affected SV |
| Declared signal paths only | Import and validate on the next simulation startup | Only if design sources changed |
| Native runtime or embedded Python ABI | Matching native build and artifacts | Native and affected SV |

Do not recompile an unchanged bridge merely because source evidence changed.
Byte-identical manifests, bridges and inventories preserve their timestamps.
Use a fresh simulation process to load changed Python; shutdown is terminal,
not a reload mechanism. Initial imports through svx_load compile current source;
already imported modules retain ordinary Python caching.

## One Project Recipe

During development, rerun the original discovery command, then its generation
command. Both commands validate sources and ownership before publishing output;
an interactive refresh does not require immediately repeating them as checks.

For a build, CI or release gate without modifying existing artifacts, run the
same commands with --check, in order:

```sh
python -m svx inheritance-manifest \
  --python-module checks.base_monitor \
  --sv-declarations sv-inheritance-declarations.json \
  --out inheritance.json --check &&
python -m svx inheritance-gen \
  --manifest inheritance.json \
  --python-out generated/python --sv-out generated/mirrors.sv \
  --artifact-manifest generated/svx-artifacts.json --check
```

An artifact check compares against its supplied manifest; it cannot substitute
for checking discovery. If discovery is stale, refresh it before generation.
Handwritten manifests have no discovery evidence: maintain their contracts and
external build dependencies explicitly. Do not add invented provenance records.

These commands are generic templates. Prefer the example's generate.py or an
equivalent project command that already owns the complete input arguments.

## Direct SV Export

Before selecting an unfamiliar project's APIs, inspect its existing inputs:

```sh
svx inspect -f project.f --sv-elaboration packages
svx inspect -f project.f --kind class type --name 'drivers_pkg::*' --json
```

inspect is read-only and does not produce a manifest, generated code or cache.
It shares the build-input importer and demand-driven library selection with
export. Its JSON contains declarations with kind, symbol, lexical scope,
physical source location, compilation-unit identity and export_status/reason;
it also lists parsed physical dependencies. Package entries list imported
package names. --kind and --name filter the displayed declarations, not the
source inputs needed for preprocessing and library resolution.

The inventory includes package declarations, classes, typedefs, parameter/
localparam statements and non-class functions/tasks. Subroutine-local types and
class methods are not separate export targets. Package-owned declarations
marked selectable have an eligible scope; this is not a promise that every
concrete type or signature can be represented. Actual export performs semantic
qualification. A typedef is reported as a type declaration even if subsequent
semantic resolution discovers that it aliases a class.

Compilation-unit entries also include compilation_unit_index for indexed
selection. Standalone $unit value typedefs and unit-level constants are
selectable as described below. Compilation-unit classes, including nested ones,
are selectable too and use $unit::Class or $unit::Outer::Inner in the report. Module/interface/program
and generate owners retain separate lexical scope components. Module/interface
classes and generate-owned classes are marked requires-instance: select a real elaborated owner, not just
the source definition name. Instance-owned type and root constant snapshots are
also requires-instance; runtime use in class signatures remains unfinished.
Actual signatures and visibility still
require qualification; see [Instance-Owned Classes](#instance-owned-classes).
Finding a declaration does not make every signature exportable. Independently
compiled inputs keep distinct compilation_unit keys, including same-named $unit
classes. Included declarations retain the owning compilation unit and their
physical source location, unaffected by logical `line remapping.

This is a preprocessed declaration inventory, not an elaborated instance tree.
Both generate branches may appear; loop bodies appear once, not once per lane.
Anonymous generate blocks use a source-position marker, never a guessed genblk
instance name. Conditional-preprocessor branches follow the original macros.
No DUT instance elaboration is performed. With --sv-elaboration packages,
hierarchy-only library requests are skipped as described below; explicit source
files and package/VIF lookup dependencies remain inputs.

For an existing SV package class or value typedef, select the target and reuse the original build
inputs. No Python subclass, Mirror stub or declaration JSON is required:

```sh
svx export --class drivers_pkg::Driver -f design.f --out generated
svx export --package drivers_pkg -f design.f --out generated
svx export --constant config_pkg::DEPTH -f design.f --out generated-constants
svx export --callable tools_pkg::check tools_pkg::wait_ready -f design.f --out generated-calls
svx export --type types_pkg::State types_pkg::Packet -f design.f --out generated
```

The output contains inheritance.json and its discovery record, python/,
mirrors.sv and artifacts.json. Add python/ to the simulation import path and
compile mirrors.sv after the original classes and runtime packages. Before calling
generated constructors/methods, explicitly register their factories and dispatchers:

```systemverilog
svx_init();
svx_exports_pkg::initialize();
svx_load("verification.entry");
svx_start("verification.run");
```

The generated initialize function is synchronous and idempotent within the
simulation. It registers generated factories/dispatchers, not application
objects. It also provides explicit references to the generated packages when
the project analyzes files in separate compiler invocations; relying only on
package-variable initializers can leave their registries empty in that flow.
The artifact's systemverilog_startup names the generated entry. It is build/startup
guidance, not a command executed by Python or by artifact loading.
Pure type/constant exports have no runtime registrations and need no such entry.

The command
prints exact Python imports, for example `from svx_mirror.drivers_pkg import Driver`.
It composes the existing discovery and generation operations; it does not define
a separate manifest or runtime. Use a dedicated output directory. `export --check`
checks both operations without modifying their outputs. Publication/ownership
rules below apply to each operation; the entire command is not a multi-file
transaction. A failure does not mean that every output was rolled back.

Selection options repeat or accept multiple values, and support quoted shell-style
patterns. An unqualified class name is accepted only when it is unambiguous;
otherwise the diagnostic lists qualified choices. Package
selection exports its owned classes, value typedefs, compile-time constants and functions/tasks,
not imported or re-exported declarations.
Imports and ancestors still participate in semantic resolution and lineage;
they are not implicitly extra targets. `--recursive-packages` explicitly selects
owned declarations in transitively imported packages. `--exclude-class 'pkg::Internal*'`
removes unwanted targets. A selector matching nothing reports an error.

By default, discovery exposes accessible methods and fields. For a narrow API
or a large library, add `--member status --member advance`, or
`--member 'drivers_pkg::Driver.*'`. A bare pattern matches member names throughout
the selected lineage; a qualified pattern matches its declaring class and name.
`--exclude-member` takes precedence. Constructors are still discovered from SV
signatures and are unaffected by member filters. Unknown included members reject
instead of silently producing an empty API. Local members are not exposed;
protected members use the existing gateways. Advanced explicit declarations
remain authoritative rather than being rewritten by these filters.

For package-based APIs, add --sv-elaboration packages to avoid design-instance
analysis and RTL library loading driven only by module instantiations:

```sh
svx export --package drivers_pkg -f project.f --sv-elaboration packages --out generated
```

The default all retains the existing behavior. The explicit packages policy
preserves every supplied source, source order, macro and include path. All
explicit sources are still preprocessed and syntax-checked; it is not a textual
deletion of DUT code or a way to ignore syntax errors. Package imports/scoped
type references and restricted-VIF dependencies still perform demand-driven
library lookup in the original directory/extension order, including imports
declared inside modules. Only hierarchy-instantiation-driven library requests
are omitted. Thus a large RTL tree reached solely through -y need not be loaded,
but RTL files explicitly listed in project.f are still parsed. No directory is
globbed and no source definition is rewritten or relocated.

Semantic probes use an internal empty analysis top instead of implicit design
tops; that top is not generated, compiled or added to the runtime. The frontend
is already lazy, so changing top selection alone need not improve performance.
Savings depend on the avoided library graph, not just signal or instance count.
Use all when analysis needs design-instance-dependent types or bindings.

Discovery evidence and generation-input records preserve this policy.
--check replays it: edits to explicit sources and selected package/VIF library
dependencies invalidate evidence; an earlier matching library candidate also
invalidates selection. Unselected DUT-only library files are not dependencies
of a packages-mode export. This is not permission to omit those files from the
original simulation build. The same option is available on inheritance-manifest
and inheritance-gen; use the same mode throughout a manual pipeline. svx export
forwards it to both steps automatically. This is selective analysis, not a
persistent parse cache or completed incremental parsing.

For repeated direct SV exports, --incremental enables opt-in result-level reuse:

```sh
svx export --package drivers_pkg -f project.f --incremental --out generated
svx export --package drivers_pkg -f project.f --incremental --out generated --check
```

SVX writes a local generated/.svx-export-cache.json after a successful full
export. It records the actual source images, parser-observed include lookups,
library lookup results (including misses), request/framework fingerprint and
all generated-output digests. A warm operation independently checks source
contents and replays native header selection plus the existing ordered library
lookup, then checks again before returning. An earlier include/library candidate,
newly satisfiable library reference, changed source/macro/build input, framework
or generated file prevents reuse. Touching an unchanged file does not require a
refresh. Both separate and direct integrated layouts are supported.

A verified hit skips SV parsing, discovery and generation; it does not import or
execute cached Python code. Cache JSON is local optimization data, not a new
manifest contract or a file to edit/publish. An absent, incompatible or damaged
entry falls back to the ordinary full operation. Unknown files at the reserved
cache path are not overwritten. Executable Python declaration/explicit
declaration inputs still run the full audited pipeline rather than assuming
their import-time behavior is deterministic. Runtime-only Python test changes
do not require regeneration unless those files are explicit generation inputs.

Omit --incremental to bypass reuse. --incremental --refresh-cache forces the
ordinary operation and refreshes a valid local entry on success. --check always
remains read-only, including the cache itself; a cold check does not create one.
The CLI reports whether reuse occurred and why it selected the full path.
This is whole-export no-op reuse: a changed dependency currently reruns the full
frontend. It is not per-compilation-unit AST reuse or changed-unit-only parsing;
those finer-grained incremental mechanisms remain unfinished.

The current direct selectors cover package classes, concrete supported
specializations, enums, packed structs, value typedefs and package functions/tasks.
Enum/struct dependencies in selected signatures and fields are generated automatically. Scalar and
container aliases use public SvTypes declarations. Standalone value export does
not require any class target, native runtime or SVX simulation startup: generated
Python modules import SvTypes only. Generation itself needs the source frontend.

Values retain the public name svx_mirror.<package>.<type>. Private
_svx_value_types modules separate declarations from mirror contract registration
to avoid import cycles; they re-export the same public class objects, with the
public __module__, not a second wrapper type. SV transport helpers use unique
private names while preserving the exact public SvTypes schema and encoding.
This permits same-named native types in different packages without renaming the
public types. Packed member writes decode into a temporary before assigning the
addressed leaf; they do not pass an illegal packed member as a ref actual or
read/modify/write its whole parent.

--exclude-type removes optional value targets, but an excluded type needed by a
selected signature or value declaration rejects with the dependency location.
Current SvTypes boundaries still apply: unpacked structs, unions, X/Z enum
literals/four-state enums, unsupported container bounds/range orientations, and
enum names colliding with SvTypes interfaces are not silently approximated.
Package export also selects owned parameter/localparam values. --constant
selects them independently, with qualified/unique short names or patterns;
--exclude-constant removes optional snapshots. Imported parameters may be used
to evaluate expressions without becoming export targets. --recursive-packages
explicitly expands ownership selection. Constants share the public
svx_mirror.<package> namespace with the exported types/classes.

These are compile-time snapshots evaluated by the SV frontend, not live SV
variables. They are decoded with the public SvTypes codec into ordinary values
(int/string/real, enum values, LogicValue, SvStruct or supported containers).
Changing a mutable Python snapshot does not change the native declaration.
Zero/empty values, signedness, wide integers and X/Z in Logic are preserved;
X/Z cannot silently pass through a two-state integer codec. Required named value
types are generated automatically. Pure constants, like pure types, need only
SvTypes at import time and no running simulator. Runtime const variables and
class/module instance parameters are not package compile-time snapshots.
Constant manifests use schema2.2.0 with unchanged generator ABI2: optional
constants entries contain symbol, public SvTypes identity/schema/encoding descriptor
and canonical hex data encoded exclusively by that codec. The public encoding
descriptor is verified both while generating and when importing a snapshot;
an incompatible dependency encoding requires regeneration, not reinterpretation
of old bytes. --check also validates their input
configuration and generated output.

--callable selects package functions/tasks directly, and --exclude-callable
excludes optional functions/tasks from direct or package selection. Python imports
the original function name from svx_mirror.<package>; there is no user-visible
carrier class or object-construction step. Importing a package does not request
export of the functions it imports. The original SV declaration, static local
variables, package state and scheduling remain native.
When a public function name collides with a generated support import or builtin,
only generated internal references receive private aliases; the public function
name, formal names, contract strings and source formatting are retained.

Every formal parameter remains in its source order. Pass ordinary values for
inputs, svx.Output() for outputs and svx.Inout(value) for inouts. Functions return
their ordinary result; tasks return None and execute their delay/wait in SV.
The existing function-callback guard rejects task/wait operations; no Python
async scheduler is introduced. All formals in the generated Python signature
must be supplied. ref/const-ref remain unsupported. Names that cannot form valid
Python syntax reject before generation rather than emitting broken wrappers.

Required values and opaque class/restricted-VIF handles use the same SvTypes
bindings as class methods. Referencing a class only as a handle does not export
that class. Class handle results retain their public SvTypes RemoteRefValue
contract (target type and object number); selecting that class adds its mirror
API, not an implicit replacement of every handle result with a Python instance.
Restricted VIF results use the existing generated view adapter.
Compile the generated bridge after the original packages and runtime,
and initialize/start SVX as in the examples; unlike pure values, invoking a
function/task requires a live SV endpoint. Runtime exceptions/cancellation follow
the existing call boundary, not a separate package-function protocol.

Callable manifests use schema2.3.0 and unchanged generator ABI2. Optional callables
entries pair a qualified symbol with an existing method-shaped signature. Its
static flag means receiver-free dispatch, not rewriting the source function's
variable lifetime. The private svpkg://<package>#<name> route uses the existing
static registry/record transport. No synthetic class enters root.classes or
the public Python API.

Package-owned nested classes are selected by their complete source name, for
example --class 'drivers_pkg::Outer::Inner'. Discovery walks class scopes,
resolves imported and lexically scoped bases through the semantic frontend, and
keeps lexical ownership separate from inheritance. Required ancestors remain
context rather than extra class targets. Package selection includes owned nested
classes and public class aliases too; local/protected typedef aliases are not
silently exposed outside their native owner.

Python publishes this type as svx_mirror.drivers_pkg.Outer.Inner. Import Outer
from svx_mirror.drivers_pkg and access its Inner attribute; Outer is not a Python
submodule. __name__ remains Inner and __module__/__qualname__ describe the public
package/scoped name. An unselected owner becomes a namespace holder, not another
native mirror target or allocated object. A selected owner is its real mirror
class. Private definition modules re-export the same type object; native helpers
still extend the original drivers_pkg::Outer::Inner. Scoped helper names use
component boundaries, not ambiguous underscore flattening or public-name hashes.
The [nested class example](../examples/sv_scoped/README.md) verifies both forms.

Public value typedefs inside these classes use the same lexical names. For
example, --type 'drivers_pkg::Outer::Packet' exports
svx_mirror.drivers_pkg.Outer.Packet without also selecting Outer as a native
class target. Enum/packed-struct dependencies are discovered automatically,
including when they occur in a selected class's arguments or fields. Package
selection includes public nested value typedefs; local/protected typedefs are
not standalone public targets. A method that requires an inaccessible named
enum/struct dependency fails discovery with that type's visibility and declared
use site rather than producing an external bridge that cannot name it.
A selected owner's mirror holds these same
SvTypes type objects, not duplicate definitions. Original native types remain
in their source scope. Named values retain their public module/qualname and
the public SvTypes identity can resolve them after import.

This currently qualifies package-owned nested classes and supported nested value
typedefs. Module/interface/program class instance bindings and alternating
source-managed lineages with automatic value/package-call records remain unfinished;
they are not native-language restrictions. No class is relocated to a synthetic
package to bypass its source ownership.
Existing explicit Python declaration frontends retain their own
SvTypes declarations; direct SV selectors derive their named values from SV.
Direct SV exports can use either separate bridges or the integrated source-copy
layout described below, including supported automatic value declarations,
nested classes/class aliases, constants and package functions/tasks.
Unsupported selected
members fail with a location/reason, including ref/const-ref and automatically
discovered static fields. Narrow selection is explicit user intent, not automatic
loss of unsupported endpoints. Native class handles do not automatically select
their target classes. See the runnable [direct export example](../examples/sv_export/README.md).

The same selectors are available on inheritance-manifest when discovery and
generation must be separate build steps. Package selection does not imply that
every possible SV type or other symbol is supported; unsupported selected types
report a reason before publishing the discovered manifest.

## Compilation-Unit Values

A value declaration does not have to live in an SV package. For compilation-unit
typedefs, including public types nested in nonparameterized unit classes, and
unit-level parameter/localparam snapshots:

```sh
svx inspect --sv-source examples/sv_scoped/unit_values.sv --kind type constant --json
svx export --type '$unit::*' --constant '$unit::*' \
  --sv-source examples/sv_scoped/unit_values.sv --out generated
PYTHONPATH=generated/python python examples/sv_scoped/unit_values.py
```

Supported values use the same public SvTypes declarations/codecs as package
exports. Native symbols stay $unit::Mode or $unit::Holder::Payload; no SV package
or duplicate native type is invented. Generated Python imports use
svx_mirror_unit.unit_<index>, for example:

```python
from svx_mirror_unit.unit_0 import Mode, Packet, INITIAL, Holder
assert Mode.ACTIVE == INITIAL.mode.value
payload = Holder.Payload()
```

The index is the preprocessed compilation-unit index reported by inspect's
compilation_unit_index, in original parser-unit order. Shared inputs have one
unit; independently parsed inputs retain separate indices. Added implicit
library units retain their own parse-unit identity. These are not hierarchy
paths or simulator object handles. Reordering/re-grouping compiler inputs may
change indices, so refresh using the same original configuration as the build.

An unambiguous bare selector such as --type Mode is accepted. If different units
define Mode, the diagnostic lists $unit[0]::Mode, $unit[1]::Mode, and so on.
Select one explicitly with --type '$unit[1]::Mode', or export all with the quoted
$unit::* pattern. Each unit gets a different Python module, even when native
declarations share a name. Real packages retain svx_mirror.<package>; a legal
SV package named __unit__ does not collide with compilation-unit values.

Unit value/constant entries use schema2.4.0 and add source_scope with
kind=compilation_unit and a nonnegative integer index. The native symbol remains
unindexed; the scope descriptor disambiguates it. These fields describe source
ownership, not another value wire format. Python values retain their exact
public SvTypes identity/schema/encoding descriptor. Alias declarations reuse the
underlying type object. A namespace such as Holder is not a generated class
constructor merely because Holder.Payload was exported.

Type/constant-only imports require SvTypes, not the SVX native runtime or a
simulation. They produce no registration startup entry. They can be bundled
with unrelated package runtime exports; unit snapshots are not incorrectly
imported into package call records. Root-level unit enums/packed structs and
containers of them can be used by classes in that same unit: their call records
are emitted in the original owner. A package or different independent unit
cannot reference those native types. Same-unit class-owned enum/struct runtime
signatures are supported. Named values from parameterized class specializations
still need specialization-aware placement; those unfinished
layouts reject explicitly rather than emitting fake package references.
Unit classes use the workflow below; class-parameter snapshots remain unfinished.
Existing SvTypes value-kind
limits still apply, including unsupported four-state enums/unpacked structs.

## Instance-Owned Values

Use the same --type and --constant selectors with concrete module, interface,
program or active generate owner paths. No declaration JSON or runtime startup
is required for these snapshots:

```sh
svx export --type 'tb_instance_values.*.Mode' 'tb_instance_values.*.Alias' \
  'tb_instance_values.*.Payload' 'tb_instance_values.*.Word' \
  'tb_instance_values.*.Packets' 'tb_instance_values.*.Modes' \
  'tb_instance_values.a.Holder::Tag' 'tb_instance_values.lanes[*].Index' \
  --constant 'tb_instance_values.*.W' 'tb_instance_values.*.DEFAULT_MODE' \
  'tb_instance_values.*.DEFAULT_PAYLOAD' 'tb_instance_values.lanes[*].ID' \
  -f examples/sv_scoped/instance_values.f --out .tmp/instance-values
```

Python publishes owner-local names in the existing instance namespace, for
example svx_mirror_instance.tb_instance_values.a.classes.Mode. --type selection
can include typedef aliases and public types nested inside classes; selecting
Holder::Tag creates a Holder namespace, not a Holder constructor. Primitive and
container aliases use standard SvTypes declarations. Enum/packed-struct nominal
names include the concrete owner, so equal-parameter instances never overwrite
each other's Python types. Typedef aliases preserve their underlying identity.
Constants are evaluated snapshots, not live hierarchical signal reads.

The manifest retains the original owner-local symbol and source_scope with
kind=instance, path and native container; discovery emits schema2.6.0. Scope
selectors, array-index encoding and ambiguity rules match instance class
selection. Package selection does not implicitly select instance values.
The hierarchy must be elaborated: --sv-elaboration packages cannot serve these
selectors. Inactive owners and unsupported concrete SvTypes schemas reject.

Selecting a class automatically collects same-owner value dependencies from its
fields, constructor and method signatures. No separate --type list is needed:

```sh
svx export --class 'tb_instance_runtime_values.*.Driver' \
  -f examples/sv_scoped/instance_runtime_values.f --out .tmp/instance-runtime-values
```

Compile the source replacements and startup unit listed in artifacts.json, not
the original file alongside its replacement. Module and interface adapters bind
native typedefs as type arguments; program adapters keep declarations in the
original lexical owner. Public codecs remain standard SvTypes codecs. The
[runtime example](../examples/sv_scoped/README.md#instance-owned-runtime-values)
checks live enum/struct fields, enum/struct/array/queue method transport,
constructor arguments, virtual callbacks, static calls and output/inout tasks.
Equal-parameter owners retain separate Python nominal identities.

Generate-owned nominal runtime combinations still need native qualification;
successful snapshot selection does not establish that runtime support.
Cross-owner native type dependencies, native handle adapters and
parameterized-class named values remain unfinished. See the
[snapshot example](../examples/sv_scoped/README.md#instance-owned-type-snapshots)
for standalone Python imports and native reference results.

## Compilation-Unit Classes

Classes declared directly in a compilation unit do not need a wrapper package
or handwritten manifest:

```sh
svx export --class Driver -f examples/sv_scoped/unit_classes.f \
  --sv-elaboration packages --out generated
```

The command resolves Driver's source package/unit ancestry, constructors,
methods and selected fields. A unique short name is enough; use the quoted
'$unit[1]::Driver' selector when independent units declare the same name.
'$unit::*' selects unit class declarations; unsupported owner/signature layouts
are reported, not silently dropped. Package selection continues to
select package-owned declarations only. The parsed unit index follows the
original independent/shared compilation grouping, not a new generated grouping.

Inherited static methods are registered under their declaring class identity,
including package and same-unit ancestors that are not export targets. Shared
ancestors are registered once per unit bridge; selecting two children does not
allocate or export additional ancestor constructor targets. Python calls the
inherited method through the selected child's ordinary mirror type.

Nested classes use the same workflow. An unambiguous lexical selector such as
Outer::Inner is accepted; '$unit[1]::Outer::Inner' disambiguates owners. Python
publishes the original class at svx_mirror_unit.unit_1.Outer.Inner, with
__name__=Inner and __qualname__=Outer.Inner. Selecting only Inner creates an
Outer namespace, not an exported or allocated Outer object. Selecting Outer too
attaches Inner to its real mirror class. OtherOuter.Inner, Outer_Inner and
case-distinct outer.Inner retain separate identities, including internal files.

Python imports the unchanged class name from svx_mirror_unit.unit_0. Native
symbols remain $unit::Driver. Because packages cannot access unit-local types,
export automatically selects source-copy integration for these targets, even
without --integrated. Replace the original inputs with the reported source
copies; do not compile both. Also compile generated/sv/exports.sv, last in the
artifact's systemverilog_compile_order. Prepare the SVX/SvTypes runtime packages
before those replacements as described in the build guide.

Instantiate one generated startup module in the top and initialize it before
loading Python:

```systemverilog
svx_exports exports();
initial begin
  svx_init();
  exports.initialize();
  svx_load("my_tests");
  svx_start("my_tests.run");
end
```

This module links each owner-local factory/static dispatcher explicitly; do not
rely on unused compilation-unit global initializers. It also initializes any
package exports in the same artifact. There is no extra polling/service loop,
source-class relocation or second object model. Shared inputs remain one unit;
independent inputs remain separate. --check and --incremental cover the startup
source as well as every replacement.

The [runnable example](../examples/sv_scoped/README.md#classes-without-a-package)
checks Python construction, inherited and local native fields, a timed
output/inout task, static calls and virtual dispatch through an original SV
base handle. The [nested unit example](../examples/sv_scoped/README.md#nested-compilation-unit-classes)
also passes same-owner root/class-owned enums, packed structs and enum arrays, preserves
X/Z during partial field writes, and verifies source typedef shadowing does not
change the selected native type. Nominal dependencies are automatic; use
--type UnitModes when the public container typedef alias itself is wanted.
Class-owned nominal types keep their complete native name, such as
$unit::Outer::Inner::State; inherited methods retain their original declaring
type even when a subclass declares its own State with identical literal names.
Use --type Outer::Inner::States for an explicitly wanted nested container alias.
Cross-unit/package access, owner-local handle adapters and alternating
unit-owned cross-language lineages still need additional placement support;
these implementation gaps report errors rather than manufacturing packages.

## Instance-Owned Classes

Export classes from real module/interface instances using the original inputs:

```sh
svx export --class 'tb_instance_classes.*.Driver' \
  -f examples/sv_scoped/instance_classes.f --out generated
svx export --class 'tb.lanes[1].agent.Driver' -f project.f --out generated
```

There is no prototype package, Mirror stub or handwritten declaration JSON.
A unique short name is accepted; ambiguity reports concrete instance paths.
Class namespaces still use ::, for example tb.agent.Outer::Inner. Numeric
hierarchy indices are literal and [*] selects array elements. Patterns and
--exclude-class use the same names; --member tb.agent.Driver.method can select
an exact declaring class/member. Imported package selection does not implicitly
add instance-owned targets.

The frontend reuses original top selections from -top/--top-module build
arguments. A concrete target resolves only its owner instead of walking
unrelated DUT subtrees; short names and hierarchy patterns require broader
instance discovery to establish matches and ambiguity. Raw original syntax is
shared within discovery, with before/after input validation kept independent.
--sv-elaboration packages remains the faster path for package/unit declarations,
but cannot resolve instance targets. Read-only inspect still lists lexical
definitions, not elaborated paths.

Each target keeps its native class and evaluated specialization. Python names
retain the original simple name under svx_mirror_instance.<owner>.classes; parent and
child owner namespaces may both expose classes. Source scope/identity details
are defined once in the [manifest contract](SVX_API_REFERENCE.md#manifest-field-inventory).
Bound adapters receive native source/ancestor types through type parameters,
without relocating or redeclaring user classes. Generated source replacements
and the same svx_exports.initialize startup are used as for unit exports.

The [complete example](../examples/sv_scoped/README.md#instance-owned-classes)
has source-only CLI/check/native qualification: same-parameter owners retain
separate live context, another owner has13bit instead of8bit fields, native
construction/inherited fields/static methods/2ns output-inout and original-SV-
handle Python callbacks pass. Interface nonstatic source-only export is also
qualified, including static functions/tasks and inherited protected static
members. Static interface gateways are inserted into the original interface's
source copy and initialized by the same startup, without allocating a source
object. Scalar owner-parameter guards keep each gateway in its matching
specialization; string, real and four-state scalar parameters are retained.
Owner type/structured parameters, library-only owner source replacement and
macro-generated endinterface anchors still need additional placement support.
Instance-owned named values/handles and alternating owner lineages remain
unfinished and diagnose rather than emitting a callable wrong contract.

## Generate-Owned Classes

Classes inside active generate blocks use the same export command and original
build inputs. For the complete [generate example](../examples/sv_scoped/README.md#generate-owned-classes):

```sh
svx export --class 'tb_generate_classes.*.lane[*].active.Driver' \
  -f examples/sv_scoped/generate_classes.f --out generated
```

The class remains in its original generate block. Local adapter classes, call
records and factories are inserted into source copies; no native class type is
passed out through a bound module's type parameter. Startup is still a single
svx_exports.initialize. The example verifies six real owners,8/9/13/14bit
fields, constructor/state independence, inherited statics, a1ns output/inout
task and original SV-handle virtual callbacks into Python.

Parent parameter guards are captured before each child generate construct.
Genvar guards are evaluated in their own lexical scope, so an inner localparam
with the same name does not change which original lane is selected. Both module
and interface containers and unnamed explicit begin/end blocks have native
qualification. Implicit genblk names come from actual elaboration; inspect
continues to show lexical anonymous markers, not invented runtime paths. A
unique short class name can discover the concrete path automatically. Inactive
branches are never export targets.

Keep the artifact's source replacements and compile order, and do not compile
originals a second time. Parameterized owner type/structured values, late
parameter guard placement, single-item generate constructs without begin/end,
macro anchors and library-only source replacement remain unfinished layouts.
These diagnose explicitly; they are not permanent restrictions on legal SV.

## Program-Owned Classes

Use the same original-input workflow:

```sh
svx export --class 'tb_program_classes.*.Driver' \
  -f examples/sv_scoped/program_classes.f --out generated
```

Original classes and complete adapters remain in the program; no module is
instantiated inside it and no external caller references a program-local type
or function by hierarchy. Generated owner callbacks register with the existing
SV inheritance registry. svx_exports.initialize dispatches these callbacks just
as it does for module/interface/generate owners.

Program declaration initialization occurs after a module's active-zero initial
process can start. Therefore selecting program targets makes initialize a task;
call it from initial/task code after svx_init and before loading/starting Python.
It waits on the native registration event at the same simulation time, rather
than polling, inserting a fixed delay or using Python async execution. The
artifact records timing=task. Without program targets the entry stays a function.
Keep the original program's own initial/$finish behavior; the exporter does not
add a process that keeps it alive or change its lifetime.

The [complete example](../examples/sv_scoped/README.md#program-owned-classes)
verifies time-zero startup, same-parameter independent owners, native fields,
inherited static methods, a1ns output/inout task and virtual dispatch from an
original SV class handle back into Python. It configures program state through
exported methods, not illegal external variable access. Program generate owners
use the same local-adapter and initializer contract. Complex owner/source layouts
listed above remain unfinished, not a separate public API.

## Integrated Source Output

For direct SV exports, one command can discover the API and generate an
integrated source copy:

```sh
svx export --package drivers_pkg -f project.f --integrated --out generated
```

Single-input and shared-compilation-unit builds write generated/sv/source.sv
instead of generated/mirrors.sv. Multiple independent compilation units instead
write ordered generated/sv/units/000000_<name>.sv, 000001_<name>.sv, and so on,
one per supplied input. Compile these in place of the supplied original SV
inputs, never alongside them, preserving the original independent/shared unit
semantics. Do not combine independent files into one include wrapper. Python
imports and artifact paths remain under generated/python and generated/artifacts.json.
The original sources are not edited; active includes are copied with logical
source locations, and original classes/types stay in their original package and
lexical scope. The normal bridge renderer supplies the same Python/SV contract,
not another inheritance implementation. The complete call-record package follows
the original native packages, so native enums/nested value types exist before
record aliases and codecs refer to them. Bridges follow the last original
package and precede subsequent top modules/units, including the explicit
svx_exports_pkg::initialize startup entry described above.
No duplicate native class or value declaration is created by relocation.

This direct layout covers selected SV classes, nested classes/class aliases,
standalone supported value types/constants and package callables. It also
preserves normal Python subclass callbacks through the generated native mirror.
It does not yet implement owner-scoped records for alternating source-managed
lineages that use automatically derived values/package callables; such requests
report the unfinished layout instead of emitting invalid forward references.
Multiple independent units currently support this direct SV layout; alternating
cross-language source-managed chains still require the supported shared-unit
layout and owner-local record work described above.

The artifact adds source_replacements, an ordered list of objects with sources
(original inputs) and output (generated replacement), plus
systemverilog_compile_order. Every path is relative to the artifact directory.
A shared-unit replacement lists all original inputs; independent replacements
each list one input. Use this mapping in the original build recipe rather than
guessing which files to remove or sorting filenames independently. Preserve
original macros/includes/options and compile the runtime first unless it is
already among the original inputs. The generated ownership inventory, --check,
obsolete-file cleanup and --incremental no-op reuse cover every replacement.

The underlying inheritance-gen command also supports qualified same-package or
already supported alternating language chains:

```sh
python -m svx inheritance-gen \
  --manifest inheritance.json \
  --sv-source bus_if.sv --sv-source drivers.sv --sv-compilation-unit \
  --python-out generated/python --sv-integrated-dir generated/sv \
  --artifact-manifest generated/svx-artifacts.json
```

Compile generated/sv/source.sv instead of the listed originals, never both.
Runtime packages precede it. Input order, definitions and include paths must
match the project build. Use --sv-compilation-unit only when the original build
actually shares a compilation unit. Direct SV targets preserve independent units
without this flag; shared-unit alternating chains retain their existing path.
--sv-integrated-dir, --sv-stage-dir and --sv-out are mutually exclusive.
Integrated mode produces copies of supplied source units; it is not a request
to infer every class as a generation target. Original sources are not edited.

Original -f/-F filelists, compiler argv, definitions, includes and ordered lazy
libraries can supply this context directly; see [Build Inputs](SVX_BUILD_INPUTS.md).
Do not maintain a second hand-expanded dependency list just for SVX.

## Source Evidence

Discovery writes the normalized manifest and a sibling
<manifest-name>.svx-discovery.json. Keep them together. The record binds the
manifest contract to selected source paths, source bytes and parsing context.
Generation validates this evidence before materializing classes or codec factories.

Ordinary Python dependencies compiled during discovery are recorded automatically;
they do not need a duplicate explicit file list for generation. Generation also
records ordinary user imports compiled while materializing codecs and adapters.
--python-source FILE audits additional explicit files without importing them.
It fingerprints bytes but cannot certify which bytes created an old cached class.

Audited filesystem imports compile current source instead of trusting timestamp/
size bytecode caches, including parent imports and lazy codec imports. Imported
bytes and consumed input selections are checked again before results are returned
or files are published. A change or disappearance rejects the command. Source
guards do not undo arbitrary Python import/codec-factory side effects, lock the
filesystem, or create a transactional source snapshot.

Repeated imports reuse path resolution only within that audited operation, with
file identity/metadata checks invalidating the lookup when its target changes.
This does not cache source acceptance: framework membership and consumed-source
evidence are still checked on each import, and source-byte validation remains
independent. It does not authorize previously unverified cached user modules.

Cached user modules require current validated prior evidence. A changed or
unaudited cached definition requires a fresh command process, not hash editing
or a new explicit source flag. Fresh processes recompute ordinary import sets
and retire unused dependencies. Standard-library, SVX, SvTypes and parser
implementation imports are not automatic application records; explicit sources
and consumed-source overwrite/stability protection remain in effect. Installed
third-party packages and same-name user modules are not blanket-excluded.

Checks replay file-backed Python module selection, participating namespace
ancestors and their ordered directories. They also replay selected SV includes,
ordered source units, macros and compilation-unit mode. A newly preferred module,
header or library candidate invalidates old evidence even if old files still
exist or have identical bytes. Rediscover old records lacking these inventories.
SV-backed validation needs the manifest optional dependency even when generation
does not repeat --sv-source. Custom importers, arbitrary existing object references,
dynamic package-path changes and unrelated external build inputs are not certified.

## Publication And Ownership

Discovery prepares changed manifest/record files before publication. A handled
publication error attempts to restore previous bytes, permissions and timestamps
and remove newly published members; incomplete recovery reports saved originals.
This pair publication is not crash-atomic or multi-writer-safe. Use one writer
per output pair. Readers reject mismatched or incomplete evidence.

Generation validates contracts, renders metadata and preflights paths before
replacing output. Each manifest uses dedicated generated roots. Inventories and
the previous artifact identify owned files; only obsolete entries with matching
generated headers, hashes and current-root ownership can be retired. Modified
files, reassigned outputs and unrelated user files are preserved or rejected.
Do not delete inventories to bypass a conflict or redirect packages with symlinks.
Absolute/traversing paths, duplicate identities and noncanonical inventory entries
are invalid. The gate checks the inventories themselves, not only bridge text.

Generated-file replacement is atomic per file, not across the complete output set.
After interrupted generation, rerun generation and check before building. Lost
inventories can be reconstructed from valid artifact ownership; if both ownership
records are lost, the generator cannot infer historical ownership automatically.

## Recovery And Diagnostics

Expected CLI declaration/filesystem errors report a location and reason and return
2. Put --debug before the subcommand for their traceback. Unexpected implementation
errors retain tracebacks without that flag.

For stale source, rerun discovery then generation in a fresh process. If only
recorded Python inputs changed, refresh records without rewriting matching bridges.
For damaged artifact metadata, restore a known-good copy; if none exists, preserve
the damaged metadata for diagnosis, remove only that generated artifact manifest
and regenerate from the full inputs. Keep inventories and handwritten sources;
do not clear the generated tree. Missing discovery provenance requires rediscovery,
not fabrication of a replacement record.

## Frontend Scope And Cost

Python modules provide explicit decorated declarations. CLI selectors or SV
metadata select exposed classes/members; supplied sources validate semantic kinds, directions,
types, qualifiers, inherited members, typedefs and closed specializations.
Native handle metadata does not add referenced classes as generation targets.
Source discovery is not arbitrary whole-project class inference or proof of every
initializer, policy, source form or codec implementation. Exact inheritance rules
belong to [Lineage](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md); opaque handles and VIF
views belong to [Handle Adapters](CROSS_LANGUAGE_HANDLE_ADAPTERS.md).

Refresh cost includes Python imports/codec materialization, SV parsing and source
selection, manifest checks and adapter generation. It grows with the observed
graph and filesystem latency. Unchanged output timestamps avoid recompilation;
they do not make checks constant-time. Measure the entire refresh/check/run path
on the actual project, not only the number of requested classes.

Within one `inheritance-manifest` discovery operation, source consumers share
raw syntax trees and their source manager. Class ancestry, value selection and
instance discovery also share the default semantic compilation when the actual
syntax trees, library context and elaboration mode are identical. Python Proxy
placeholders are enriched separately for each discovery context; semantic probes
use separate compilations rather than adding checks to the shared source graph.
Generation-time native-handle and virtual-interface enrichment has its own
shared analysis scope. Its consumers reuse one raw parse, but do not retain
discovery trees across the generation input-validation boundary.
Initial and final input observations independently re-read current source bytes
and replay parser-recorded include/library lookups. Within one CLI operation,
discovery and generation may reuse a proven dependency graph after those fresh
checks; changed or non-replayable selections use the full parser path. This does
not keep old file bytes or suppress input-change rejection. The observation
scope ends with the command; it is not changed-unit AST incrementality or a
persistent parse cache. Opt-in unchanged-result reuse remains a separate layer.
Proof contexts use the current physical identity of existing include directories,
so equivalent path spellings can share dependency observations. Directory order
and duplicate entries remain intact; the actual compiler inputs are not rewritten.
Unresolvable directory paths retain their spelling, and symlink retargeting is
checked again on later observations.
Non-replayable selections remain uncached and use the dependencies from that
fresh parse without parsing them a second time. A source/lookup change detected
during capture still forces another fresh parse rather than accepting old data.

### Selected Source Declarations

The frontend imports decorated Python modules and consumes explicit SV JSON
declaration metadata or direct class/package selectors. `--sv-source` supplies
semantic context and VIF declarations; it alone does not select export targets.
Direct selection discovers accessible members and SV constructor signatures.
Python constructor parameters come from declarations, not arbitrary `__init__`
bodies. Selected methods retain effective virtual/static/pure-virtual
qualifiers. Conflicting source metadata rejects before manifest replacement;
local members cannot be exposed, while protected members use derived gateways.

`--python-module` selects decorated classes defined in that module, not classes
merely re-exported by its `__init__.py`. Select the defining module. Mirror-only
stubs supply discovery context but are not export targets. A zero-target error
identifies these cases; adding sources alone does not select a class.

For the explicit Python declaration frontend, enum and packed-struct discovery reuses concrete public SvTypes
declarations visible in the selected Python modules or their ancestor modules.
It compares ordered members/values or fields and recursive width, signedness
and state domain with SV. A typedef retains its native spelling but uses the
underlying value's SvTypes identity. Missing or ambiguous matches need explicit
metadata. Direct SV selectors instead synthesize the public declarations and
their required dependencies, as described above.

A parameterized SV class must resolve to a closed specialization. Default
integral/string value parameters and named class typedefs are discoverable;
localparams are not specialization arguments. X/Z-containing integral values
cannot be flattened to manifest integers and need explicit metadata. A named
typedef such as `typedef Base#(byte, 4) ByteBase;` supplies a stable class identity
without generating the template as another target. Different named
specializations stay distinct. Inline non-default bases need a named typedef
or explicit specialization metadata, not substitution with a default instance.

Native handle typedefs and closed defaults are normalized across fields,
constructors, formals/results and Python declarations. A named closed class
typedef supplies its RemoteRef target identity; unnamed parameterized handles
need explicit identities. Alias-only edits preserve matching manifests;
incompatible static types for one target reject. Source-absent opaque types keep
their explicit spelling and are not source-validated. These handle rules do not
turn referenced classes into generation targets; see
[Handle Adapters](CROSS_LANGUAGE_HANDLE_ADAPTERS.md) for endpoint support.

## Evidence Format

The manifest's discovery_provenance has schema_version and a canonical relative
path. The referenced record has schema_version, contract_sha256, sources and
configuration. Source entries use unique canonical relative paths and lowercase
SHA-256 digests. The manifest/record cannot be their own source dependencies.
The contract digest covers sorted compact ASCII JSON without the provenance key.

Configuration retains python_modules, python_selections, python_namespaces,
python_sources, sv_declarations, sv_sources, sv_dependencies, sv_predefines,
sv_undefines, sv_include_dirs and source_mode. Selection records pair module names
with source paths; namespace records pair module names with ordered directory
paths. Imported original build recipes are replayed as described in Build Inputs.
Applications must not hand-author these records to certify cached definitions.

Generated artifact metadata can be inspected for public generated type names.
Call records, constructor envelopes, object IDs, registration functions and
field-operation envelopes remain private ABI, not application extension hooks.
The API reference owns their public/private classification.
