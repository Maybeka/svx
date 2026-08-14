# SVX Project Specification

Status: architectural baseline. The normative proposed `1.0.0` feature and
release contract is [SVX_1_0_REQUIRED_FEATURES.md](SVX_1_0_REQUIRED_FEATURES.md).

## 1. Purpose

SVX, short for SystemVerilog eXtension, is a simulator-hosted Python
verification extension for SystemVerilog.

SVX is intended for SystemVerilog verification engineers who want to keep
hardware-coupled testbench structure in SystemVerilog while moving higher-level
verification intent into Python.

Hardware-coupled code includes interfaces, clocking/reset logic, drivers,
monitors, agents, sequencers, DUT binding, and other code that must stay close
to SystemVerilog timing semantics.

Python code is intended for tests, sequences, transactions, configuration,
checking policy, reusable scenario logic, and other high-level verification
behavior.

SVX must support incremental migration from existing SystemVerilog or UVM
environments. Existing SV/UVM components should be able to call Python
components, and Python components should be able to interact with existing
SystemVerilog services through SVX.

Post-silicon reuse of Python verification code is a useful future direction,
but it is not part of the initial SVX project scope.

## 2. Design Philosophy

SVX uses Python as a synchronous verification logic language hosted by the
SystemVerilog simulator. Python is not a simulator scheduler.

All simulation timing, event control, process scheduling, and simulator-visible
parallel execution are owned by the SystemVerilog simulator.

Python code obtains timing and concurrency behavior only through SVX primitive
APIs. Those primitive APIs cross DPI into SystemVerilog services that are
scheduled by the simulator.

SVX must not expose Python `async`/`await` as a user model.

SVX may allow Python-native host-side computation, but Python-native
concurrency is outside the simulator scheduling contract and must not call SVX
primitive APIs.

## 3. Concurrency Model

SVX distinguishes three forms of concurrency.

### 3.1 Simulation Concurrency

Simulation concurrency is owned by the SystemVerilog simulator.

It includes SystemVerilog `fork`, `join`, `join_any`, `join_none`, events,
delays, waits, process handles, and other simulator-kernel scheduling
mechanisms.

This is the only concurrency that may affect simulation time.

### 3.2 Python Interpreter Concurrency

SVX uses one embedded CPython interpreter loaded into the simulator process by
the SVX shared library.

Python execution is governed by the CPython GIL. Multiple simulator processes
may request Python callback execution, but all Python interpreter entry must be
managed by SVX.

Milestone implementations should prefer a conservative model: one interpreter,
shared GIL, and serialized Python bytecode execution unless a later spec defines
a stricter reentrant execution contract.

### 3.3 Host Concurrency

Python threads, `asyncio`, multiprocessing, subprocesses, C++ threads, and
other host-native concurrency mechanisms are not simulation concurrency.

They may be used only for host-side work that does not call SVX primitive APIs.
They must not advance simulation time, wait on simulator events, call exported
SV tasks, access simulator objects, or use SVX process primitives.

## 4. SVX Execution Context

An SVX execution context is created when the SystemVerilog simulator enters
Python through an SVX-managed DPI path.

SVX primitive APIs are legal only inside an SVX execution context.

Examples of simulator-owned SVX execution contexts include:

- A Python function invoked by `svx_start`.
- A Python callable launched by `svx.fork_join`.
- A Python callable launched by `svx.fork_join_any`.
- A Python callable launched by `svx.fork_join_none`.
- A callback explicitly entered by a simulator-owned SVX service.

Examples that must not have an SVX execution context include:

- Python code running in a user-created Python thread.
- Python code running in an `asyncio` task.
- Python code running in a multiprocessing worker.
- Python code running in a subprocess.
- Python code imported or executed outside the simulator-hosted SVX runtime.

Every SVX primitive API must validate that a current SVX execution context
exists. If no context exists, it must fail with a clear SVX context error rather
than attempting to call into the simulator.

## 5. Project Layers

SVX is organized into separate layers.

### 5.1 SvTypes

SvTypes is the data definition layer.

SvTypes is a separate versioned dependency of SVX. It must remain usable as an
independent package and repository. This helps adoption because users can define
SystemVerilog-like data models in Python and generate matching SystemVerilog
and C++ code without adopting the full SVX runtime immediately.

SvTypes is responsible for:

- Python DSL definitions for SV-like data types.
- Package, type, object, parameter, enum, and collection modeling.
- SystemVerilog and C++ code generation.
- Cross-language serialization parity.
- Type-safe transaction and configuration modeling.

SVX depends on a versioned SvTypes package and consumes only public SvTypes
Python APIs and installed SvTypes SV/C++ support files. SvTypes owns its
by-value and object-graph identity, schema, codec-session, wire-descriptor, and
binary-format contracts. SVX owns a separate simulation-scoped foreign-object
registry used for cross-language inheritance.

