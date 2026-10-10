# SVX Documentation

## Core Documents

- [RELEASE_1.0.0.md](RELEASE_1.0.0.md): supported compatibility contract,
  installation model, and release gates for SVX 1.0.0.
- [SVX_1_0_REQUIRED_FEATURES.md](SVX_1_0_REQUIRED_FEATURES.md): stable
  feature contract, SvTypes prerequisites, implementation sequence, and release
  qualification gates for SVX 1.0.0.
- [SVX_SPEC.md](SVX_SPEC.md): project scope, architecture, concurrency model,
  execution context, export model, process model, and non-goals.
- [SVX_PROJECT_LAYOUT.md](SVX_PROJECT_LAYOUT.md): intended production project
  structure and migration map.
- [decisions/0001-svtypes-as-versioned-external-dependency.md](decisions/0001-svtypes-as-versioned-external-dependency.md):
  accepted decision to split SVX and SvTypes into two repositories, with SVX
  depending on versioned SvTypes.
- [SVX_USER_MANUAL.md](SVX_USER_MANUAL.md): active user manual covering
  adoption, SvTypes generation, Python test startup, typed channels, generated
  SV helpers, lifecycle rules, debug flow, cross-language inheritance, signal
  access, and anti-patterns.
- [SVX_COOKBOOK.zh-CN.md](SVX_COOKBOOK.zh-CN.md): a standalone, step-by-step
  Chinese cookbook with a five-step Register Lab project route, a capability
  index and focused chapters on runtime, channels, inheritance and signals.
- [../examples/register_lab/README.md](../examples/register_lab/README.md):
  one runnable register-peripheral project, with bilingual instructions,
  generation/check commands and positive/negative result criteria.
- [SVX_SVTYPES_CORE_CONCEPTS.zh-CN.md](SVX_SVTYPES_CORE_CONCEPTS.zh-CN.md):
  Chinese concept guide that connects the architecture diagrams to runnable
  examples for SvTypes data contracts, SVX primitives, typed channels, signals,
  and both cross-language inheritance directions.
- [../examples/RUNNING_EXAMPLES.zh-CN.md](../examples/RUNNING_EXAMPLES.zh-CN.md):
  shared operational setup, build-input, runtime-loading, and result criteria
  for every published example.
- [SVX_API_REFERENCE.md](SVX_API_REFERENCE.md): stable Python, CLI, and
  SystemVerilog surface plus private runtime ABI boundaries.
- [CROSS_LANGUAGE_HANDLE_ADAPTERS.md](CROSS_LANGUAGE_HANDLE_ADAPTERS.md):
  declared `RemoteRef` transport for arbitrary SV class handles and generated
  restricted virtual-interface views.
- [CROSS_LANGUAGE_INHERITANCE_LINEAGE.md](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md):
  full inheritance design, target residency, construction, member semantics,
  and explicit distinctions between implemented interfaces and planned ones.
- [diagrams/](diagrams/): visual overview diagrams for SVX layers,
  concurrency, and typed channels.

SvTypes-specific binary-format, support-matrix, and object-graph documentation
lives in the external SvTypes repository.

## Architecture Details

Detailed architecture notes live in [architecture/](architecture/).
The binding, cross-layer API, and type-taxonomy notes retain explicitly marked
historical sketches; use the API reference and current source declarations for
actual build/API contracts.

- [architecture/generated_wrapper_layering.md](architecture/generated_wrapper_layering.md):
  generated-code and user-code layering guidance.
