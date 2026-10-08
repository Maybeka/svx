# SVX 1.0.0 Release Contract

## Scope

SVX 1.0.0 is the stable source/runtime release of the split SVX repository. It
covers the public Python API in `svx`, the `svx_pkg` SystemVerilog services,
the simulator-loadable C++ runtime, the documented CLI, manifest-driven
cross-language inheritance, and the narrow hierarchical signal access API.

The version applies to SVX only. SvTypes is an external, independently
versioned dependency. SVX 1.x preserves its documented stable Python,
SystemVerilog, manifest, generated-artifact, and runtime contracts.

The version label alone is not proof of complete conformance to every item in
the required-feature document. See its
[implementation conformance note](SVX_1_0_REQUIRED_FEATURES.md#implementation-conformance-note)
for known current gaps. Release qualification must cover those requirements,
not only the existing passing examples.

## Compatibility

| Component | 1.0.0 contract |
|---|---|
| Python | 3.11 or newer |
| SvTypes | `>=1.4.2,<2.0.0` |
| greenlet | `>=3.1,<4.0`, for internal synchronous constructor continuation |
| Simulator | A SystemVerilog simulator with the DPI and VPI C interfaces used by SVX |
| Required simulator behavior | SystemVerilog classes, DPI import/export, resumable calls through exported DPI tasks, and direct VPI object access |
| Native toolchain | CMake 3.20+, C++20 compiler, and Python development headers for the simulator Python ABI |

Validate each target toolchain with its local build and regression configuration
before using it for a release.
The SvTypes lower bound reflects the public TypeSpec normalization and identity
APIs used by declarations and manifests. Startup also checks that these APIs are
callable; matching major versions and wire capabilities alone are insufficient.
Startup additionally requires the public `SvObject.codec_template()` API.
Constructor continuation keeps the original Python call stack and evaluated
`super().__init__()` arguments. It does not introduce an asynchronous user API.
SvTypes `1.4.2` includes the public codec and external-field fixes required by
SVX. The old `1.4.1` package is not sufficient for this contract.
The dependency qualification must exercise declaration refresh for source
Mirrors, public associative codec queries, nested SV rendering contexts,
preservation of explicit request/response fields, JSON-safe enum identities,
and owner-bound deep field access. A candidate wheel built from development sources can qualify those
operations in an isolated environment, but does not qualify a previously
published wheel carrying the same version number. Record the exact candidate
inputs and repeat the checks against the released dependency before release.
The minimum version is not a substitute for qualification of the exact package
inputs and the supported scenarios described in the conformance note.

## Installation Model

The Python package supplies the `svx` API, CLI, and installed SV support files.
The simulator-loadable native runtime is built with CMake because it must match
the Python ABI used by the simulator process.

```sh
python -m pip install 'svtypes>=1.4.2,<2.0.0'
python -m pip install svx==1.0.0
cmake -S "$(svx native-source)" -B build \
  -DPython3_EXECUTABLE="$(python -c 'import sys; print(sys.executable)')" \
  -DSVX_SIMULATOR_INCLUDE_DIR=/path/to/simulator/include \
  -DSVX_REQUIRE_DIRECT_VPI=ON
cmake --build build -j2
```

Use this interpreter for the simulator-hosted Python runtime as well. When
changing interpreters, configure a fresh build directory rather than relying on
an existing CMake cache. A successful native build alone does not prove simulator
loading: DPI symbols supplied by the simulator are required at runtime.

The default CMake configuration without `vpi_user.h` builds the core runtime
with a signal-service stub for non-simulator development only. It does not
provide hierarchical signal access and is not a release-qualified runtime.

For source development, use the editable sibling dependency:

```sh
python -m pip install -e ../svtypes
python -m pip install -e .
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

Before tagging `v1.0.0`, all of the following must pass from the release
candidate commit:

```sh
PYTHONPATH=python:../svtypes/python:. python -m pytest --runxfail -q
export SVX_SIMULATOR_INCLUDE_DIR=/path/to/simulator/include
cmake -S . -B .tmp/release-build \
  -DPython3_EXECUTABLE="$(python -c 'import sys; print(sys.executable)')" \
  -DSVX_SIMULATOR_INCLUDE_DIR="$SVX_SIMULATOR_INCLUDE_DIR" \
  -DSVX_REQUIRE_DIRECT_VPI=ON
cmake --build .tmp/release-build -j2
cmake -S . -B .tmp/release-sanitizer \
  -DPython3_EXECUTABLE="$(python -c 'import sys; print(sys.executable)')" \
  -DSVX_SIMULATOR_INCLUDE_DIR="$SVX_SIMULATOR_INCLUDE_DIR" \
  -DSVX_REQUIRE_DIRECT_VPI=ON -DSVX_ENABLE_SANITIZERS=ON
cmake --build .tmp/release-sanitizer -j2
python -m build
```

Use the actual target headers in place of the placeholder. Both native build
gates must fail if direct VPI support is unavailable; a core-only stub build is
useful for development but cannot satisfy these release gates. The interpreter
selected above must match the simulator-hosted runtime.
The Python release gate runs known-failure tests normally with `--runxfail`;
an expected-failure marker is not release acceptance. Resolve the underlying
failures rather than deleting scenarios or weakening their assertions.

Run the maintained local simulator validation before a release. The package
build must be inspected to ensure it contains the Python package and SV support
files, but no generated simulator artifacts. Run the sanitizer-built runtime
through the qualified simulator regression where the toolchain supports it.

## Release Inputs

- A committed `CHANGELOG.md` entry for `1.0.0`.
- Apache-2.0 `LICENSE` file.
- Reviewed dependency range and SvTypes release availability.
- A clean worktree after the release verification commands.
- Annotated tag `v1.0.0` created from the verified commit.
