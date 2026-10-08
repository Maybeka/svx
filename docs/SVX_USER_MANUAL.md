# SVX User Manual

Status: active user guide for SVX 1.0.0.

This manual explains how to use SVX in an existing SystemVerilog verification
environment.

SVX is not a replacement simulator scheduler and it is not a new component
framework. The intended user is a SystemVerilog verification engineer who wants
to keep timing-aware verification structure in SystemVerilog while moving
higher-level test intent, data modeling, generation, and checking into Python.

## 1. Core Usage Model

Use this split as the default design rule:

- SystemVerilog owns clocks, resets, interfaces, signal driving, monitor
  sampling, agents, sequencers, UVM phases, process scheduling, and simulator
  integration.
- Python owns tests, sequences, transaction construction, configuration data,
  expected data, scoreboarding policy, and reusable scenario logic.
- SVX connects the two through explicit exported Python entry points,
  simulator-owned primitives, and binary SvTypes channels.

Python `async`/`await` is not part of the SVX simulation model. Python threads,
subprocesses, or host-native async code may be used only for host-side work
that does not call SVX primitive APIs.

## 2. First Adoption Pattern

Start with a Python-controlled test around an existing SV or UVM environment.

1. Keep the existing SV testbench structure.
2. Add `svx_init()` and one simulator-started Python entry point.
3. Keep the existing SV driver and monitor timing code.
4. Replace only the sequence-item source or checker sink with SVX channels.
5. Let Python generate transactions and check responses or observations.

This proves the SVX boundary without moving signal-level behavior out of
SystemVerilog.

For an example, see
[examples/milestone_5_existing_env](../examples/milestone_5_existing_env).

## 3. Define SvTypes Models

Define transaction, response, observation, and configuration objects in Python.
Group them by protocol or subsystem.

```text
verification/
  svtypes_models/
    apb_types.py
  sv/
    generated/
      apb_types.sv
  tests/
    apb_smoke.py
```

Example model:

```python
from svtypes import Bit, Int, SvObject, get_package, svobj

pkg = get_package("apb_types")

@svobj(registry=pkg)
class ApbReq(SvObject):
    id = Int()
    addr = Bit(32)
    data = Bit(32)
    write = Bit(1)
```

SvTypes is independent from the SVX runtime. It is the data contract used by
Python, generated SystemVerilog, and generated C++ support code.

Constrained randomization, coverage collection, and UCIS export remain SvTypes
operations. Randomize objects before sending them and sample coverage at the
explicit verification point chosen by the testbench; SVX transports the value
without implicitly randomizing or sampling it.

## 4. Generate SystemVerilog Types

Generate matching SV classes from the Python model module:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module verification.svtypes_models.apb_types \
  --out verification/sv/generated/apb_types.sv
```

Generate only selected declarations when needed:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module verification.svtypes_models.apb_types \
  --types ApbReq,ApbRsp,ApbObs \
  --out verification/sv/generated/apb_types.sv
```

Generate SystemVerilog typed-channel helpers at the same time:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module verification.svtypes_models.apb_types \
  --types ApbReq,ApbRsp,ApbObs \
  --channel-helpers \
  --out verification/sv/generated/apb_types_and_channels.sv
```

Generated files should be deterministic. For integration projects, either
commit generated SV files or regenerate them as an explicit build step.

## 5. Inspect Build Inputs

Use the SVX CLI to discover package files, include paths, and simulator flags.

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx share
PYTHONPATH=python:../svtypes/python:. python3 -m svx sv-files
PYTHONPATH=python:../svtypes/python:. python3 -m svx compile-flags
PYTHONPATH=python:../svtypes/python:. python3 -m svx libs
```

These commands are intended to make project build scripts depend on SVX tooling
instead of hard-coded local paths.

## 6. Include SVX in SystemVerilog

Include the SvTypes runtime, SVX package, and generated model file in the SV
testbench or a project package.

```systemverilog
`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "verification/sv/generated/apb_types_and_channels.sv"

module tb;
  import svx_pkg::*;
endmodule
```

SystemVerilog remains responsible for timed behavior. Drivers should consume
request objects, drive interfaces, and publish response objects. Monitors
should sample interfaces and publish observations.

## 7. Start Python From SystemVerilog

Use `svx_run_test(module_name, function_name)` when you want a single
registered Python test entry point.

```systemverilog
initial begin
  svx_init();

  fork : background_services
    begin
      existing_driver();
    end
    begin
      existing_monitor();
    end
  join_none
  svx_run_test("verification.tests.apb_smoke", "test_apb_smoke");
  // The test has completed; stop the SV-only background services.
  disable background_services;
  svx_shutdown();
  $finish;
end
```

`svx_run_test` is a convenience wrapper over module loading and exported
function startup. The Python function must still be registered explicitly.

## 8. Write Python Tests

Use `@svx.test` for simulator-started tests. Use role helpers for common
request/response and monitor channel patterns.

```python
import svx
from verification.svtypes_models.apb_types import ApbObs, ApbReq, ApbRsp

@svx.test
def test_apb_smoke():
    bus = svx.reqrsp_channel("env.apb0", ApbReq, ApbRsp)
    mon = svx.mon_channel("env.apb0.mon", ApbObs)

    req = ApbReq()
    req.id.value = 1
    req.addr.value = 0x1000
    req.data.value = 0x12345678
    req.write.value = 1

    rsp = bus.request(req)
    assert rsp.id.value == 1

    obs = mon.get()
    assert obs.addr.value == req.addr.value
