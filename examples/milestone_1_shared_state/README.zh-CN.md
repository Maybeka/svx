# 共享 Python 状态

[English](README.md)

配合 fork/join 示例使用。它说明 fork 出来的 Python object method 共享同一
Python heap，而每个仿真器拥有的 Python process 具有独立执行状态。

测试从同一 `SharedCounter` object fork 两个 bound method：

- `writer` 等待 1 ns 后将 `counter.value` 设为 7。
- `reader` 等待 2 ns 后检查能观察到 `counter.value == 7`。

通过表示专用 `PyThreadState` 隔离的是 Python 调用栈，而不是 Python object
memory。
