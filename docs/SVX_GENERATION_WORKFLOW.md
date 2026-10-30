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

## Integrated Source Output

Use integrated output for qualified same-package or alternating language chains:

```sh
python -m svx inheritance-gen \
  --manifest inheritance.json \
  --sv-source bus_if.sv --sv-source drivers.sv --sv-compilation-unit \
  --python-out generated/python --sv-integrated-dir generated/sv \
  --artifact-manifest generated/svx-artifacts.json
```

Compile generated/sv/source.sv instead of the listed originals, never both.
Runtime packages precede it. Input order, definitions and include paths must
match the project build. Multiple inputs require --sv-compilation-unit.
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

Python modules provide explicit decorated declarations. SV metadata selects the
exposed classes/members; supplied sources validate semantic kinds, directions,
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

### Selected Source Declarations

The frontend imports decorated Python modules and consumes explicit SV JSON
declaration metadata. `--sv-source` validates selected SV declarations and
discovers VIF members; it does not infer every class method/field in a project.
Constructor parameters are explicit metadata, not inferred from arbitrary
`__init__` bodies. Selected methods retain effective virtual/static/pure-virtual
qualifiers. Conflicting source metadata rejects before manifest replacement;
local members cannot be exposed, while protected members use derived gateways.

For enum and packed-struct values, discovery reuses concrete public SvTypes
declarations visible in the selected Python modules or their ancestor modules.
It compares ordered members/values or fields and recursive width, signedness
and state domain with SV. A typedef retains its native spelling but uses the
underlying value's SvTypes identity. Missing or ambiguous matches need explicit
metadata; discovery does not synthesize Python value classes or new targets.

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
