# SVX Repository Layout

This is the current source map, not a proposed target tree. Architectural
ownership is defined in [the specification](SVX_SPEC.md); build and release
rules are defined in [shared setup](../examples/RUNNING_EXAMPLES.md) and
[the release contract](RELEASE_1.0.0.md).

| Location | Responsibility |
|---|---|
| python/svx | Public Python API, declarations, parsing, generation and runtime adapters |
| sv | Simulator-side package, timing, processes, channels and inheritance services |
| svx_runtime | CPython embedding, native contexts, DPI routing, payloads and direct VPI services |
| examples | Runnable application sources, project-specific build recipes and acceptance markers |
| tests | Python/native/HDL regression sources |
| docs | Current guides, contracts, reference material and editable diagrams |
| docs/site | Static website renderer and visual presentation, built from the current documents |
| incubator/uvmx | Temporary source-only UVM adapter, excluded from SVX distributions |
| CMakeLists.txt | Native runtime build and support-file installation |
| pyproject.toml / MANIFEST.in | Python dependencies and package contents |

SvTypes is an external repository and versioned dependency; its Python package,
runtime support, codec semantics and type implementation do not live in SVX.
Source development uses ../svtypes as an editable dependency. Installed consumers
locate SVX support through its CLI rather than assuming checkout-relative paths.

Generated build trees, simulator executables, caches, local runner scripts,
milestones and review notes are not public source structure. Generated application
files stay in their project's designated output root; they are not edited by hand.
