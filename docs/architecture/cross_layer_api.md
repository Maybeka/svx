# SVX Cross-Layer API Contracts

See [SVX_SPEC.md](../SVX_SPEC.md) Section 5 for layer descriptions.

The tables below are historical M1/M2 sketches, not the current DPI signature
contract. Application code must use [the public API](../SVX_API_REFERENCE.md),
not hand-written calls to these private entry points.

The authoritative current declarations are `sv/svx_init.sv`,
`sv/svx_process.sv`, `sv/svx_timing.sv`, `sv/svx_channel.sv`,
`sv/svx_inheritance.sv`, `sv/svx_error.sv`, and
`svx_runtime/include/svx/sv_dpi.hpp`. Initialization includes product/ABI
arguments; blocking delay/channel calls include cancellation state;
inheritance has separate task/function gateways; fatal reporting uses a function.
Do not infer C task-return ABI from the abbreviated SV prototypes below.

An SV task has no SV value result, but the native task entry points use an
`int` return for the task completion/disable protocol in the qualified ABI.
It is not the Python method's return value. The current native definitions are
checked against compiler-derived import prototypes; changing these task entries
to C `void` would break that signature check. Ordinary function results and
generated method response records remain separate contracts.

At the C boundary, `longint unsigned` object IDs use `unsigned long long`,
and SV enum ports use `int`. C++ object-ID and enum types are converted at the
boundary rather than substituted into dynamically resolved function prototypes.
The native qualification build checks all core export pointer types against
compiler-generated C declarations, including exported tasks and the fixed-array
fork pointer. Exported task pointers use `int`, not `void`; blocking delay and
channel wrappers also inspect that disable result. A separate source contract
check keeps the fixed fork-array capacity equal on both sides. These checks
qualify the tested toolchain configuration, not every possible simulator ABI mode.

## 1. DPI Contract Table

All functions below are the minimum set required for Milestone 1.

### 1.1 SystemVerilog → C++ (exported from C++, imported by SV)

| DPI Signature | Purpose | Layer |
|---|---|---|
| `import "DPI-C" context task svx_runtime_init()` | Initialize the embedded Python runtime | Runtime → SV |
| `import "DPI-C" context task svx_runtime_load(string module_name)` | Import a Python module and run export decorators | Runtime → SV |
| `import "DPI-C" context task svx_runtime_start(string export_name)` | Resolve and execute a registered Python export | Runtime → SV |
| `import "DPI-C" context task svx_process__exec(chandle proc)` | Execute a Python callable from an SV process. This must be a task because child Python may call time-consuming exported SV tasks such as `delay_svx`. | Runtime → SV |
| `import "DPI-C" context function void svx_process__set_svobj_idx(chandle proc, int index)` | Bind process handle index after SV process creation | Runtime → SV |

### 1.2 C++ → SystemVerilog (exported from SV, imported by C++)

| DPI Signature | Purpose | Layer |
|---|---|---|
| `export "DPI-C" task delay_svx(real duration, int unit_code)` | Advance simulation time by floating duration and SVX time-unit code | SV → Runtime |
| `export "DPI-C" task fork_svx(chandle fork_proc, chandle procs[32], e_svx_fork_join_type fork_type)` | Create simulator-owned processes for Python callables | SV → Runtime |
| `export "DPI-C" task start_process(chandle proc)` | Start a single simulator process for a Python callable | SV → Runtime |
| `export "DPI-C" task svx_fatal_svx(string source, string message)` | Report a fatal SVX failure through `$fatal` | SV → Runtime |
| `export "DPI-C" function e_proc_state proc_status_svx(int index)` | Query process state by index | SV → Runtime |
| `export "DPI-C" function void kill_proc_svx(int index)` | Kill a process by index | SV → Runtime |
| `export "DPI-C" task await_proc_svx(int index)` | Block until process completes | SV → Runtime |
| `export "DPI-C" function void suspend_proc_svx(int index)` | Suspend a process (future) | SV → Runtime |
| `export "DPI-C" function void resume_proc_svx(int index)` | Resume a suspended process (future) | SV → Runtime |

## 2. Shared Type Definitions

Defined in the production layout by `svx_runtime/include/svx/common.hpp` and
`sv/svx_defs.svh`.

```cpp
// Process state enum — shared between C++ and SystemVerilog
typedef enum {
    FINISHED,
    RUNNING,
    WAITING,
    SUSPENDED,
    KILLED,
    NOT_CREATED,
    REMOVED
} e_proc_state;

// Maximum number of parallel fork children
const int SVX_MAX_FORK_NUM = 32;

// Fork/join type enum — shared between C++ and SystemVerilog
typedef enum {
    FORK_JOIN,
    FORK_JOIN_ANY,
    FORK_JOIN_NONE
} e_svx_fork_join_type;

// Time unit enum — Python maps unit strings to these codes
typedef enum {
    SVX_TIME_S,
    SVX_TIME_MS,
    SVX_TIME_US,
    SVX_TIME_NS,
    SVX_TIME_PS,
    SVX_TIME_FS
} e_svx_time_unit;
```

