# 仿真器驱动的 Fork/Join

[English](README.md)

当 Python 测试意图需要由仿真器管理的并发工作时，使用此示例。它展示：

- `svx.fork_join`
- `svx.fork_join_any`
- `svx.fork_join_none`
- `ProcessGroup.status`
- `ProcessGroup.kill`
- `ProcessGroup.await_`

预期总时间约为 3.75 ns：

- `fork_join`：两个 child 分别延时 1 ns 和 2 ns，因此 parent 在 2 ns 恢复。
- `fork_join_any`：较快 child 延时 0.5 ns，parent 在 2.5 ns 恢复并终止较慢 child。
- `fork_join_none`：后台 child 延时 1.25 ns，随后被等待，最终时间为 3.75 ns。
