# SVX Documentation

## Core Documents

- [RELEASE_1.0.0.md](RELEASE_1.0.0.md): supported compatibility contract,
  installation model, and release gates for SVX 1.0.0.
- [SVX_1_0_REQUIRED_FEATURES.md](SVX_1_0_REQUIRED_FEATURES.md): proposed stable
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
- [SVX_API_REFERENCE.md](SVX_API_REFERENCE.md): stable Python, CLI, and
  SystemVerilog surface plus private runtime ABI boundaries.
- [diagrams/](diagrams/): visual overview diagrams for SVX layers,
  concurrency, and typed channels.

SvTypes-specific binary-format, support-matrix, and object-graph documentation
lives in the external SvTypes repository.

## Architecture Details

Detailed architecture notes live in [architecture/](architecture/).

- [architecture/generated_wrapper_layering.md](architecture/generated_wrapper_layering.md):
  generated-code and user-code layering guidance.
