# Running SVX Examples

[中文](RUNNING_EXAMPLES.zh-CN.md)

This is the common operational procedure for every example in this directory.
Each example README supplies its own Python entry, generated files, and expected
behavior; follow its instructions in addition to the steps below.

## 1. Prepare the Development Environment

Run these commands from the repository root. Development uses the adjacent
SvTypes checkout as the source of the data contract:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ../svtypes
python -m pip install -e '.[dev,manifest]'
```

Build the native runtime:

```sh
cmake -S . -B build
cmake --build build -j2
```

Installation, native compilation and embedded Python must use the same
interpreter. With multiple Python installations, add
`-DPython3_EXECUTABLE="$(python -c 'import sys; print(sys.executable)')"` to the
first CMake configuration. Use a new build directory when changing the ABI.

The hierarchical-signal example additionally needs a runtime built with the
target tool's VPI headers and direct VPI service enabled:

```sh
cmake -S . -B build \
  -DSVX_SIMULATOR_INCLUDE_DIR=/path/to/simulator/include \
  -DSVX_REQUIRE_DIRECT_VPI=ON
cmake --build build -j2
```

## 2. Generate Declared Artifacts

Run the generation command in the selected example README before compiling its
testbench. Type and channel helper generation produces an SV source file; the
inheritance examples produce both an SV source file and a Python package. Add
those generated files to the compilation/import inputs exactly as that README
states.

Generation should also be part of a project build gate. For a manifest discovered
from source declarations, first run its original `inheritance-manifest` command
with `--check`, using the same modules, declarations and source/compiler options.
Only if discovery passes, check its generated artifacts:

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest <example>/inheritance.json \
  --python-out <example>/generated/python \
  --sv-out <example>/generated/inheritance_mirrors.sv \
  --artifact-manifest <example>/generated/svx-artifacts.json \
  --check
```

An artifact check verifies output against the supplied manifest; it does not
rediscover edited Python declarations. Refreshing artifact input hashes against
an old manifest cannot replace the discovery check. Handwritten manifests have
no discovery command: update their contracts explicitly before checking output.
See [Iterative Development](../docs/SVX_GENERATION_WORKFLOW.md)
for the ordered commands and body-only edit workflow.

## 3. Compile and Load

Ask the installed SVX package for its integration inputs:

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx sv-files
PYTHONPATH=python:../svtypes/python:. python -m svx compile-flags
SVX_LIB_DIR="$PWD/build" PYTHONPATH=python:../svtypes/python:. python -m svx libs
```

Compile the selected example's `tb.sv`, the files printed by `svx sv-files`,
and any generated SV file named in that example README. Use the target tool's
normal DPI mechanism to load the library printed by `svx libs`.
If `tb.sv` already includes those files, compile that top with the required
include directories instead of compiling the same package/interface twice.
Register Lab uses this arrangement, requires the direct-VPI runtime, and sets
`SVX_ARTIFACT_MANIFEST` as shown in its README.

The simulator process needs this baseline import path:

```text
<repository root>:<repository root>/python:<repository root>/../svtypes/python
```

For an inheritance example, append its `generated/python` directory. Do not
replace the simulator's scheduling model with Python `async`, host threads, or
host timers.

## 4. Run and Judge the Result

Run the compiled testbench normally. A successful ordinary example reaches
`svx_shutdown()` and then `$finish` without an `ERROR` display or a fatal
report. Intentional fault cases, including Register Lab's `corrupt_read` and
`function_wait`, require their specific documented fatal diagnostic instead.
Reject a normal pass marker, timeout or crash. An exit status alone, whether
zero or nonzero, does not qualify an expected failure.

The testbench is the sole owner of initialization and shutdown. Python tests
must not call `svx_shutdown()` themselves.

## 5. Quick Source-Level Checks

Before a simulator run, the repository's Python contract tests can validate
generators, descriptors, manifests, and examples that do not require a live
simulation:

```sh
PYTHONPATH=python:../svtypes/python:. .venv/bin/python -m pytest -q
```
