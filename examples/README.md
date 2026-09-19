# SVX Examples

[中文](README.zh-CN.md)

These examples are arranged by the workflow a verification engineer normally
adopts, rather than by the historical milestone in which a capability was
introduced. Start with the typed-bus example, then choose the focused example
for the boundary you need.

| Goal | Start here | What it demonstrates |
|---|---|---|
| Run one Python test from an SV testbench | [Basic bootstrap](milestone_1_basic) | `svx_init`, `svx_run_test`, display, and simulator-owned delay |
| Move transactions across the boundary | [Typed bus testbench](milestone_7_sv_typed_helpers) | SvTypes models, generated SV helpers, request/response and monitor channels |
| Introduce SVX into a maintained testbench | [Existing SV environment](milestone_5_existing_env) | Leave driving and monitoring in SV; move scenario and checking policy to Python |
| Use generated types in a build | [CLI workflow](milestone_6_cli_workflow) | `svx svtypes-gen` and CLI discovery commands |
| Derive an SV class in Python | [Cross-language inheritance](cross_language_inheritance) | Manifest validation, generated mirrors, SV-owned construction, and a timed Python override |
| Derive a Python class in SV | [Python-owned inheritance](python_owned_inheritance) | Python-initiated construction, SV factory registration, and cross-language `super()` |
| Inspect or temporarily alter a hierarchy path | [Hierarchical signal access](hierarchical_signal_access) | Predeclaration, startup validation, read/write, force/release, and four-state values |
| Use raw bytes instead of a typed model | [Payload channels](milestone_2_payload_channel) | Binary payload, peek, and nonblocking channel operations |
| Understand runtime behavior | [Fork/join](milestone_1_fork), [shared state](milestone_1_shared_state), and [error policy](milestone_1_error) | Simulator-backed process control, Python heap sharing, and uncaught-exception handling |

The `milestone_*` directory names are retained for source and regression
compatibility. They are not a recommended learning sequence.

## Learning Path

1. Read [Basic bootstrap](milestone_1_basic) to understand the runtime entry
   boundary and simulator-owned time.
2. Run [Typed bus testbench](milestone_7_sv_typed_helpers) to learn the
   default transaction path for a clocked SV environment.
3. Use [Existing SV environment](milestone_5_existing_env) or [CLI workflow]
   (milestone_6_cli_workflow) when integrating that path into a maintained
   project and its build.
4. Add [cross-language inheritance](cross_language_inheritance) or
   [Python-owned inheritance](python_owned_inheritance) only when a declared
   virtual-class boundary is the right extension mechanism.
5. Use [hierarchical signal access](hierarchical_signal_access) only for small,
   temporary setup, inspection, or fault injection.

## Capability Matrix

| SVX capability | Primary example | Important boundary |
|---|---|---|
| Runtime lifecycle: initialize, load, start, run a test, shutdown | [Basic bootstrap](milestone_1_basic) | SV owns simulation lifecycle and time |
| Delay, display, and process groups | [Fork/join](milestone_1_fork) | Python uses only simulator-backed primitives |
| Shared Python objects across simulator processes | [Shared Python state](milestone_1_shared_state) | Call stacks are isolated; object heap is shared |
| Fatal exception reporting | [Error policy](milestone_1_error) | Uncaught Python exceptions follow the configured SVX policy |
| Opaque binary transport | [Raw payload channels](milestone_2_payload_channel) | Use only when a typed SvTypes model is not appropriate |
| Checked typed transport and generated SV helpers | [Typed bus testbench](milestone_7_sv_typed_helpers) | SvTypes descriptors and bytes are the sole typed wire contract |
| Typed channel roles: request, response, monitor | [Typed bus testbench](milestone_7_sv_typed_helpers) | Keep timing, driving, and sampling in SV |
| Generated model and build-input discovery | [CLI workflow](milestone_6_cli_workflow) | Derive paths and generated output from `svx` CLI |
| Incremental adoption in an existing environment | [Existing SV environment](milestone_5_existing_env) | Replace narrow data boundaries, not the SV component structure |
| SV-owned class extended in Python | [Cross-language inheritance](cross_language_inheritance) | SV initiates construction; Python implements declared overrides |
| Python-owned class extended in SV | [Python-owned inheritance](python_owned_inheritance) | Python initiates construction; SV registers a factory |
| Targeted hierarchical read/write/force/release | [Hierarchical signal access](hierarchical_signal_access) | Every path is declared and validated before runtime readiness |

SvTypes randomization, coverage collection, and UCIS handling remain SvTypes
features. SVX transports explicitly prepared typed values; it does not choose
random values or implicitly sample coverage at a channel, inheritance, or
signal crossing.

## Recommended First Run

Read and generate the models in the typed-bus example first:

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx svtypes-gen \
  --module examples.milestone_7_sv_typed_helpers.tests.types \
  --channel-helpers \
  --out examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv
```

Then compile its `tb.sv`, SvTypes runtime SV package, `svx_pkg.sv`, and the
generated file through the target simulator's normal DPI flow. The CLI exposes
the installed paths with `svx sv-files`, `svx compile-flags`, and `svx libs`.

All examples keep time, clocks, signal driving, monitor sampling, and testbench
concurrency in SystemVerilog. Python owns test intent, typed data preparation,
and checking policy.
