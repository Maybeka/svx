# Shared Python State

[中文](README.zh-CN.md)

Use this with the fork/join example to understand that forked Python object
methods share the same Python
heap while each simulator-owned Python process has its own execution state.

The test forks two bound methods from one `SharedCounter` object:

- `writer` waits 1 ns, then sets `counter.value = 7`.
- `reader` waits 2 ns, then checks that it can observe `counter.value == 7`.

Passing this test confirms that dedicated `PyThreadState` instances isolate
Python call stacks, not Python object memory.
