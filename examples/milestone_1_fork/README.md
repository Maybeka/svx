# Simulator-Backed Fork/Join

[中文](README.zh-CN.md)

Use this when Python test intent needs simulator-owned concurrent work. It
demonstrates:

- `svx.fork_join`
- `svx.fork_join_any`
- `svx.fork_join_none`
- `ProcessGroup.status`
- `ProcessGroup.kill`
- `ProcessGroup.await_`

The expected total time is approximately 3.75 ns:

- `fork_join`: children delay 1 ns and 2 ns in parallel, so parent resumes at 2 ns.
- `fork_join_any`: fast child delays 0.5 ns, so parent resumes at 2.5 ns and kills the slow child.
- `fork_join_none`: background child delays 1.25 ns and is awaited, so final time is 3.75 ns.
