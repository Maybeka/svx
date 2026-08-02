# SVX 0.1.0 Release Contract

## Scope

SVX 0.1.0 is the first source/runtime release of the split SVX repository. It
covers the public Python API in `svx`, the `svx_pkg` SystemVerilog services,
the simulator-loadable C++ runtime, the documented CLI, manifest-driven
cross-language inheritance, and the narrow hierarchical signal access API.

The version applies to SVX only. SvTypes is an external, independently
versioned dependency. The `0.1` version indicates that compatibility changes
may occur before SVX reaches a future `1.0.0` release.

## Compatibility

| Component | 0.1.0 contract |
|---|---|
| Python | 3.11 or newer |
| SvTypes | `>=0.1.0,<0.2.0` |
| Simulator | A SystemVerilog simulator with the DPI and VPI C interfaces used by SVX |
| Verilator | Unsupported until upstream provides resumable timing and blocking behavior across DPI-exported tasks |
| Icarus Verilog | Unsupported; its VPI extension model cannot provide the SVX DPI and cross-language class runtime |
| Native toolchain | CMake 3.20+, C++20 compiler, and Python development headers for the simulator Python ABI |

Validate each target toolchain with its local build and regression configuration
before using it for a release.

## Installation Model

The Python package supplies the `svx` API, CLI, and installed SV support files.
The simulator-loadable native runtime is built with CMake because it must match
the Python ABI used by the simulator process.

```sh
python -m pip install 'svtypes>=0.1.0,<0.2.0'
python -m pip install svx==0.1.0
cmake -S . -B build
cmake --build build -j2
```

For source development, use the editable sibling dependency:

```sh
PYTHONPATH=../svtypes/python python -m pip install -e .
```

Set `SVX_LIB_DIR` to the CMake output directory when `svx libs` cannot infer
it. Set `SVX_SHARE_DIR` only when SV support files are installed
outside the normal Python data scheme.

## Stable Boundaries

- SystemVerilog owns simulator time and scheduling; Python uses only explicit
  SVX primitives from an active SVX execution context.
- SvTypes is the only typed argument/result contract across the SVX boundary.
- Cross-language inheritance uses versioned manifests and generated adapters;
  arbitrary reflective SV method invocation is not part of this release.
- Hierarchical signal access accepts only predeclared whole packed objects and
  is intended for occasional temporary access.
- The signal VPI service is direct C VPI called through an ordinary SV DPI
  context. No VPI system task or VPI `-load` plugin is required.

## Release Gates

Before tagging `v0.1.0`, all of the following must pass from the release
candidate commit:

```sh
PYTHONPATH=python:../svtypes/python:. python -m pytest -q
cmake -S . -B .tmp/release-build
cmake --build .tmp/release-build -j2
python -m build
```

Run the maintained local simulator validation before a release. The package
build must be inspected to ensure it contains the Python package and SV support
files, but no generated simulator artifacts.

## Release Inputs

- A committed `CHANGELOG.md` entry for `0.1.0`.
- Apache-2.0 `LICENSE` file.
- Reviewed dependency range and SvTypes release availability.
- A clean worktree after the release verification commands.
- Annotated tag `v0.1.0` created from the verified commit.
