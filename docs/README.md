# SVX Documentation

## Choose A Route

| Need | Start here |
|---|---|
| Learn by doing | [Chinese Cookbook](SVX_COOKBOOK.zh-CN.md) or [its searchable website](site/README.md) |
| Prepare a source checkout | [Running Examples](../examples/RUNNING_EXAMPLES.md) / [中文](../examples/RUNNING_EXAMPLES.zh-CN.md) |
| Install a release | [Release installation](RELEASE_1.0.0.md#installation-model) |
| Migrate an existing environment | [OpenTitan UART](../examples/opentitan_uart/README.md) |
| Try a smaller complete project | [Register Lab](../examples/register_lab/README.md) |
| Add Python UVM tests | [UVMX preparation](UVMX_GETTING_STARTED.md) / [中文](UVMX_GETTING_STARTED.zh-CN.md) |
| Find a focused example | [Examples index](../examples/README.md) |
| Read diagrams | [Chinese architecture reading guide](SVX_SVTYPES_CORE_CONCEPTS.zh-CN.md) |

## Authoritative References

Each topic has one current owner. The Cookbook teaches a route through these
references; it is not another API specification. Translations describe the same
topic, not separate contracts. Example instructions own project-specific inputs
and expected results, not general API rules.

| Topic | Current owner |
|---|---|
| Goals, scheduling and repository responsibilities | [Specification](SVX_SPEC.md) |
| Public Python, SV and CLI surface; manifest fields | [API Reference](SVX_API_REFERENCE.md) |
| Discovery, generation, freshness and output ownership | [Generation And Incremental Builds](SVX_GENERATION_WORKFLOW.md) |
| Original filelists, macros, includes and lazy libraries | [Build Inputs](SVX_BUILD_INPUTS.md) |
| Inheritance, construction, dispatch and field residency | [Cross-Language Lineage](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md) |
| External class handles and restricted virtual interfaces | [Handle Adapters](CROSS_LANGUAGE_HANDLE_ADAPTERS.md) |
| Installation, compatibility and release qualification | [Release Contract](RELEASE_1.0.0.md) |
| UVMX preparation and first test | [Getting Started](UVMX_GETTING_STARTED.md) / [中文](UVMX_GETTING_STARTED.zh-CN.md) |
| Current source locations | [Project Layout](SVX_PROJECT_LAYOUT.md) |

[User Manual](SVX_USER_MANUAL.md) retains its familiar section links as a reading
map. [1.0 Feature Map](SVX_1_0_REQUIRED_FEATURES.md) routes release requirements
to the owners above; neither maintains another implementation plan.
SvTypes owns its own types, codecs, storage and format documentation.

## Runtime Internals

These notes explain implementation mechanisms, not alternative public APIs:

- [Execution contexts](architecture/execution_context.md)
- [CPython state isolation](architecture/gil_management.md)
- [Simulator process scheduling](architecture/concurrency_design.md)
- [Time conversion](architecture/delay_precision.md)
- [Export registration](architecture/export_model.md)
- [Binding and scope](architecture/binding_mechanism.md)
- [Native ABI checks](architecture/cross_layer_api.md)
- [Exception reporting](architecture/error_policy.md)
- [Generated/user code layering](architecture/generated_wrapper_layering.md)

The [SvTypes dependency decision](decisions/0001-svtypes-as-versioned-external-dependency.md)
records why the repositories are separate. The
[architecture reading guide](SVX_SVTYPES_CORE_CONCEPTS.zh-CN.md) links editable
source diagrams; additional overviews live in [diagrams/](diagrams/).