When a foreign class instance is carried as a typed argument or result, SvTypes
encodes only an opaque `RemoteRef(target_type_name)` value. SVX resolves and
type-checks that reference against its own manifest and registry. A SvTypes
object-graph ID and an SVX foreign-object ID are distinct identities with
distinct lifecycle and ownership rules.

### 5.2 SVX Runtime

The SVX runtime is the C++/DPI/VPI bridge loaded by the simulator.

It is responsible for:

- Embedded CPython interpreter startup and shutdown.
- Python module loading.
- Python export registration lookup.
- Managed Python callback entry.
- GIL handling.
- SVX execution context tracking.
- Exception capture and reporting.
- Process and callable handle management.
- Named channel and payload transfer management.
- DPI and VPI service integration.

### 5.3 SVX SystemVerilog Package

The SVX SystemVerilog package provides simulator-side services.

It is responsible for:

- Initialization entry points.
- Python task start entry points.
- Exported DPI tasks/functions used by Python primitive APIs.
- Process creation and process management services.
- Timing primitives.
- Named channel registry and payload synchronization services.
- DPI service declarations and startup/shutdown integration.

### 5.4 Python Verification API

The Python verification API is the user-facing Python package.

It is responsible for:

- Export decorators.
- Primitive APIs such as delay, display, and fork/join.
- Process/group handle wrappers.
- Named channel APIs for raw payload and typed transaction exchange.
- Error policy configuration.
- User-facing exceptions.

## 6. Python Export Model

Python functions callable from SystemVerilog must be explicitly exported.

The default export name is namespaced by Python module and function name:

```text
<python_module>.<function_name>
```

Example:

```python
# tests/basic_test.py
import svx

@svx.export
def main():
    svx.display("hello")
```

The exported function is registered as:

```text
tests.basic_test.main
```

SystemVerilog may then start it by name:

```systemverilog
initial begin
  svx_init();
  svx_load("tests.basic_test");
  svx_start("tests.basic_test.main");
end
```

Arbitrary dynamic function lookup without explicit export is not part of the
core SVX execution contract.

## 7. Primitive API Model

SVX starts with explicit primitive APIs rather than a generic arbitrary
SystemVerilog task call mechanism.

Primitive APIs are user-facing Python functions backed by known SVX runtime and
SystemVerilog services.

Initial primitive categories include:

- Display/logging.
- Delay and timing.
- Simulator-owned process creation.
- Process status, await, and kill.
- Named payload channels.
- VPI-backed simulator object access.

Manifest-declared foreign object methods are callable through generated
cross-language inheritance adapters. Their arguments and results use SvTypes
request/response types, and dispatch uses canonical class/method IDs rather
than simulator reflection.

Generic calling of an undeclared SystemVerilog task by hierarchical name is not
part of the core contract. It would require a separate declaration, scheduling,
and type-conversion design.

## 8. Process Model

SVX supports Python-authored simulation concurrency through SVX process
primitives.

Python code may call:

```python
svx.fork_join([...])
svx.fork_join_any([...])
svx.fork_join_none([...])
```

These calls do not create Python-native concurrency. They delegate process
creation and scheduling to the SystemVerilog simulator.

Each child Python callable is entered through an SVX-managed DPI callback and
receives its own valid SVX execution context.

`fork_join_none` should return a process or process-group handle that can later
be used to query, await, or kill simulator-owned work.

## 9. Error Policy

Uncaught Python exceptions in SVX execution contexts are handled by a
configurable exception policy.

The default policy is fatal.

The fatal policy must report the Python exception and traceback, then terminate
or fail the simulation through the configured SystemVerilog fatal mechanism.

Future policies may include:

- `return`: report failure to the SV caller without fatal termination.
- `defer`: store failure in a process handle and report on await/status query.
- `callback`: invoke a user-provided error handler.

## 10. Backward Compatibility

SVX must support incremental adoption in existing SV/UVM environments.

It should not require users to replace existing drivers, monitors, agents,
sequencers, or UVM phase structure in order to use Python-authored tests and
sequences.

Existing SV code should be able to call into SVX at controlled integration
points. Python code should be able to use SVX primitive APIs to interact with
the simulator and with registered SVX services.

## 11. Non-Goals

SVX does not initially replace all SystemVerilog testbench code.

SVX does not initially replace UVM drivers, monitors, sequencers, agents, or
phase mechanics.

SVX does not expose Python `async`/`await` as the user timing model.

SVX does not treat Python threads, multiprocessing workers, subprocesses, or
`asyncio` tasks as simulator-visible processes.

SVX does not provide reflective invocation of undeclared SystemVerilog tasks by
hierarchical name. Manifest-declared class method dispatch is the supported
generic object-call mechanism.

SVX does not initially target post-silicon execution, although APIs should avoid
unnecessary simulator-only coupling where practical.
