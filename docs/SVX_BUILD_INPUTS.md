# Reuse Existing SV Build Inputs

SVX can import the source order, macro definitions and include paths from the
project's existing build. Do not maintain a second list of class dependencies.
Importing build inputs supplies parsing context; it does not select additional
classes for generation, replace the project build system, or execute a compiler.

## Original Filelists

```sh
svx compile-config \
  --sv-filelist build/design.f --sv-build-directory "$PROJECT_BUILD"

svx inheritance-manifest \
  --sv-filelist build/design.f --sv-build-directory "$PROJECT_BUILD" \
  --sv-declarations verification/selected_classes.json \
  --out generated/inheritance.json

svx inheritance-gen \
  --sv-filelist build/design.f --sv-build-directory "$PROJECT_BUILD" \
  --manifest generated/inheritance.json \
  --python-out generated/python --sv-out generated/mirrors.sv \
  --artifact-manifest generated/artifacts.json
```

CLI filelist filenames are relative to the invocation directory. With
`--sv-filelist` (`-f`), entries are relative to the original build working
directory, not automatically to the filelist's directory. With
`--sv-relative-filelist` (`-F`), entries are relative to the containing filelist.
Nested `-f` retains its current path context; nested `-F` switches to its own
directory. Preserve the convention used by the original build.

Filelists support shell-like quoting, escaped whitespace, `#`, `//` and block
comments. Paths expand `$NAME`, `${NAME}`, `$(NAME)` and `~`; unset environment
variables reject. Macro replacement text is not environment-expanded. For
literal string-valued macros, preserve the quotes in the compiler argv; in a
filelist they may need escaping, for example `-DLABEL=\"uart\"`.

## Capture the Actual Compiler Invocation

When the build system already constructs a command, export its actual argv and
working directory at that point:

```json
{
  "directory": "/project/build/work",
  "arguments": ["compiler", "-f", "design.f", "+define+ENABLE_CHECKS", "+incdir+include"]
}
```

Use the exported file directly:

```sh
svx compile-config --sv-build-command build/compiler-input.json
svx inheritance-gen \
  --sv-build-command build/compiler-input.json \
  --manifest generated/inheritance.json \
  --python-out generated/python --sv-out generated/mirrors.sv \
  --artifact-manifest generated/artifacts.json
```

The JSON object contains exactly `directory` and `arguments`, including the
compiler executable as the first argument. A relative `directory` is relative
to the JSON file. Export the final compile command, not a shell script, Make
invocation or unresolved configuration template. Generate this record as part
of the original build rather than editing or copying its flags by hand.

Source files added by SVX integration can be appended with `--sv-source` without
relisting upstream dependencies. Explicit `--sv-define`, `--sv-undefine` and
`--sv-include-dir` remain available for intentional additions. Imported inputs
are processed first; explicit macros override them, and explicit include paths
are appended. Multiple command files are processed in argument-list order,
then `--sv-filelist` inputs, then `--sv-relative-filelist` inputs. Prefer one
actual command record when mixed ordering matters.

## Supported Semantics and Limits

The importer supports ordered SV sources, nested filelists, `+incdir+`, `-I`,
`+define+`, `-D`, `-U`, explicit library files (`-v`), ordered library-directory
search (`-y` / `+libext+`), and compilation-unit
selection. Repeated imported definitions use their final replacement; a later
definition cancels an earlier undefinition. Known tool defaults and implicit
UVM sources are resolved from the original compiler environment where supported.
Inspect `compilation_unit` and the resolved source list with `compile-config`.
For a standalone filelist or an unrecognized tool default, use
`--sv-compilation-unit` if the original build shares macros across source files.

Known output, native-linking, diagnostic, timing and runtime-instrumentation
arguments are reported in `non_parser_arguments`; they are not used to predict
simulation behavior. Unknown options reject instead of being dropped. This is
not universal command-line compatibility: arbitrary tool extensions, per-file
language/macro resets and shell globbing are not imported. Duplicate source entries reject rather than
silently changing their compilation-unit meaning.

Library directories remain search locations, not added source trees. The
frontend indexes declarations and design-unit references in supplied sources,
then searches for an unresolved unit by exact filename: directory order first,
then `+libext+` extension order within that directory. Selected files are parsed
as library units and their references are searched recursively. There is no
recursive directory scan and no implicit `.v`/`.sv` added to an explicit suffix
list. Without `+libext+`, lookup uses the exact unit basename, with no automatic
extension. An empty suffix in an explicit list also requests that exact basename.
Existing explicit declarations suppress unnecessary library loads. An
invalid selected file is an error, not a reason to silently select a later file.
Unresolved units with no matching file remain for the ordinary semantic and
original-compiler diagnostics; SVX does not invent placeholder modules.

Only selected library files and their include dependencies are fingerprinted.
Read-only checks repeat lookup, so a newly added earlier candidate changes the
selected dependency set and makes the outputs stale even if the filelist did
not change. Editing an unrelated unused library file does not invalidate them.
Class/interface/package references are obtained from parsed syntax, not regular
expression scans. A selected source containing extra declarations is kept as a
whole file, as in ordinary source-library compilation; those declarations do not
automatically become generation targets.

Protected source regions remain opaque. Recognizing their boundaries does not
decrypt them or make hidden classes available for mapping. Selected public
declarations and signature types must resolve from readable source; actual
generated code must still pass the original project compiler.

Do not use `--sv-integrated-dir` on an entire project command merely to provide
dependency context: that mode emits an integrated copy of every supplied source.
For the ordinary selected-boundary workflow, use `--sv-out` as above.

## Freshness Checks

Repeat the same discovery and generation commands with `--check`. SVX rereads
the original command record and nested filelists. Their hashes, resolved paths,
source/include order, macro configuration, and relevant auxiliary configuration
files participate in the input records. Discovery provenance also replays the
import recipe before loading discovered declarations, including changed path
selection caused by the current environment. `compile-config` output is for
inspection, not a frozen replacement for the original build inputs.

This checks selected inputs; it does not monitor the build system continuously
or guarantee an atomic snapshot against concurrent file edits. Refresh the
original build export before checking if the build recipe itself changed.

See the [OpenTitan UART guide](../examples/opentitan_uart/README.md) for real
project integration and its separately recorded remote qualification.
