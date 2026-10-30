# SVX Cross-Layer API Contracts

See [SVX_SPEC.md](../SVX_SPEC.md) Section 5 for layer descriptions.

Application code uses [the public API](../SVX_API_REFERENCE.md). This note
explains native ABI checks, not an alternative set of callable prototypes.

The authoritative current declarations are `sv/svx_init.sv`,
`sv/svx_process.sv`, `sv/svx_timing.sv`, `sv/svx_channel.sv`,
`sv/svx_inheritance.sv`, `sv/svx_error.sv`, and
`svx_runtime/include/svx/sv_dpi.hpp`. Initialization includes product/ABI
arguments; blocking delay/channel calls include cancellation state;
inheritance has separate task/function gateways; fatal reporting uses a function.
Use the compiler-derived C declarations for the target toolchain.

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