```

Uncaught Python exceptions are reported through the configured SVX exception
policy. The default policy is fatal.

Use `pytest` for pure-Python model, generator, and helper tests that do not
need a simulator.

## 9. Use Typed Helpers in SV

Generated typed-channel helpers remove manual payload metadata checks and
`pack`/`unpack` boilerplate from drivers and monitors.

```systemverilog
ApbReq req;
ApbRsp rsp;
ApbObs obs;

svx_get_ApbReq("env.apb0.req", req);

// Drive timed SV behavior here.

rsp = new();
svx_put_ApbRsp("env.apb0.rsp", rsp);

obs = new();
svx_put_ApbObs("env.apb0.mon", obs);
```

For nonblocking empty-channel checks, use the task-form `try_get` helper:

```systemverilog
bit ok;
ApbReq req;

svx_try_get_ApbReq("env.apb0.req", ok, req);
if (!ok) begin
  // Channel was empty.
end
```

Generated helper names are type-driven:

```text
svx_get_<TypeName>
svx_put_<TypeName>
svx_peek_<TypeName>
svx_try_get_<TypeName>
svx_try_put_<TypeName>
```

Generated helpers validate:

- payload kind is `svtypes`
- content type is `application/x-svtypes`
- payload type metadata matches the expected SvTypes class
- unpack consumed the entire byte stream

Fatal diagnostics include helper name, channel name, expected type, and actual
metadata when available.

## 10. Channel Naming

Use stable, hierarchical names:

```text
<env>.<agent_or_block>.<role>
```

Recommended roles:

- `req`: request or sequence item
- `rsp`: response or completion item
- `mon`: monitor observation
- `config`: configuration object
- `expected`: expected scoreboard item
- `actual`: actual scoreboard item
- `control`: explicit test-control message

Examples:

```text
env.bus0.req
env.bus0.rsp
env.bus0.mon
```

Avoid language-specific names such as `python_to_sv`, global names such as
`req`, and reusing one channel for unrelated object types.

## 11. Existing SV Driver Pattern

An existing SV driver can keep its timing and interface code. Only its item
source changes.

```systemverilog
task automatic existing_style_driver();
  Req tx;
  forever begin
    svx_get_Req("env.bus0.req", tx);
    drive_interface(tx);
    svx_put_Rsp("env.bus0.rsp", rsp);
  end
endtask
```

Do not move clock waits, handshakes, or interface assignments into Python.

## 12. Existing SV Monitor Pattern

An existing SV monitor can keep sampling in SV and publish typed observations
to Python.

```systemverilog
task automatic existing_style_monitor();
  Obs obs;
  forever begin
    sample_interface(obs);
    svx_put_Obs("env.bus0.mon", obs);
  end
endtask
```

Python can consume `env.<agent>.mon` and compare observations against expected
data.

## 13. Existing UVM Environment Pattern

For UVM environments, keep the UVM component hierarchy and phase ownership in
SystemVerilog. SVX should enter through narrow typed-channel boundaries instead
of replacing `uvm_driver`, `uvm_monitor`, sequencer arbitration, config-db, or
factory behavior.

Recommended first adoption points:

- a test or environment phase calls `svx_init()` and starts one Python entry
  point
- an existing driver retrieves SvTypes sequence items from a named `req`
  channel instead of a legacy sequence source
- an existing monitor publishes generated SvTypes observation objects to a
  named `mon` channel
- Python owns scenario construction and high-level checking
- SV translates Python config objects into existing UVM config objects when
  that avoids broad testbench churn

Keep `raise_objection`, `drop_objection`, interface timing, sequencer policy,
and monitor sampling in SV. A separate integration layer may build stronger
UVM abstractions on these SVX boundaries without changing their ownership.

## 14. Object Lifecycle Rules

SVX owns the codec session used by its typed channel and inheritance services.
Do not close it or clear its registries while SVX is ready. A default SvTypes
registry reset is not a reset of SVX's active codec session. At scenario
boundaries within one simulation:

- drain channels or use unique named channels
- do not persist SvTypes graph IDs or SVX foreign-object IDs across simulation
  runs
- document any intentional object sharing scope

At simulator teardown, stop/join active work and call `svx_shutdown()` to release
SVX-owned resources. Shutdown is terminal; a fresh simulator process establishes
the next session. Applications using independent SvTypes codecs manage those
separate sessions themselves, without clearing the active SVX session.
Shutdown first cancels and joins tracked children; it cannot finish until a non-cooperative user SV task returns.
Current shutdown clears SVX registries and its codec session but does not finalize CPython;
the embedded interpreter is retained until simulator exit. Do not use interpreter
exit hooks or garbage collection as a substitute for explicit simulation-resource
cleanup. Retaining the interpreter until process exit is intentional, not a
missing interpreter-finalization feature. The shutdown entry point does not
promise comprehensive leak reporting or forced unwinding of arbitrary user tasks.

For object graphs, use the current default policy:

- update compatible registered objects in place
- rebind fields to the selected registry object
- fail on type mismatch

## 15. Compile and Run

Compile the SVX package files, the SvTypes runtime, generated type helpers,
and the project testbench using the target simulator's normal DPI integration
mechanism. Build the C++ runtime for the Python ABI used by the simulator
process, then make its library path available to the simulator.

Project build scripts should derive SVX include paths, SV file lists, and
library paths from the CLI commands in section 5 instead of hard-coding local
paths.

## 16. Reference Examples

Start with [the examples index](../examples/README.md). The recommended first
end-to-end path is the typed bus testbench, followed by the focused
cross-language inheritance and hierarchical signal-access examples as needed.

Prepare the existing-environment example:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module examples.milestone_5_existing_env.tests.types \
  --channel-helpers \
  --out examples/milestone_5_existing_env/generated_types.sv

```

