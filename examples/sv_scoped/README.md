# Export Nested SV Classes

[中文](README.zh-CN.md)

For class bridges, prepare the runtime using the shared [run guide](../RUNNING_EXAMPLES.md).
Type/constant-only snapshots below need the manifest CLI and SvTypes, not the native runtime.
This example exports original package-scoped nested types without moving or
copying the native classes into generated packages.

## Generate

From the repository root:

```sh
svx export --class 'scoped_classes_pkg::*::Inner' scoped_classes_pkg::Outer_Inner \
  -f examples/sv_scoped/design.f --out examples/sv_scoped/generated
```

Only these four classes are generation targets. Their constructors, methods,
fields, original cross-package Base ancestry and required package value types
are discovered automatically. To select the package's owned declarations,
including Outer and OtherOuter themselves, use --package scoped_classes_pkg.
The same command accepts --sv-elaboration packages for package-only analysis;
it does not alter the original native compilation inputs.

```python
from svtypes import Int
from svx_mirror.scoped_classes_pkg import Outer, OtherOuter, Outer_Inner
first = Outer.Inner(Int(3))
second = OtherOuter.Inner(Int(3))
```

The two Inner types have distinct native and Python identities. Their public
names are svx_mirror.scoped_classes_pkg.Outer.Inner and
svx_mirror.scoped_classes_pkg.OtherOuter.Inner. `__name__` remains Inner,
`__module__` is svx_mirror.scoped_classes_pkg, and `__qualname__` retains its lexical
scope. Outer_Inner stays distinct from Outer.Inner, including in private SV
helper names. Use `from svx_mirror.scoped_classes_pkg import Outer`, then
Outer.Inner; Outer is a class/type namespace, not an importable Python submodule.
The additional outer.Inner type differs from Outer.Inner by case only; internal
files and include guards retain this distinction on case-insensitive hosts too.

When only Inner is selected, Outer is a namespace holder, not an automatically
exported or constructible native mirror. No Outer object is required to create
Inner. If Outer is selected too, its real generated mirror owns the Inner class
attribute. Internal definition files re-export the same class object, not an
extra wrapper or a second native type. The artifact manifest records the public
qualified name.

## Compile And Run

Compile [classes.sv](classes.sv), then [tb.sv](tb.sv), with the repository root
on the include path. The top includes the runtime and generated bridge; do not
compile those packages again. Add examples/sv_scoped/generated/python and the
repository root to the simulation's Python path and load the ready native runtime.

[entry.py](entry.py) creates Inner directly, updates its inherited count field,
calls a two-nanosecond task with an output holder, calls a static function,
round-trips Packet and updates its native packed field without losing X/Z.
PythonInner overrides status through ordinary Python inheritance. The SV top
retrieves it as the original scoped_base_pkg::Base handle and checks the virtual
call returns121. Expect SCOPED_PYTHON_PASS and SCOPED_SV_PASS at2ns. Repeat the
generation command with --check to validate outputs without rewriting them.

This qualification covers package-owned nested class declarations and their
supported package and class-owned value dependencies. Outer.LocalMode and
Outer.LocalPacket remain native nested types: entry.py passes the packed struct
through echo_local and writes its native mode field while preserving X/Z flags.
They are available on either the unselected Outer namespace or its selected
mirror class. To export just that value API without any class target, run:

```sh
svx export --type scoped_classes_pkg::Outer::LocalPacket \
  -f examples/sv_scoped/design.f --out examples/sv_scoped/generated-values
```

Import Outer from svx_mirror.scoped_classes_pkg and use Outer.LocalPacket;
the required Outer.LocalMode enum is generated automatically. This import needs
SvTypes, not a running simulation.

## Integrated Variant

```sh
svx export --package scoped_classes_pkg --integrated \
  -f examples/sv_scoped/design.f --out .tmp/sv-scoped-integrated
```

In tb.sv, replace the generated mirrors include with
`.tmp/sv-scoped-integrated/sv/source.sv`. Compile tb.sv without classes.sv,
because the integrated copy already contains the original packages. Use
.tmp/sv-scoped-integrated/python and its artifacts.json for this run. The same
entry.py, virtual callback and pass markers apply; the package variant also
constructs Outer.Alias, the native class alias for Outer.Inner. Both integrated
and separate bridge variants have been compiled and run.

