# SVX Production Project Layout

## 1. Purpose

This document defines the intended production project structure for SVX.

SVX uses this production-shaped layout with clear ownership boundaries
between Python APIs, the C++ runtime, SystemVerilog services, examples, tests,
documentation, and the external SvTypes dependency.

## 2. Target Layout

```text
svx/
├── README.md
├── pyproject.toml
├── CMakeLists.txt
├── docs/
│   ├── SVX_SPEC.md
│   ├── SVX_PROJECT_LAYOUT.md
│   ├── architecture/
│   ├── decisions/
│   └── plans/
│
├── python/
│   └── svx/
│       ├── __init__.py
│       ├── export.py
│       ├── context.py
│       ├── channel.py
│       ├── primitives.py
│       ├── process.py
│       └── errors.py
│
├── svx_runtime/
│   ├── include/
│   │   └── svx/
│   │       ├── svx.hpp
│   │       ├── common.hpp
│   │       ├── python_runtime.hpp
│   │       ├── context.hpp
│   │       ├── export_registry.hpp
│   │       ├── channel.hpp
│   │       ├── process.hpp
│   │       ├── fork.hpp
│   │       ├── timing.hpp
│   │       ├── display.hpp
│   │       └── vpi.hpp
│   │
│   └── src/
│       ├── svx.cpp
│       ├── python_runtime.cpp
│       ├── context.cpp
│       ├── export_registry.cpp
│       ├── channel.cpp
│       ├── process.cpp
│       ├── fork.cpp
│       ├── timing.cpp
│       ├── display.cpp
│       └── vpi.cpp
│
├── sv/
│   ├── svx_pkg.sv
│   ├── svx_defs.svh
│   ├── svx_init.sv
│   ├── svx_process.sv
│   ├── svx_fork.sv
│   ├── svx_channel.sv
│   ├── svx_timing.sv
│   ├── svx_display.sv
│   └── svx_vpi.sv
│
├── examples/
│   ├── milestone_1_basic/
│   │   ├── README.md
│   │   ├── tb.sv
│   │   └── tests/
│   │       └── basic_test.py
│   │
├── tests/
│   ├── python/
│   ├── cpp/
│   ├── sv/
│   └── integration/
│       ├── milestone_1/
│       └── milestone_2/
│
├── tools/
│   ├── build_svx.py
│   ├── run_sim.py
│   └── generate.py
│
└── third_party/
```

## 3. Directory Responsibilities

### 3.1 `python/svx`

Python user-facing API for SVX runtime services.

This package owns:

- `@svx.export`
- SVX execution-context validation
- primitive APIs such as `display`, `delay`, and `fork_join`
- named channel APIs for raw payload and typed transaction exchange
- process and process-group handle wrappers
- exception types and error policy configuration

This package may call into the native SVX runtime extension, but it should not
own simulator scheduling itself.

### 3.2 External `svtypes`

SvTypes is an independent, versioned dependency in the separate SvTypes
repository. The SvTypes repository owns:

- SystemVerilog-like Python type modeling
- package and scope modeling
- object, struct, enum, parameter, and collection modeling
- SV/C++ code generation
- Python-side serialization

`svtypes` must not import `svx`.

SVX consumes SvTypes as a versioned external dependency for typed data exchange.
SvTypes must remain usable without the SVX runtime.

### 3.3 `svx_runtime`

C++ implementation of the SVX shared library loaded by the simulator.

This directory owns:

- embedded CPython interpreter lifecycle
- Python module loading
- Python export lookup and invocation
- GIL management
- SVX execution-context push/pop
- exception capture and traceback reporting
- callable and process handle management
- channel registry and payload transfer
- DPI/VPI bridge implementation

Public C++ headers live under `svx_runtime/include/svx`.

Implementation files live under `svx_runtime/src`.

### 3.4 `sv`

SystemVerilog package and simulator-side services.

This directory owns:

- `svx_pkg`
- `svx_init`
- `svx_load`
- `svx_start`
- exported DPI tasks/functions used by Python primitives
- simulator-owned process creation
- named channel registry and payload synchronization
- timing primitives
- display/logging primitives
- VPI-related declarations

SystemVerilog remains the owner of simulation timing and process scheduling.

### 3.5 External `svtypes_runtime`

Language support generated or maintained for SvTypes.

The production SVX repository should not own this directory. It is provided by
the versioned SvTypes dependency. The SvTypes repository owns:

- `svtypes_pkg.sv`
- `svtypes.hpp`
- shared serialization helpers
- base classes/helpers needed by generated SvTypes code

This support must not depend on the SVX runtime. It is support for the
independent SvTypes data contract, not part of the SVX simulator runtime.

### 3.6 `examples`

Runnable examples for users and developers.

Examples are not the primary verification mechanism; they demonstrate intended
usage.

Each example should include a short `README.md` with the expected build/run
command once those commands are stable.

### 3.7 `tests`

Automated project tests.

The repository contains Python tests, fixtures, and SV/Python integration
sources.

### 3.8 `docs`

Project specifications, architecture notes, plans, and design decisions.

Suggested subdirectories:

- `docs/architecture`: stable architecture documents
- `docs/decisions`: ADR-style decision records
- `docs/plans`: implementation plans and migration plans

Important decisions that should have dedicated records:

- no Python `async`/`await`
- simulator-owned concurrency
- explicit Python export registration
- SVX execution-context guard
- SvTypes independence

### 3.9 `tools`

Developer commands and helper scripts.

This directory owns:

- local build helpers
- simulator run wrappers
- code generation helpers
- packaging helpers

Tools should wrap repeatable workflows, not hide core build logic that belongs
in `pyproject.toml` or `CMakeLists.txt`.

### 3.10 `third_party`

Vendored or pinned third-party source, if needed.

Prefer external package managers where practical. Use this directory only when
the project needs source-level vendoring.

## 4. Split Repository Map

The split is complete. The SVX repository contains:

```text
python/svx/               public Python API and CLI
svx_runtime/              simulator-loadable C++ runtime
sv/                       SVX SystemVerilog package and DPI declarations
docs/, examples/, tests/  SVX-owned documentation and verification
```

The sibling or installed SvTypes dependency contains its Python package,
`svtypes_runtime`, and all SvTypes-specific documentation, examples, and tests.

## 5. Dependency Rules

The production layout should follow these dependency rules:

```text
svtypes              depends on no SVX runtime package
svtypes_runtime      depends on no SVX runtime package
python/svx           may depend on native SVX runtime bindings
svx_runtime          may embed CPython and call Python SVX internals
sv                   talks to svx_runtime only through DPI/VPI boundaries
examples             may depend on any public user-facing API
tests                may depend on internal APIs when needed
```

The most important rule is:

```text
SvTypes must remain independent.
SVX depends on versioned SvTypes, but SvTypes must not consume SVX.
```

## 6. Packaging Direction

The project is split into two repositories.

The `svtypes` repository packages:

```text
python/svtypes/
svtypes_runtime/
SvTypes docs/tests/examples
```

The `svx` repository packages:

```text
python/svx/
svx_runtime/
sv/
SVX docs/tests/examples
```

SVX declares a versioned dependency on SvTypes in `pyproject.toml`.

`CMakeLists.txt` should build the simulator-loadable SVX shared library from
`svx_runtime/`.

SystemVerilog files under `sv/` should be installable or copyable as simulator
include/package sources. SvTypes support files should come from the installed
SvTypes package.
