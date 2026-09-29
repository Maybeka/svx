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
python -m pip install pytest
PYTHONPATH=../svtypes/python python -m pip install -e .
```

Build the native runtime:

```sh
cmake -S . -B build
cmake --build build -j2
```

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

Generation should also be part of a project build gate. For inheritance
artifacts, check that committed output is current:

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest <example>/inheritance.json \
  --python-out <example>/generated/python \
  --sv-out <example>/generated/inheritance_mirrors.sv \
  --artifact-manifest <example>/generated/svx-artifacts.json \
  --check
```

## 3. Compile and Load

Ask the installed SVX package for its simulator-neutral integration inputs:

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx sv-files
PYTHONPATH=python:../svtypes/python:. python -m svx compile-flags
SVX_LIB_DIR="$PWD/build" PYTHONPATH=python:../svtypes/python:. python -m svx libs
```

Compile the selected example's `tb.sv`, the files printed by `svx sv-files`,
and any generated SV file named in that example README. Use the target tool's
normal DPI mechanism to load the library printed by `svx libs`.

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
report. `milestone_1_error` and explicitly named expected-failure testbenches
are different: their documented fatal diagnostic is the expected result.

The testbench is the sole owner of initialization and shutdown. Python tests
must not call `svx_shutdown()` themselves.

## 5. Quick Source-Level Checks

Before a simulator run, the repository's Python contract tests can validate
generators, descriptors, manifests, and examples that do not require a live
simulation:

```sh
PYTHONPATH=python:../svtypes/python:. .venv/bin/python -m pytest -q
```