Module/interface/program instance bindings and alternating source-managed
lineages with automatic value records remain unfinished. See the current
[export boundaries](../../docs/SVX_GENERATION_WORKFLOW.md#direct-sv-export).

[Original filelist](design.f).

## Values Without A Package

[unit_values.sv](unit_values.sv) defines a unit-level enum, packed struct,
aliases, dynamic-array alias, constants and Holder's public nested types:

```sh
svx export --type '$unit::*' --constant '$unit::*' \
  --sv-source examples/sv_scoped/unit_values.sv --out .tmp/unit-values
PYTHONPATH=.tmp/unit-values/python python examples/sv_scoped/unit_values.py
```

[unit_values.py](unit_values.py) checks public SvTypes declarations, alias
identity, packed X/Z snapshots and nested types without loading SVX's native
runtime. Expected marker: UNIT_VALUES_PYTHON_PASS. The optional
[SV top](tb_unit_values.sv) includes the original declarations in its unit and
checks the same native values; expect UNIT_VALUES_NATIVE_PASS. Both checks have
run remotely. No native class mirror is generated by requesting Holder.Payload.

Imports use svx_mirror_unit.unit_0. Independent units use distinct indices;
inspect --json reports compilation_unit_index, and a selector such as
'$unit[1]::Mode' disambiguates a duplicate name. See the authoritative
[unit-value workflow](../../docs/SVX_GENERATION_WORKFLOW.md#compilation-unit-values)
for grouping, ownership and unfinished runtime-record layouts.

## Instance-Owned Type Snapshots

[instance_values.sv](instance_values.sv) declares types and constants in module,
interface, program and generate scopes. Follow the single authoritative
[generation workflow](../../docs/SVX_GENERATION_WORKFLOW.md#instance-owned-values)
to export them from [the original filelist](instance_values.f). Add the generated
.tmp/instance-values/python directory and repository root to the Python path,
then run:

```sh
python -m examples.sv_scoped.instance_values
```

[The Python example](instance_values.py) checks public SvTypes enum/struct codecs,
aliases, nested Holder.Tag, equal-parameter independent owners and nondefault
widths. It prints INSTANCE_VALUES_PYTHON_PASS without loading a native runtime.
Compile/run the original SV source to see INSTANCE_VALUES_NATIVE_PASS at1ns;
the five INSTANCE_VALUE and two INSTANCE_INDEX rows have been compared remotely
against the generated Python snapshots. No generated SV bridge is needed here.
Parameterized enum literals use explicit W-sized casts; the program includes
its own2ns process so it cannot end the simulation before the top's1ns check.
Runtime class-field/method bindings are exercised separately below.

## Instance-Owned Runtime Values

[The SV source](instance_runtime_values.sv), [filelist](instance_runtime_values.f)
and [Python entry](instance_runtime_values.py) use three original module owners,
two with width8 and one with width13. Export just the classes using the
[workflow command](../../docs/SVX_GENERATION_WORKFLOW.md#instance-owned-values);
the CLI collects each owner's Mode, Payload, Word, Packets and Modes dependencies.
Compile the artifact compile order and use its generated Python path. The SV top
initializes the generated startup module and starts the Python entry.

Python constructs native objects, updates a struct field locally, calls methods
with enum/struct/fixed-array/queue values, and waits for three1ns output/inout
tasks. A Python subclass overrides virtual methods; an SV base-class handle
then calls it, including super calls back into SV. Both
INSTANCE_RUNTIME_VALUES_PYTHON_PASS and INSTANCE_RUNTIME_VALUES_NATIVE_PASS
are required. The exact example passed remotely; equivalent interface and
program owner scenarios also passed. Generate-owned nominal runtime types and
cross-owner dependencies are not claimed by this example.

## Classes Without A Package

[unit_classes.sv](unit_classes.sv) declares Driver directly in the compilation
unit, extending UnitBase in the same unit and a real package-owned Base.
The [original top](tb_unit_classes.sv)
includes it in the same unit. Reuse the project's [filelist](unit_classes.f):

```sh
svx export --class Driver -f examples/sv_scoped/unit_classes.f \
  --sv-elaboration packages --out .tmp/unit-classes
```

No declarations JSON, stub or new wrapper package is required. The command
automatically generates .tmp/unit-classes/sv/source.sv and sv/exports.sv.
Compile the prepared SvTypes and SVX runtime packages first, then those two
generated inputs in artifact order instead of the original top. Do not compile
unit_classes.sv separately: its declaration is already in the source copy.
Set the Python path to .tmp/unit-classes/python and the repository root, and
use its artifacts.json with the ready native runtime. The top instantiates
one svx_exports module and calls exports.initialize after svx_init, before
loading the Python entry. Independent units need this explicit connection;
unused global initializer side effects are not a reliable startup path.

[unit_classes.py](unit_classes.py) imports Driver from svx_mirror_unit.unit_0,
constructs native instances, reads and updates both inherited and local fields,
calls a2ns task with output/inout and static functions declared on Driver and
both ancestors, and overrides a virtual
method using normal Python inheritance. The top retrieves the Python-created
child as the original SV Driver handle and verifies its virtual call returns108.
Expect UNIT_CLASSES_PYTHON_PASS and UNIT_CLASSES_NATIVE_PASS at2ns. This exact
CLI generation/check/native scenario has run remotely. Two independent
same-named Driver classes have also passed source-only generation and native
execution, including a nondefault13-bit generic ancestor.
Only Driver is an export target: ancestor metadata and static dispatch are
included as dependencies without creating additional constructor targets.

See the authoritative [unit-class workflow](../../docs/SVX_GENERATION_WORKFLOW.md#compilation-unit-classes)
for indexed selectors, source grouping, startup and remaining owner-local layouts.

## Nested Compilation-Unit Classes

The [native declarations](unit_nested.sv), [top](tb_unit_nested.sv) and
[Python entry](unit_nested.py) use the same owner-local layout:

```sh
svx export --class '$unit::*::Inner' Outer_Inner Outer::Alias \
  --type UnitModes -f examples/sv_scoped/unit_nested.f \
  --sv-elaboration packages --out .tmp/unit-nested
```

Compile the ready SvTypes/SVX runtime packages, then the reported source
replacement and .tmp/unit-nested/sv/exports.sv. Do not compile the original top
or declarations again. Run tb_unit_nested with .tmp/unit-nested/python and the
repository root on the Python path, its artifacts.json and the native runtime.
The top already contains the single startup instance and initialize call.

Only the five selected class views are generated. Outer and OtherOuter are
Python namespaces, not constructor targets. Outer.Inner, OtherOuter.Inner,
outer.Inner and Outer_Inner stay distinct; Outer.Alias retains the selected
native class typedef name. The original Outer constructor deliberately fails
if called, proving that Inner construction does not allocate an Outer object.

Root UnitMode and UnitPacket dependencies are discovered automatically and
remain real SvTypes enum/packed-struct declarations. The explicit --type selects
the public UnitModes container alias; a class export need not publish every
non-nominal source typedef. The entry passes all three through native methods,
updates a packed field while preserving X/Z, calls a2ns output/inout task and
static method, and overrides a virtual method from Python. The SV top receives
the original Outer::Inner handle and verifies callback108. An Inner-local
UnitMode typedef also checks that explicit $unit type references are preserved.
Class-owned Inner.State and Inner.Packet are discovered as nominal dependencies
too. The derived class declares another State with the same literal names but
different values; inherited methods/fields still use Outer.Inner's original
types. Native enum calls and packed-field X/Z updates verify both identities.
Expect UNIT_NESTED_PYTHON_PASS and UNIT_NESTED_NATIVE_PASS at2ns.

This CLI/check/native scenario has run remotely. See the
[authoritative unit-class workflow](../../docs/SVX_GENERATION_WORKFLOW.md#compilation-unit-classes)
for indexed independent owners and remaining specialization/instance layouts.

## Instance-Owned Classes

Select a concrete module instance, not just the source module definition:

```sh
svx export --class 'tb_instance_classes.*.Driver' \
  -f examples/sv_scoped/instance_classes.f --out .tmp/instance-classes
```

No declaration JSON, prototype package or Python stub is needed. The command
reads the original build inputs and evaluates each instance's types. Its three
public views retain the source class name:

```python
from svx_mirror_instance.tb_instance_classes.a.classes import Driver as DriverA
from svx_mirror_instance.tb_instance_classes.b.classes import Driver as DriverB
from svx_mirror_instance.tb_instance_classes.c.classes import Driver as DriverC
```

DriverA and DriverB bind different live owner contexts despite using the same
module parameters; DriverC has13bit rather than8bit storage. The original Base
and Driver remain in SV. Bound adapters receive their native types through
type parameters, without relocating or redeclaring user classes. Only the three
selected Driver views are targets; Base is lineage context, not an extra request.

Compile SvTypes/SVX runtime packages first, then the artifact's reported
systemverilog_compile_order. Replace the original top input with its generated
source copy; do not compile both. The supplied top already instantiates
svx_exports and calls initialize after svx_init, before loading Python.

instance_classes.py checks construction, inherited fields and virtual methods,
parameterized bit widths, independent live owner-state reads/writes, direct/inherited static
calls and a2ns output/inout task. It publishes PythonDriver as the original SV
Driver handle; the native top verifies the Python override. Expected markers
are INSTANCE_CLASSES_PYTHON_PASS and INSTANCE_CLASSES_NATIVE_PASS at2ns.

## Generate-Owned Classes

Sources: [design](generate_classes.sv), [testbench](tb_generate_classes.sv),
[Python](generate_classes.py), [filelist](generate_classes.f).

Export actual lanes directly from the original filelist:

```sh
svx export --class 'tb_generate_classes.*.lane[*].active.Driver' \
  -f examples/sv_scoped/generate_classes.f --out .tmp/generate-classes
```

The three module instances each contain two lanes. Their six Driver views keep
separate owner contexts and8/9/13/14bit native fields. The nested active block
deliberately shadows LANE with99; the original INDEX and export selection still
refer to the correct outer lane. Only Driver is selected; Base stays lineage
context. No user prototype, declaration JSON or class relocation is involved.

For example, the generated import for b.lane[1].active is:

```python
from svx_mirror_instance.tb_generate_classes.b.svx_scope_4_lane_p1.active.classes import Driver
```

Compile the runtime packages, then the artifact's systemverilog_compile_order,
replacing the original top input rather than compiling both copies. The supplied
top uses the same svx_exports.initialize after svx_init. Complete adapters stay
inside their original generate owner, so no native class type escapes through
a bound module parameter. Parent guards are captured before children, retaining
lexical shadowing and actual genvar values.

generate_classes.py checks construction, live fields and module state, direct/
inherited static methods and a1ns output/inout task. It publishes all six
objects; the SV top casts them to the original Driver type in each lane and
checks virtual dispatch into PythonDriver. Expected markers at1ns are
GENERATE_CLASSES_PYTHON_PASS and GENERATE_CLASSES_NATIVE_PASS. The ordinary
source-only CLI/check/native flow passed remotely for module and interface
containers, including an unnamed generate-block variant. See the
[workflow](../../docs/SVX_GENERATION_WORKFLOW.md#generate-owned-classes) for
remaining source-placement layouts.

## Program-Owned Classes

Sources: [program](program_classes.sv), [top](tb_program_classes.sv),
[Python](program_classes.py), [filelist](program_classes.f).

```sh
svx export --class 'tb_program_classes.*.Driver' \
  -f examples/sv_scoped/program_classes.f --out .tmp/program-classes
```

The three programs expose the same Driver class name at
svx_mirror_instance.tb_program_classes.<a/b/c>.classes.Driver. Their original
classes remain program-local. Generated callbacks select the actual owner,
then use the existing SV registry for fields, construction and method dispatch.
The top does not read program variables or call program functions by hierarchy.

Compile the runtime packages, then replace the original top with the artifact's
reported source copies/compile order. The top calls svx_init and the same
svx_exports.initialize before loading Python. For program targets initialize is
a task: it waits for program declaration registration through an SV event,
without advancing simulation time. The top asserts time is still zero before
Python starts. Module/interface-only generation retains a function initializer.

Python configures state through exported methods, constructs objects, checks
same-parameter owner independence and8/13bit fields, inherited statics and a1ns
output/inout task. verify_published runs in SV with the original Driver handle
and invokes the Python override. Expected markers at1ns are
PROGRAM_CLASSES_PYTHON_PASS and PROGRAM_CLASSES_NATIVE_PASS. The source-only
CLI/check/native flow passed remotely. See the
[program workflow](../../docs/SVX_GENERATION_WORKFLOW.md#program-owned-classes)
for initialization/lifetime and remaining layout boundaries.
