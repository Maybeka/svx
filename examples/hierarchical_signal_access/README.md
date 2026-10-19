# Hierarchical Signal Access

[中文](README.zh-CN.md)

Follow the common [example run guide](../RUNNING_EXAMPLES.md), including its direct-VPI build requirement.

Use this for targeted setup, inspection, and fault injection from a Python
test. It is intentionally not a replacement for an SV driver, monitor, or
high-volume signal transport.

`signal_declarations.py` is imported while SVX initializes. It declares every
path and its SvTypes codec up front. `tb.sv` calls
`svx_init_with_signal_declarations` with that module name, so invalid paths or
incompatible packed shapes fail before the Python test begins.

The test demonstrates:

- two-state `Bit` read and write;
- `force` followed by `release` on a packed signal;
- four-state `Logic` read/write using `LogicValue`;
- explicit `with status.subscribe() as latest` cached observation;
- explicit delays only where the testbench needs simulation to advance.

The force interval uses `try/finally` so a Python exception still attempts
explicit release before leaving the active runtime context. Neither garbage
collection nor shutdown releases a force automatically. Shutdown warns about
forces still recorded as active; it does not restore previous signal values.
SVX tracks force state per declared path, not per Python handle, and provides
no nested force stack. Coordinate callers sharing a path.

A subscription seeds its initial value and caches native value-change
notifications without executing Python callbacks. `latest.read()` decodes that
cache; `status.read()` still reads the current HDL value. Notifications may lag
same-region writes and may coalesce, so this is not a settled sampling barrier
or an event log. The example advances to a stable testbench observation point
before comparing the two. The `with` block closes the subscription; explicit
`close()` is also supported, and shutdown retires remaining subscriptions.
Garbage collection does not unsubscribe. Use subscriptions for frequently read,
infrequently changing signals, not as a replacement for high-volume SV monitors.

The example declares two-state paths as `reg` and packed `reg` in `tb.sv`;
they use the `Bit` codec on the Python side. This is the portable packed
variable form accepted by the current SVX VPI signal service.

Compile `tb.sv` with SVX built with its direct VPI signal service enabled. No
VPI system task or separately loaded VPI plugin is part of the application
interface; the SVX library is loaded through the normal DPI library flow.

Keep paths in one declaration module and do not add them after initialization.
For repeated driving or sampling, retain the behavior in SV and exchange typed
transactions or summaries over channels instead.
