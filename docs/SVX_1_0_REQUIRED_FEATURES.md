# SVX Feature Contract Index

This retained filename is a navigation index, not a second release specification
or an unfinished implementation plan. Version/dependency requirements and release
gates have one owner: [Release Contract](RELEASE_1.0.0.md). API names and accepted
metadata have one owner: [API Reference](SVX_API_REFERENCE.md).

### Implementation Conformance Note

The current public generation path supports the documented SV-root and Python-root
alternating controls, natural constructor continuation and declared field storage.
It does not imply arbitrary source forms, inheritance graphs or reflective object
access. Exact executable boundaries and restrictions are maintained in
[Lineage](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md), not in a parallel progress list.
Project-specific qualification results remain with their examples. The temporary
UVMX source and its preparation guide do not turn SVX into a Python UVM class library.

## Find The Current Contract

| Subject | Authority |
|---|---|
| Ownership, scheduling and non-goals | [Project specification](SVX_SPEC.md) |
| Exports, timing, processes, channels and lifecycle | [Public API](SVX_API_REFERENCE.md#stable-python-api) |
| Signal subscriptions and waveform operations | [API reference](SVX_API_REFERENCE.md) |
| Inheritance, constructors, fields and dispatch | [Lineage](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md) |
| Native class handles and restricted VIF views | [Handle adapters](CROSS_LANGUAGE_HANDLE_ADAPTERS.md) |
| Manifest keys and API classification | [Manifest inventory](SVX_API_REFERENCE.md#manifest-field-inventory) |
| Discovery, stale records and output ownership | [Generation workflow](SVX_GENERATION_WORKFLOW.md) |
| Existing filelists and compiler arguments | [Build input import](SVX_BUILD_INPUTS.md) |
| Installation, versions and release validation | [Release contract](RELEASE_1.0.0.md) |
| UVMX source preparation and native run_test | [UVMX preparation](UVMX_GETTING_STARTED.md) |

Historical stage-by-stage hardening requirements are not current user instructions.
Use Git history for previous decisions and local planning notes for future work.