Prepare the CLI workflow example:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module examples.milestone_6_cli_workflow.tests.types \
  --channel-helpers \
  --out examples/milestone_6_cli_workflow/generated/types.sv

```

Prepare the typed-bus example:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module examples.milestone_7_sv_typed_helpers.tests.types \
  --channel-helpers \
  --out examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv

```

Each example supplies SystemVerilog and Python sources for integration with
the project's target simulator configuration.

## 17. Cross-Language Inheritance

Cross-language inheritance is generated from an SVX inheritance manifest. The
manifest is the sole inheritance metadata contract. The runtime executes
generated adapters and validates their compatibility artifact manifest; it does
not execute a raw inheritance manifest. Every value binding records a canonical
SvTypes type identity plus SvTypes-derived SV declaration and packer metadata;
SVX transports only object/method metadata and opaque SvTypes bytes.

The manifest may be authored directly or normalized from declaration front
ends. A Python-owned class uses explicit decorators:

```python
from svtypes import Int
from svx import Function, inheritance_class, inheritance_method

@inheritance_class(canonical_id="py://checks/BaseMonitor")
class BaseMonitor:
    @inheritance_method
    def sample(self, sample_id: Int) -> Function[Int]:
        return sample_id
```

An unwrapped concrete SvTypes type `T` and `Input[T]` mean `input`; `Output[T]` and
`Inout[T]` put their respective direction in the Python prototype. Each
parameter is independent: a direction marker does not affect later parameters.
`-> Task`, `-> Function`, and
`-> Function[T]` select a task, a void function, and a function with a SvTypes
result respectively. They are declaration metadata, not Python runtime value
types. `Output[T]` and `Inout[T]` remain in their declared position and receive
mutable `svx.Output` / `svx.Inout` carriers; access their `.value` and return
only the ordinary function result. Generated SvTypes records are private. The
older `parameters=`, `return_type=`, and `timing=` form remains available but
cannot be mixed with an annotation for the same fact. This rule does not apply
to `@svx.export` or `@svx.test`, whose entry is always task-shaped.

The markers remain friendly to static tooling: `Input[T]` is checked as `T`,
`Function[T]` as `T`, and `Task` as `None`; `Output[T]` and `Inout[T]` expose a
typed `.value: T` carrier.

SV-owned declarations use a versioned JSON sidecar with schema URI
`https://svx.dev/schema/sv-inheritance-declarations/v1`. Its `classes` entries
use the same class shape as the manifest and must all declare `language: "sv"`.
Normalize either or both sources before mirror generation:

```sh
python -m svx inheritance-manifest \
  --python-module checks.base_monitor \
  --sv-declarations sv-inheritance-declarations.json \
  --out inheritance.json
```

Use `--check` to verify the normalized manifest without rewriting it. Both
front ends pass through the same strict v2 manifest parser; they are not
additional runtime contracts.
Discovery fingerprints explicitly listed SV declaration files, selected SV source
dependencies and file-backed Python entry modules before importing the entries.
Repeat `--python-source FILE` to include additional declaration or codec helper
files in this stability check and output-overwrite protection. This option does
not import the listed files; normal entry-module imports still run. Missing
explicit files fail before entry import. These fingerprints protect this command
invocation and are persisted in the sibling `<manifest-name>.svx-discovery.json`
record, bound to the normalized manifest contract. Ordinary user source imports
compiled during discovery are recorded automatically; they need not be repeated
as generation inputs. Keep the manifest and its source record together.
Discovery prepares both changed files before publishing either. If publication
raises an error and recovery succeeds, it restores existing files (including
their timestamps and permissions) and removes newly published files. Retry the
discovery command after resolving the error. If recovery also fails, the error
identifies saved originals; preserve them and reconcile the pair before checking
or generating again. Do not delete the output directory as a recovery shortcut.
This protection applies to the discovery pair, not all generated artifacts.
It is not crash-atomic and does not lock competing writers: use one writer per
output pair. Readers can temporarily encounter incomplete evidence during
publication and must reject it rather than use a partially updated contract.
It revalidates them before returning a check result or writing the normalized
manifest. Detected changes or disappearance abort discovery and preserve the
existing output. Python entry modules are still imported and may have side
effects. Newly loaded ordinary source dependencies imported by those entries or
during declaration/codec materialization are checked automatically for this
invocation and passed to generation through the source record. Use a
fresh command process to discover edited Python declarations: this guard does
not reload modules cached by a long-lived Python caller or create an immutable
source snapshot. A cached entry is accepted only with current prior discovery
evidence; otherwise use a fresh process. Custom importers and unaudited cached
dependencies do not acquire complete provenance merely by appearing in a module.
Ordinary imports during discovery and generation also check cached dependencies, including
`from`/relative imports and `importlib.import_module()`. This includes lazy codec
materialization after declaration modules finish executing.
A cached helper without current validated discovery or generation evidence is rejected before
publication, even if its current file is unchanged: a current hash does not prove
which bytes created cached definitions. Use a fresh command process rather than
adding `--python-source` to certify old cached code. Valid prior evidence permits
unchanged cached helpers to be reused without rewriting matching output.
This import check is not complete tracking of existing object references or
custom loaders. Explicit source paths alone do not certify cached definitions.
Discovery also records ordinary file-backed user module names and selected source
paths. Validation resolves their current filesystem selection without executing
package initializers; a newly preferred same-name module invalidates old evidence.
Older Python-entry records without this inventory require rediscovery. Check with
the application's current import paths. Custom importers, runtime package-path
mutations are not certified by this mapping. Participating namespace ancestors
and their ordered directory locations are also recorded: adding a package
initializer or changing these locations invalidates old evidence even when the
child source path is unchanged. Rediscover older incomplete namespace records;
keep the ordered discovery check rather than using generation checking alone.
For newly imported ordinary filesystem entry modules, their parent packages,
imports whose source path is explicitly listed with `--python-source`, and
ordinary source dependencies imported during discovery and codec materialization,
discovery compiles current source rather than trusting timestamp/size-based
bytecode caches. This also covers rapid same-size edits and entry imports during
parent-package initialization. The guard starts before entry-spec lookup because
that lookup may import parents. It remains active through manifest serialization,
including lazy imports performed by codec factories. Already imported modules,
imports outside this discovery command, and custom import loaders retain normal
Python import behavior.
The source bytes compiled by this scoped loader are also checked before output,
including an entry imported by a parent before its entry fingerprint is recorded.
Loaded parent/entry/explicit-helper and transitive source files are protected
from output replacement. These checks do not undo import side effects. Ordinary
user sources compiled during discovery are persisted in its source record and
validated by later artifact generation; they do not need a duplicate explicit
file list. Use `--python-source` for additional build inputs outside that observed
graph. This records their file bytes, not arbitrary cached/custom execution.

