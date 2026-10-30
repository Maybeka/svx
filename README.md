# SVX

SVX 1.0.0 is a simulator-hosted Python verification runtime for
SystemVerilog. It lets SystemVerilog testbenches run explicit Python tests and
services while preserving the simulator as the owner of time, event scheduling,
and simulator-visible concurrency.

## Supported Contract

- Python: 3.11 or newer.
- SvTypes: `>=1.4.2,<2.0.0`.
- Simulator: a SystemVerilog simulator with the DPI and VPI C interfaces used
  by SVX, including resumable calls through exported DPI tasks.
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

The integrated source path supports qualified Python-root alternating chains
and natural per-ancestor constructor argument routing. Supported inheritance
shapes and boundaries are specified in [Cross-Language Lineage](docs/CROSS_LANGUAGE_INHERITANCE_LINEAGE.md).

Hierarchical signal access is intentionally for temporary, targeted operations
such as setup checks and fault injection. It is not a replacement for SV
drivers, monitors, or bulk signal databases.

## Build And Test

Use [Running Examples](examples/RUNNING_EXAMPLES.md) for the source-checkout
environment, editable SvTypes dependency, native build and simulator loading.
Use the [release installation guide](docs/RELEASE_1.0.0.md#installation-model)
for an installed package. Keep the same Python ABI throughout.

Run the source tests after preparing that environment:

```sh
PYTHONPATH=python:../svtypes/python:. .venv/bin/python -m pytest -q
```

The SV and Python integration regression sources are in `tests/integration/`.

## Simulator Integration

The CLI prints the SV files and simulator flags needed by a build script:

```sh
svx share
svx native-source
svx sv-files
SVX_LIB_DIR="$PWD/build" svx libs
svx compile-flags
```

The direct VPI service is compiled into `libsvx` for designs that enable
hierarchical signal access. It does not use a VPI system task or a separately
loaded plugin.

## Documentation

- [Examples and adoption paths](examples/README.md)
- [Step-by-step Cookbook (Chinese)](docs/SVX_COOKBOOK.zh-CN.md)
- [Cookbook website and local preview](docs/site/README.md)
- [Real Project Migration: OpenTitan UART](examples/opentitan_uart/README.md)
- [Documentation map](docs/README.md)
- [User manual](docs/SVX_USER_MANUAL.md)
- [API reference](docs/SVX_API_REFERENCE.md)
- [1.0.0 release contract and gates](docs/RELEASE_1.0.0.md)
- [Project specification](docs/SVX_SPEC.md)
- [SvTypes dependency decision](docs/decisions/0001-svtypes-as-versioned-external-dependency.md)