## 3. Export Registry

### 3.1 Registration

`@svx.export` writes into a global Python `dict`:

```python
# python/svx/export.py (user-facing)
# python/svx/_registry.py (internal)

# Internal registry — keyed by fully qualified export name
_registry: dict[str, Callable] = {}

def register(name: str, func: Callable) -> None:
    if name in _registry:
        raise SVXExportError(f"Export name '{name}' is already registered")
    _registry[name] = func

def resolve(name: str) -> Callable:
    func = _registry.get(name)
    if func is None:
        raise SVXExportError(f"No export registered for '{name}'")
    return func
```

### 3.2 Naming Convention

```
<python_module>.<function_name>
```

Examples:

| Python declaration | Export name |
|---|---|
| `tests/basic_test.py`, `def main():` | `tests.basic_test.main` |
| `pkg/sequences.py`, `def reset_seq():` | `pkg.sequences.reset_seq` |

### 3.3 `svx_load` Contract

`svx_load(string module_name)` maps to `PyImport_Import(module_name)` on the C++ side. This causes the Python module's top-level code to execute, which triggers `@svx.export` decorators to register their functions.

Ordering guarantee: `svx_load` must complete before `svx_start` can resolve the export. If `svx_start` is called before `svx_load` for the target module, it must raise `SVXExportError`.

## 4. Display/Logging

`svx.display(message)` uses native standard output in the current implementation,
not VPI. The following was an early design sketch:

```cpp
// C++ side — uses VPI
vpi_printf((PLI_BYTE8*)"%s\n", message);
```

There is no current promise that output uses the simulator's `$display` channel
or receives an automatic simulation timestamp.

## 5. Milestone 2 Additions

M2 adds named payload channels. The verified DPI contract keeps payload data in
native binary buffers and passes opaque payload handles across the SV/C++
boundary. Python and SV user APIs present payload data as bytes or
byte-equivalent objects; no hex/base64 transport encoding is part of the
contract.

### 5.1 C++ Runtime → SystemVerilog Channel Services

Exported SV tasks/functions:

| DPI Signature | Purpose | Layer |
|---|---|---|
| `export "DPI-C" task svx_channel_put_payload(string name, chandle payload)` | Put one raw payload handle into a named channel | SV → Runtime |
| `export "DPI-C" task svx_channel_get_payload(string name, output chandle payload)` | Blocking get from a named channel | SV → Runtime |
| `export "DPI-C" task svx_channel_peek_payload(string name, output chandle payload)` | Blocking peek from a named channel | SV → Runtime |
| `export "DPI-C" function bit svx_channel_try_put_payload(string name, chandle payload)` | Nonblocking put into a named channel | SV → Runtime |
| `export "DPI-C" function chandle svx_channel_try_get_payload(string name)` | Nonblocking get from a named channel; returns null when empty | SV → Runtime |

For the blocking `get` and `peek` tasks, the C++ side calls the exported SV
task with an output `chandle` parameter. `get` transfers ownership of the
returned payload handle to the receiver. `peek` returns a borrowed handle and
does not transfer ownership.

### 5.2 SystemVerilog → C++ Payload Handle Services

Imported C++ functions:

| DPI Signature | Purpose | Layer |
|---|---|---|
| `import "DPI-C" context function chandle svx_payload_create(string kind, string type_name, string content_type)` | Allocate a native binary payload buffer | Runtime → SV |
| `import "DPI-C" context function void svx_payload_push_byte(chandle payload, byte unsigned value)` | Append one byte to a payload | Runtime → SV |
| `import "DPI-C" context function int svx_payload_size(chandle payload)` | Return payload byte count | Runtime → SV |
| `import "DPI-C" context function byte unsigned svx_payload_get_byte(chandle payload, int index)` | Read one payload byte | Runtime → SV |
| `import "DPI-C" context function string svx_payload_kind(chandle payload)` | Read payload kind metadata | Runtime → SV |
| `import "DPI-C" context function string svx_payload_type_name(chandle payload)` | Read payload type metadata | Runtime → SV |
| `import "DPI-C" context function string svx_payload_content_type(chandle payload)` | Read payload content type metadata | Runtime → SV |
| `import "DPI-C" context function void svx_payload_destroy(chandle payload)` | Release a payload handle owned by the caller | Runtime → SV |

Future optimized transports may add open arrays, chunking, or shared buffers
while preserving the same user-facing Python and SV APIs.

## 6. Future Additions (Post-M2)

These were early proposals, not public APIs or a current roadmap:

- `svx_vpi_get_handle()` — VPI-backed signal access
- `svx_vpi_get_value()` / `svx_vpi_set_value()` — signal read/write
- Generic `svx_call_sv_task(hierarchical_name, args)` was not adopted. Current
  object-method invocation uses typed generated SV dispatch, not arbitrary
  hierarchical task reflection. Hierarchical `Signal` access is implemented
  through direct C VPI and is a separate service.