Install `svx[manifest]` and pass `--sv-source drivers.sv` to validate the
declared SV package, class, `extends`, and method facts during manifest
discovery with the `pyslang` frontend. For methods found in the scanned source
lineage, it checks task/function, formal count/order/direction, and virtual or
static declarations. Include the relevant base-class sources as well. This is
not a full SV elaborator or proof that arbitrary source types are equivalent;
compile the generated adapters with the real design. SvTypes bindings remain
the sole contract for call data.

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest inheritance.json --python-out generated/python \
  --sv-out generated/inheritance_mirrors.sv \
  --artifact-manifest generated/svx-artifacts.json
```

Set `SVX_ARTIFACT_MANIFEST` to that compatibility manifest before runtime
initialization. Use the same command with `--check` in a build verification
step to reject stale mirrors without rewriting them.

For an SV-owned `tb_pkg::BaseDriver` that crosses into Python, derive from the
generated `svx_mirror.tb_pkg.BaseDriver`. A Python-owned construction creates the internal SV bridge
and binds it to the Python instance; an SV-owned generated construction binds
its Python companion before its initializer accesses projected fields.
SV-origin constructor metadata does not prohibit normal Python construction;
calling the mirror initializer for an already-bound SV receiver does not
allocate another object. The implementation bridge is
`svx_mirror_sv_tb_pkg_BaseDriver::BaseDriver`, not an application base type.
For a Python-owned `checks.BaseMonitor` that is followed
by an SV descendant, derive in SV from the generated
`svx_proxy_checks::BaseMonitor`; Python accesses its own source base through
the generated same-name runtime adapter `svx_py.checks.BaseMonitor`, which
forwards the source Python implementation to its SV companion. The generated
public types keep the source simple name; their package/module identifies the
boundary and source namespace.
Declared task overrides may call `super()` across either language boundary.

All proxy objects use a nonzero unique 64-bit remote object ID. Call
`svx.close_instance(instance)` for deterministic pair release, without reading
generated private ID attributes. The integer-ID form remains supported. Or invoke
`svx_pkg::svx_shutdown()` during simulator teardown to clear all inheritance
registries. Calls after either release fail with an unknown-object diagnostic.
Repeated close is idempotent in an active context. Unprojected Python-local
fields remain valid; projected field views do not fall back to old local values.
Release removes the receiver's own SvTypes codec-session registration without
closing the shared session or unregistering other objects. Python close uses a
nonblocking DPI function bridge, including from SV function callbacks. Cleanup
hooks must not delay or perform blocking operations.

Constructible classes declare a manifest `constructor` with an `initiator`
(`python` or `sv`) and an ordered SvTypes-bound parameter list. This origin
metadata is not an exclusive permission to construct from only one language.
The actual generated construction entry determines ownership; a constructible
SV Mirror can allocate its SV receiver from Python, and initialization of an
already bound receiver reuses that receiver. Callers never manually provide a
remote object ID for these factories. The factory allocates the ID, creates both
sides through the generated construction path and binds the pair before Python
initialization accesses projected storage. There is no public post-bind hook API.
If either construction step fails, it rolls back both partial entries. Foreign
virtual calls from constructors are invalid until binding completes.

The generated factory controls the lifecycle: it allocates one object ID,
constructs the paired portions and registers the companion. In supported
alternating chains, Python initializers run at their assigned ancestor stages;
they do not necessarily wait until every SV descendant constructor has returned.
Each Python portion initializes once on the same receiver.
An SV-originated construction must use the
generated construction path; SVX cannot observe the end of arbitrary
handwritten `new` expressions. A raw existing SV handle cannot be given a
Python mirror in SVX 1.0 because SVX has no general object reflection or
destructor hook. Every cross-language instance therefore enters through a
generated constructor or factory.

For existing low-level integrations, an SV target without constructor metadata
retains its ID-based view constructor, `Mirror(registered_object_id)`. The ID must
already identify an SVX dispatchable endpoint with the declared method/field
gateways; it is not a raw SV handle. Selected fields bind to that endpoint through
SvTypes storage, without allocating another SV object or changing construction
selection. Failed field binding removes only the new Python companion; it leaves
the existing SV endpoint intact. This does not generate a new SV helper or make
arbitrary source instances automatically mirrorable. Prefer declared constructors
and generated factories for application code.

Independent ancestor constructor argument routing is not complete. A direct
Python construction can compute arguments in `super().__init__(...)` before
allocating its SV base. In a later initializer stage of an already-constructed
SV descendant, those arguments must match the values used by the completed SV
base; a mismatch is rejected, not silently ignored or used to allocate a second
base object. This is an implementation gap, not a restriction on the intended
natural inheritance model. Do not flatten different ancestor signatures or
rewrite source `super()` expressions to work around it. The internal
`ConstructionRequest` transport is not a public constructor API and is not yet
wired into generated construction. See the
[construction design and current evidence](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md#construction).

This restriction concerns executable mirrors, not declared handle transport.
An arbitrary existing SV class handle may be passed through a declared
`svtypes.RemoteRef[target]` boundary and is opaque in Python: it can be
retained, forwarded, or returned, but not constructed, introspected, or called.
A declared virtual interface similarly crosses as `RemoteRef`, but decodes to
a generated restricted Python view whose signal and task/function members are
derived from its static interface/modport type. See
[Cross-Language Handle Adapters](CROSS_LANGUAGE_HANDLE_ADAPTERS.md) and the
[foreign handles example](../examples/foreign_handles).

Python mirrors preserve every declared parameter in order. `input` receives a
decoded value; `inout` and `output` receive mutable `svx.Inout` and
`svx.Output` carriers. The override reads or writes carrier `.value` and
returns only its ordinary function result, if any. The generated SvTypes
request/response records and their scalar `.value` access are private bridge
implementation details.

Python overrides can implement SV pure-virtual functions and tasks, and an SV
base-typed handle dispatches to those overrides normally. A pure-virtual SV
member has no qualified base implementation: calling its Python mirror wrapper
through `super()` raises `SVXRemoteError` with code `pure_virtual_base`, preserving
the object and method IDs. That failed base call does not copy out output/inout
parameters or fabricate a return value.

An inheritance callback is always an ordinary synchronous Python `def`.
`async def`, an awaitable return value, and `asyncio` are invalid in this path
and cause a fatal SVX callback diagnostic.

Cross-language inheritance manifests accept only `input`, `output`, and
`inout`. `ref` and `const ref` are rejected during generation because SVX does
not transport SV lvalue aliases. A member that needs ref semantics remains in
user SystemVerilog. Applications can define a separate mutable protocol through
SvTypes objects or getter/setter methods.

An SV method declared with `"static": true` is exposed as a generated Python
`@staticmethod`. SVX registers a class-level generated dispatcher that invokes
the qualified SV static member with no object ID. Static methods cannot be
`virtual`; a Python subclass can shadow the name for ordinary Python lookup but
does not override the SV static implementation.

Parameterized SV bases are supported only as concrete specializations. A
manifest identifies `Packet#(int, 16)` with complete type/value arguments, and
that concrete specialization has its own generated mirror/proxy artifact and
canonical class identity. Open parameters and unresolved source expressions
are rejected during generation.

