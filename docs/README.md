# SVX Documentation

## Core Documents

- [RELEASE_0.1.0.md](RELEASE_0.1.0.md): supported compatibility contract,
  installation model, and release gates for SVX 0.1.0.
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
- [diagrams/](diagrams/): visual overview diagrams for SVX layers,
  concurrency, and typed channels.

SvTypes-specific milestone, binary-format, support-matrix, and object-graph
documentation lives in the external SvTypes repository.

## Architecture Details

Detailed architecture notes live in [architecture/](architecture/).

- [architecture/generated_wrapper_layering.md](architecture/generated_wrapper_layering.md):
  M6 generated-code and user-code layering guidance.
