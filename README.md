# SVX

SVX 0.1.0 is a simulator-hosted Python verification runtime for
SystemVerilog. It lets SystemVerilog testbenches run explicit Python tests and
services while preserving the simulator as the owner of time, event scheduling,
and simulator-visible concurrency.

## Supported Contract

- Python: 3.11 or newer.
- SvTypes: `>=0.1.0,<0.2.0`.
- Simulator: a SystemVerilog simulator with the DPI and VPI C interfaces used
  by SVX.
- Runtime model: SystemVerilog owns clocks, resets, drivers, monitors, UVM
  phases, timing, and process scheduling. Python owns test intent, typed data,
  checking policy, and high-level orchestration.

SVX does not expose Python `async`/`await` as a simulation model. Python
threads and other host-native concurrency must not call simulator-facing SVX
APIs.

The repository is split from SvTypes. SVX owns `python/svx`, `svx_runtime`,
`sv`, and its own examples, tests, and documentation. SvTypes owns the
`svtypes` Python package and `svtypes_runtime`; during development use the
sibling repository at `../svtypes` as the editable dependency.

## Capabilities

- Simulator-started Python tests, delay, display, and simulator-owned
  fork/join services.
- Binary SvTypes payload channels and generated typed SV helpers.
- Manifest-driven cross-language class inheritance with generated mirrors and
  proxies, SvTypes arguments/results, and callback-cycle detection.
- Small-scale, predeclared hierarchical signal read, write, force, and release
  through a direct VPI C service invoked from an SV DPI context.

Hierarchical signal access is intentionally for temporary, targeted operations
such as setup checks and fault injection. It is not a replacement for SV
drivers, monitors, or bulk signal databases.

## Build And Test

Create a development environment with the sibling SvTypes package visible:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pytest
PYTHONPATH=../svtypes/python python -m pip install -e .
```

Build the simulator-loadable runtime:

```sh
cmake -S . -B build
cmake --build build -j2
```

Run the Python and native build checks:

```sh
PYTHONPATH=python:../svtypes/python:. .venv/bin/python -m pytest -q
cmake --build build -j2
```

The simulator-neutral SV and Python integration sources are in
`tests/integration/`. Their environment-specific execution harnesses are
maintained locally because they depend on licensed simulator installations and
internal execution environments.

For a non-default CMake build location, expose the simulator library to the
CLI with `SVX_LIB_DIR=/path/to/build`. For an installed SV support directory,
set `SVX_SHARE_DIR=/path/to/share/svx/sv` when automatic discovery is not
available.

## Simulator Integration

The CLI prints the SV files and simulator flags needed by a build script:

```sh
svx share
svx sv-files
SVX_LIB_DIR="$PWD/build" svx libs
svx compile-flags
```

The M14 direct-VPI C source is compiled directly into the simulator invocation
for designs that enable hierarchical signal access. It does not use a VPI
system task or a `-load` plugin.

## Documentation

- [User manual](docs/SVX_USER_MANUAL.md)
- [0.1.0 release contract and gates](docs/RELEASE_0.1.0.md)
- [Project specification](docs/SVX_SPEC.md)
- [SvTypes dependency decision](docs/decisions/0001-svtypes-as-versioned-external-dependency.md)