For a Python-owned root whose manifest names the Python base, select its
concrete SV implementation with the generated typed factory:

```systemverilog
svx_proxy_base_monitor::BaseMonitorFactory#(SvCounter) factory;
svx_init();
factory = new();
// Now load/start the Python entry that constructs its BaseMonitor view.
```

The generated factory decodes the typed constructor request and registers the
implementation. Application code does not implement `svx_factory`, deserialize
request records, or call the internal registry. Its derived class forwards the
provided opaque `object_id` to the generated base constructor. This selects
one implementation of the Python root; it does not infer the SV descendant's
full lineage from its name.

This factory example is not the complete Python-root alternating-lineage
workflow. Public generation currently rejects a complete Python-root crossing
plan. Standalone and SV-root projected Python-source static function/task bridges are publicly generated
and require importing their generated Python module to register the source
`@staticmethod`, without constructing a source instance. Projected sources are
resolved from their declared manifest symbol on the first callback, avoiding a
circular eager import between a user class and its generated mirror. Qualified
static calls select that source class, not a more-derived instance. Internal staged
constructor regressions do not make the complete lineage workflows
available. These are implementation gaps rather than restrictions imposed by
the inheritance design; see the
[conformance note](SVX_1_0_REQUIRED_FEATURES.md#implementation-conformance-note).

Natural constructor argument transformations across multiple portions are also
not fully routed. The internal staged path compares a Python base initializer's
arguments with an already completed SV base constructor and rejects a mismatch;
it cannot send newly computed arguments back to that completed constructor.
This is not a design restriction against `super().__init__(seed + 1)`, and the
single implementation-selector example does not establish that broader support.

Supported today: declared task and nonblocking function calls in both
directions, SvTypes payloads, task/function-base `super()` calls, direct
recursive callback rejection, both constructor initiators with SvTypes
arguments, timed task overrides, and explicit shutdown cleanup. Function
callbacks are nonblocking and cannot consume simulator time. General
blocking cycles are rejected when an active object/method frame repeats; the
diagnostic includes the complete repeated-frame path.

Integration sources, including inheritance regressions, are available under
`tests/integration/`. The Python suite runs through `pytest`.

## 18. Hierarchical Signal Access

Declare every path in one imported declaration module and initialize SVX with
that module before loading tests:

```python
import svx
from svtypes import Bit, Logic

status = svx.declare_signal("tb.status", Bit(8))
control = svx.declare_signal("tb.control", Logic(8))
```

```systemverilog
svx_init_with_signal_declarations("project.signal_declarations");
```

Initialization resolves and validates the complete set before the runtime
becomes ready. The registry is then sealed; paths cannot be added lazily.
`read()`, `write()`, `force()`, and `release()` are synchronous operations at
the current simulation point. A two-state codec rejects an observed X or Z.
`Logic` preserves 0, 1, X, and Z through its public SvTypes value/X/Z
planes for reads, deposits, and forces.
Always pair a successful `force()` with explicit `release()` in `finally`.
The force ledger belongs to the declared path, not to an individual Python
handle; SVX does not maintain nested force stacks or restore an earlier force.
Shutdown warns about forces still recorded as active and clears the path cache,
but does not release those forces. Garbage collection also does not release them.
Release while the runtime and execution context remain active, before shutdown.

Use this interface only for small, temporary setup, inspection, and fault
injection. Keep repeated, signal-intensive behavior in SystemVerilog and move
summaries or transactions through typed channels.

## 19. Debug Checklist

When integration fails, check:

- `PYTHONPATH` includes the repository and project Python roots
- `LD_LIBRARY_PATH` includes the SVX shared library directory
- simulator load configuration includes the `libsvx` runtime
- generated SV matches the current Python SvTypes declarations
- channel names match exactly
- payload kind is `svtypes`
- payload content type is `application/x-svtypes`
- payload type metadata matches the expected class name
- object registries were not cleared too early
- Python code called SVX primitives only inside an active SVX execution context

## 20. Anti-Patterns

Avoid:

- Python `async`/`await` for simulator timing
- Python threads or subprocesses calling SVX primitives
- Python-owned signal-level bus timing
- storing raw simulator handles in SvTypes objects outside declared `RemoteRef` contracts
- sending typed transaction data as strings or hex text
- reusing one channel for unrelated payload types
- replacing stable SV drivers or monitors before the channel boundary is proven
- creating a new component hierarchy before the current primitives are adopted
- invoking undeclared foreign methods or bypassing generated mirrors
- manually serializing inheritance values outside SvTypes

## 21. Iterative Development

Separate application implementation changes from boundary-contract changes:

| Change | Regenerate | Recompile SV/native | Next run |
|---|---|---|---|
| Python method/test body, with unchanged declarations | Refresh discovery/artifact records if the edited source is tracked; unchanged bridges are preserved | No | Fresh simulator run imports the edited Python code |
| Python method parameter/result/direction/timing declaration | Manifest and affected bridge outputs | Compile affected generated SV | Fresh run validates the new artifacts |
| SvTypes field/schema or projected field declaration | Types and affected bridges | Compile affected generated SV | Fresh run uses matching descriptors/codecs |
| SV method body with unchanged interface | Refresh tracked discovery/artifact records; refresh integrated SV copies when used; unchanged interface bridges are preserved | Compile the changed original or integrated SV source | Fresh run |
| SV interface/modport or exposed method signature | Metadata/manifest and bridges/views | Compile changed SV/generated sources | Fresh run |
| Declared hierarchical signal paths | No inheritance generation | Only if the SV design changed | Fresh run imports and validates declarations |
| SVX native runtime or Python ABI upgrade | Regenerate matching bridges when ABI changes | Rebuild native and matching SV inputs | Fresh run |

Repeated generation preserves byte-identical outputs and their timestamps.
Use `--check` for a read-only build gate. Do not regenerate bridges merely
because a test algorithm changed. Keep generated files in their own output
root and never edit them manually.

For routine body-only edits, automatic discovery provenance and generation import
records still detect changes to tracked source, even without `--python-source`.
Rerun discovery and generation with the same arguments to refresh their records,
in that order, and continue only when both commands succeed. They already validate
sources and their output ownership before publication. A routine interactive
refresh does not require immediately repeating both commands with `--check`.
Use the ordered read-only checks below when verifying existing artifacts in a
build, CI or release gate without modifying them. Unchanged manifest contracts and bridge files
retain their timestamps; metadata refresh does not require SV recompilation.
Edits outside the tracked input graph do not require this refresh, but the checks
do not certify such inputs. Keep generation commands in a
project build script and reuse their argument lists for checking rather than
maintaining separate handwritten check recipes. The CLI does not reconstruct
the discovery command or infer a complete source dependency graph; the build
script must still maintain those inputs.
Source validation has a nonzero cost that grows with the observed import graph
and filesystem latency, even when only one class is generated. Preserving bridge
timestamps avoids recompilation; it does not make metadata refresh or checks
free. Measure the complete refresh/check/run workflow for the application rather
than using a small example as a large-project performance guarantee.

For an explicit source audit, repeat `inheritance-gen --python-source FILE` for
the Python input files your build tracks. This fingerprints files without
executing them, detects edits even when the manifest and generated code are
unchanged, and protects them from generated-output replacement or cleanup.
For files explicitly included in this audit, a body-only edit requires refreshing the artifact
input record before its `--check` can pass; unchanged bridge sources and their
timestamps are preserved, so this is not a reason to recompile unchanged SV.
The manifest still requires its own discovery check when declarations change.
During generation, newly imported ordinary codec-factory modules and their source
dependencies are also read directly from source and checked before returning a
check result or writing outputs. Changes or disappearance abort the command;
consumed sources cannot be overwritten or pruned, even with an old generated
marker. Ordinary user source files actually compiled during generation are also
recorded as `generation_inputs.python_imports` in the artifact manifest.
Python standard-library, SVX, SvTypes and source-parser implementation modules are not automatic user input records:
their import timing depends on interpreter warm-up. They still participate in
the command's consumed-source stability/overwrite protection when loaded, and
explicit `--python-source` inputs remain recorded regardless of their location.
Artifact checking regenerates the bridge using the current framework; these
user import records are not a framework installation or dependency lock.
Standard-library exclusion uses the interpreter's actual library roots and module
identities, not module names alone or a blanket exclusion of installed packages.
Same-name user modules and third-party packages remain audited; explicit inputs
remain audited even when they belong to the standard library.
Subsequent checks detect their edits even if bridge text is unchanged; refresh
generation to update the record without rewriting matching bridge files.
In-process repeat callers retain recorded imports reused from the module cache.
If an audited cached module's source changed, generation rejects it and asks
for a fresh command process instead of certifying old code against new bytes.
Ordinary imports also reject cached user dependencies with no current validated
discovery or generation evidence, including on initial generation. Naming a file
with `--python-source` does not establish which bytes created cached definitions.
This does not reload cached modules, replace custom importers or track arbitrary
preexisting object references. The separate discovery source record carries its
audited ordinary-source graph to generation.
Automatic import records require canonical relative paths, unique resolved
source identities and lowercase SHA-256 digests. Damaged records reject both
generation and checking before outputs change. A fresh command recomputes the
actually imported dependencies, so removing an import and its unused source
does not leave a permanent obsolete dependency. A long-lived caller retains
audited cached imports; use a fresh process to recompute that graph.
If the artifact metadata itself is damaged, restore a known-good copy. When no
copy exists, preserve the damaged file for diagnosis, remove only that generated
artifact manifest and regenerate in a fresh process using the complete inputs.
Keep the output inventories and original sources; do not clear the output tree.
Then rerun declaration and artifact checks in order. This recovery reconstructs
current metadata, not missing historical discovery provenance.
Run the two read-only gates in order when verifying existing artifacts for builds
driven by Python declarations:

```sh
python -m svx inheritance-manifest \
  --python-module checks.base_monitor \
  --sv-declarations sv-inheritance-declarations.json \
  --out inheritance.json --check &&
python -m svx inheritance-gen \
  --manifest inheritance.json \
  --python-out generated/python --sv-out generated/mirrors.sv \
  --artifact-manifest generated/svx-artifacts.json --check
```

For same-package or mixed-root alternating inheritance, use an integrated copy
of the original SV source units instead of manually placing generated includes:

```sh
python -m svx inheritance-gen \
  --manifest inheritance.json \
  --sv-source bus_if.sv --sv-source drivers.sv --sv-compilation-unit \
  --python-out generated/python --sv-integrated-dir generated/sv \
  --artifact-manifest generated/svx-artifacts.json
```

Compile `generated/sv/source.sv` in place of the listed original source units;
do not compile both copies. Compile the SvTypes and SVX runtime packages before
it. The output includes the shared call records and ordered source/helper
declarations. Original source files remain unchanged. Sources are consumed in
the given order; multiple inputs require `--sv-compilation-unit`. Supply the
same macro definitions and include directories as the build. The optional
`manifest` installation extra provides the required source parser.
`--sv-integrated-dir`, `--sv-stage-dir` and `--sv-out` are mutually exclusive.
Repeat the same command with `--check` for a read-only freshness check. Unchanged
files retain timestamps; inventories and input-overwrite protection apply to
both generated directories. This does not automatically rerun declaration
discovery, infer missing build inputs, or support every source/macro form and
constructor routing scenario. The remaining restrictions are described in
[the lineage contract](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md).

Use the same source/compiler options as the corresponding generation commands.
If discovery fails, update declarations/metadata and rerun it without `--check`
before regenerating bridges. If discovery passes and only audited Python input
records changed, refresh generation without `--check`; no unchanged bridge needs
recompilation. Source discovery writes a versioned record next to the manifest;
generation rejects changed discovery sources before executing codec factories.
Body-only edits require rediscovery to refresh that record, followed by generation
to refresh artifact inputs; matching manifest and bridge timestamps are retained.
For manifests discovered from SV sources, checking also replays their stored
source/include order, macros and compilation-unit mode. A newly added preferred
header makes the selection stale even when previously selected files are intact
and both headers have the same content. Install the `manifest` extra for these
file-backed checks, including generation commands with no repeated `--sv-source`.
Rediscover older source records missing the selected-dependency inventory.
Imports outside the generation source-loader scope and external build scripts
are not automatically tracked. Handwritten/legacy manifests without the discovery
reference have no source-discovery evidence, so keep explicit dependency checks.
For example, a discovery helper can define `Scalar = svtypes.Bit[8]` for a
method argument annotation. Changing it to `Bit[16]` makes generation reject the
old manifest using its discovery source record, even though generation need not
import that helper. Rediscovery updates the contract and record; generation then
reports stale bridges. The two-stage checks still verify the requested discovery
configuration and the generated outputs, not an entire external build recipe.
Stale diagnostics identify changed, added or removed recorded input files and
changed parsing configuration. When all bridge files and other artifact metadata
match and only selected Python input records differ, the check says so and
recommends refreshing the record without rewriting unchanged bridges. This is
not automatic declaration discovery or proof that unrelated build inputs are
current. SV input changes still require rebuilding the affected original SV
sources even if their generated adapters have not changed.
Generation records the selected input fingerprints before manifest
materialization and revalidates them before returning a check result or writing
generated output. A detected edit or missing input aborts the command without
writing generated files; retry after the inputs settle. The artifact records
the initial fingerprints, not a later revision silently picked up during output
generation. This guard does not lock source files or provide a transactional
filesystem snapshot, and it cannot undo side effects in user codec factories.

The check includes the sorted Python and staged-SV generated-file inventories,
not only source contents and the artifact manifest. Missing or stale inventories
fail the gate without rewriting files. Regeneration restores the current
inventory without touching unchanged sources. The previous artifact manifest
also provides historical ownership when an inventory is lost or retirement was
interrupted: only recorded obsolete files inside the current output root, with
matching generated headers and SHA-256, can be removed. Modified files are
reported before writes, and files outside that root or absent from the record
are left alone. Files reassigned to any current output are protected. If both
the historical inventory and artifact manifest are lost, SVX cannot infer old
ownership; preserve these metadata files with your generated build inputs.

Inheritance generation preflights output ownership and path boundaries. If a
requested target is an existing non-generated file, move your handwritten code
or select a dedicated generated output directory; SVX refuses to overwrite it.
This includes an artifact manifest that is not an SVX generated-artifact JSON.
Existing non-directory parents and overlapping output-file paths are rejected
before writing. Contract/schema validation and artifact metadata rendering also
finish before output replacement or removal of obsolete generated modules.
Do not use directory symlinks to redirect individual generated packages outside
that output root. Inventory entries must be canonical relative paths. Absolute
paths, parent traversal, duplicate file identities and obsolete-file symlinks
are rejected before changing outputs. Preserve valid ownership metadata rather
than deleting it to bypass a diagnostic. File replacement is atomic per file, not across the whole
output set. After an I/O interruption, regenerate and run `--check` before building.

Expected command errors report their location/reason on stderr and return 2.
Use `python -m svx --debug inheritance-gen ...` for the full traceback; the
`--debug` option belongs before the subcommand. Unexpected implementation errors
retain their traceback even without that option.

`svx_load` reads current filesystem Python source on first import, including
source dependencies imported during that load, rather than trusting timestamp-based
bytecode caches. Already imported modules retain ordinary Python import caching;
this is not a hot-reload operation.
Shutdown/reinitialization within the same simulator process is not supported.
Restarting simulation is needed to load edited Python modules, but does not by
itself require recompiling the simulation executable.

The source frontend currently imports decorated Python modules and consumes
explicit SV JSON declaration metadata. `--sv-source` validates SV declarations
and discovers VIF members; it does not automatically infer every SV class
method/field declaration. Selected methods, constructor formals and fields
are checked against semantic source types, including equivalent typedefs and
closed specialization. A type mismatch preserves the previous manifest; a
body-only change does not rewrite unchanged output. This is not a validation
of every initializer, field policy or codec implementation.
Selected methods also retain their effective SV virtual/static/pure-virtual
qualifiers. A source qualifier change that conflicts with metadata fails before
replacing the manifest. `local` methods/fields cannot be exposed; `protected`
members use derived gateways rather than changing their source visibility.
Source discovery therefore requires importable
Python declarations (including mirror stubs where needed), and SV metadata must
be maintained with its source. Constructor parameters are explicit metadata,
not inferred from arbitrary `__init__` bodies. These are current integration
costs, not requirements to duplicate handwritten transport/serialization code.
For selected `RemoteRef` fields, the frontend can discover native class/VIF
handle information from supplied SV sources, including imported typedefs and
inherited members. The source-derived static type is checked before comparing
it with the wire carrier. This does not add the referenced class to the target
list, and by-value SvTypes object fields remain by-value fields.
For SV enum and packed-struct values, discovery can reuse concrete public
`svtypes.Enum` and `svtypes.SvStruct` declarations visible in the selected Python
modules or their ancestor modules. It checks ordered enum members and values,
ordered struct fields, and recursive width, signedness and state domain against
the SV source. A typedef alias retains its native SV spelling while using the
underlying value declaration's SvTypes identity. Missing or ambiguous matching
declarations require explicit metadata; discovery does not synthesize Python
value classes or add them to the generation targets.
For a parameterized SV base with a closed default specialization, discovery
records the resolved type/value arguments and discovers members from that
specialization. Automatic value discovery currently covers integral and string
parameters. Localparams are not specialization arguments. Integral values
containing X/Z cannot be flattened into manifest integers and require explicit
metadata. Named class typedefs such as `typedef Base#(byte, 4) ByteBase;`
also support discovery: the typedef supplies the stable class name and identity,
and its specialized members are discovered without an extra template target.
Different named specializations remain distinct. Inline non-default base
specializations require a named typedef or explicit specialization metadata;
discovery rejects a mismatch rather than substituting the default instance.
For scalar class-handle fields and call parameters/returns, a named closed class
typedef also supplies the `RemoteRef` target identity. The native SV type is
resolved to the underlying specialization; the referenced type is not added to
the generation targets. An unnamed parameterized handle still requires an
explicit target identity rather than an automatically guessed name.
Source-resolvable native handle aliases and default specializations are normalized
across fields, constructors, method parameters/returns and Python declarations.
Equivalent alias-only edits leave unchanged manifests untouched; incompatible types
for one handle target fail before replacing the manifest. Opaque types whose source
definitions are absent retain their explicit spelling and are not source-validated.
