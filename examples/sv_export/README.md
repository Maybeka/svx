# Export Existing SV Declarations

[中文](README.zh-CN.md)

Follow the common [run guide](../RUNNING_EXAMPLES.md) first. This example needs
the manifest extra but no handwritten manifest, SV declarations JSON, Python
Mirror stub or decorated Python subclass.

## Generate

From the repository root:

```sh
svx inspect -f examples/sv_export/design.f --kind class type
svx export --class export_driver_pkg::Driver \
  -f examples/sv_export/design.f --out examples/sv_export/generated
```

inspect lists candidates without generating files. Add --name 'export_driver_pkg::*'
or --json for filtered declarations, source locations and availability reasons.
The [workflow](../../docs/SVX_GENERATION_WORKFLOW.md#direct-sv-export) defines
scope eligibility versus actual type/signature qualification.

The command reuses the original filelist and discovers constructor parameters,
fields, method signatures and the imported `export_base_pkg::Base` ancestry.
Only Driver is a requested export target. Import it with:

```python
from svx_mirror.export_driver_pkg import Driver
```

Mode and Packet are discovered automatically from its signatures and fields.
They are public SvTypes Enum/SvStruct declarations in the same Python module.
The other package also defines Mode; its identity remains distinct at
svx_mirror.export_base_pkg.Mode. To export values without any class:

```sh
svx export --type export_driver_pkg::Mode export_driver_pkg::Packet \
  -f examples/sv_export/design.f --out .tmp/exported-types
```

Those Python modules need SvTypes, not the SVX native runtime.

Compile-time parameters can be selected without exporting a class:

```sh
svx export --constant 'export_driver_pkg::*' \
  -f examples/sv_export/design.f --out .tmp/exported-constants
```

Add .tmp/exported-constants/python to the Python path:

```python
from svx_mirror.export_driver_pkg import COUNT, FLAGS, DEFAULT_PACKET
assert COUNT == 18
assert str(FLAGS) == '10xz'
assert DEFAULT_PACKET.tag.value == 0x81
```

These are evaluated snapshots using SvTypes codecs, not live native variables.
The example includes imported parameter expressions, strings, real values,
packed-struct and array parameters. Package selection includes owned constants;
--exclude-constant can remove unneeded snapshots. The generated constants were
compared against an independently compiled SV evaluation of these declarations.

To select every owned class, supported value type, constant and function/task, replace `--class` with
`--package export_driver_pkg`. Imports provide dependency context; they do not
automatically export all of `export_base_pkg`. `--recursive-packages` explicitly
requests that expansion. See [target selection](../../docs/SVX_GENERATION_WORKFLOW.md#direct-sv-export)
for patterns, member selection and current boundaries.

For a package API in a larger project, the same export command can include
--sv-elaboration packages. It preserves explicit-source preprocessing while
omitting design-instance analysis and DUT-only library requests. It does not
remove explicitly listed RTL files from parsing or change the simulation build.
See [analysis policy](../../docs/SVX_GENERATION_WORKFLOW.md#direct-sv-export).
Add --incremental to that export command for verified no-op reuse. Repeat it
with --check to leave both outputs and local cache unchanged. Input or lookup
changes select the full pipeline; --incremental --refresh-cache forces it.
This does not cache runtime Python tests or parse only individual changed files.

## Compile And Run

The top calls svx_init(), svx_exports_pkg::initialize(), then loads/starts Python.
The generated initialization function explicitly registers factories/dispatchers
and is idempotent. Do not depend solely on package-variable initializers when
analyzing original and generated files in separate compiler invocations.

The package API also supports an integrated source copy:

```sh
svx export --package export_driver_pkg --integrated \
  -f examples/sv_export/design.f --out .tmp/sv-export-integrated
```

For that variant, change the generated include in tb_package_calls.sv to
`.tmp/sv-export-integrated/sv/source.sv` and compile that top without drivers.sv.
Use the printed Python path and artifact manifest. The same package_calls.py
checks and3ns pass markers apply. Native classes, enums and interface definitions
are present exactly once, before the ordinary generated call records/bridges.
Both layouts have been compiled and run. See
[source-copy rules](../../docs/SVX_GENERATION_WORKFLOW.md#integrated-source-output).

For the default separate layout:

Compile drivers.sv before tb.sv, with the repository root on the include path.
The top includes SVX and generated mirrors, so do not compile those packages
again. Add examples/sv_export/generated/python and the repository root to the
simulation process's Python path, and load the ready native runtime as described
in the shared run guide.

entry.py creates a real SV Driver, reads/writes its inherited count field,
calls a two-nanosecond task with output/inout holders, and calls a static method.
It round-trips enums and packed structs, preserves X/Z in a struct field, and
updates a real SV struct field both as a whole and by an addressed member.
Its ordinary Python subclass overrides status and uses super(). It is published
back to SV as a Base handle; the SV virtual call returns 108 through Python.

Expect SV_EXPORT_PYTHON_PASS and SV_EXPORT_SV_PASS, finishing at2ns.
Validate both discovery and generation without rewriting files by repeating the
export command with --check. Generated files are ignored by Git.

## Package Functions And Tasks

Generate direct function imports without selecting any class:

```sh
svx export --callable 'export_driver_pkg::*' \
  -f examples/sv_export/design.f --out examples/sv_export/generated
```

Compile drivers.sv followed by tb_package_calls.sv instead of tb.sv, with the same
runtime/include/Python setup above. package_calls.py imports ordinary functions:

```python
import svx
from svtypes import Int
from svx_mirror.export_driver_pkg import add, step
previous, total = svx.Output(), svx.Inout(10)
assert add(Int(2), Int(3), previous) == 23
step(Int(4), previous, total)
assert previous.value == 1 and total.value == 15
```

All parameters retain their positions; no response records are exposed. The
example also calls a void no-argument function, round-trips a Packet containing
X/Z, creates/returns unexported Other objects as opaque handles, checks native
handle identity, and returns/reads/passes back a restricted VIF view. The SV top
checks native package state and exactly3ns elapsed time. Expect
PACKAGE_CALLS_PYTHON_PASS and PACKAGE_CALLS_SV_PASS. These operations reuse SVX's
normal call transport and require the running native endpoint; pure type and
constant snapshots above do not.

## Independent Compilation Units

The optional units.f project keeps two different $unit::UnitLocal declarations
and macro widths5/13 in separate compilation units. It exports only the API in
unit_child_pkg, whose Child inherits unit_base_pkg::Base:

```sh
svx export --package unit_child_pkg --integrated --incremental \
  -f examples/sv_export/units.f --out .tmp/sv-export-units
```

Compile the runtime packages first, then replace each original units.f source
with its corresponding source_replacements output from artifacts.json. Follow
systemverilog_compile_order and preserve independent analysis; do not include
all replacements in one wrapper. Select tb_independent_units. The existing top
already calls svx_exports_pkg::initialize before loading unit_entry.py. Add the
generated python directory and repository root to the simulation Python path,
and load the runtime as in the common guide.

The SV probes verify that the two same-named native classes return11/22 and
that macros have not leaked. Python creates a Child subclass, accesses inherited
and local fields, executes a2ns task with output/inout, then explicitly publishes
the object. SV obtains the real Child handle and its virtual call reaches the
Python override. Expect INDEPENDENT_UNITS_PYTHON_PASS and
INDEPENDENT_UNITS_SV_PASS at2ns. $unit classes are preserved, not exported in
this example. Original sources plus a separately analyzed bridge, a top-include
variant, and the integrated replacement build passed native separate-analysis execution.

## Source Files

- [Original SV declarations](drivers.sv) and [original filelist](design.f).
- [Class-extension entry](entry.py) and [its SV top](tb.sv).
- [Package-function entry](package_calls.py) and [its SV top](tb_package_calls.sv).
- [Independent-unit filelist](units.f), [base unit](base_unit.sv),
  [child unit](child_unit.sv), [Python entry](unit_entry.py) and [SV top](tb_units.sv).
