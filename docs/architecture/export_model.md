# Export Registration

The [API Reference](../SVX_API_REFERENCE.md) owns callable signatures and public
symbols. The [first-entry Cookbook chapter](../SVX_COOKBOOK.zh-CN.md#2-建立最小-sv---python-入口)
owns the runnable introduction.

## Registration Versus Execution

`@svx.export` and `@svx.test` explicitly register zero-argument entry functions.
The default name is the function's module plus qualified name; an explicit
`name=` provides a stable alternative. Duplicate names fail at registration.
`list_exports()` returns a snapshot and does not require a simulator context.

`svx_load` imports a module, so decorators execute and populate the registry.
It does not create application execution context. A module with no exported
entry is valid: it can provide declarations, data or imported registrations.
Ordinary Python import caching still applies after the first import.

`svx_start` resolves a previously registered name and invokes it within an SVX
execution context. The initiating SV process waits for completion. An unknown
name is an error; it is not evaluated as an arbitrary Python expression.
Errors cross the native reporting boundary, not as Python exception objects
returned to SV. Import/entry exception policy is specified in
[Exception Reporting](error_policy.md).

## Separate Declaration Channels

Inheritance classes and methods use manifest declarations, not export registry
lookups. UVMX test registration uses its own UVM factory integration on top of
public SVX callback contracts; users do not export every UVM phase method.
Neither mechanism expands `svx_start` into an argument-passing API.
