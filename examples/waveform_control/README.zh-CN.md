# 可选波形控制

[English](README.md)

由 [tb.sv](tb.sv) 启动 [python_test.py](python_test.py)。SV DUT 持续运行，
Python 控制波形记录的时间与范围，无须 manifest、生成镜像或自行编写 wrapper。

## 准备与运行

遵循[共用运行指南](../RUNNING_EXAMPLES.zh-CN.md)。构建 `libsvx` 时启用直接
层次访问：设置 `SVX_REQUIRE_DIRECT_VPI=ON` 和匹配的
`SVX_SIMULATOR_INCLUDE_DIR`。仿真构建中加载 FSDB dumping 后端，并在编译
`svx_pkg` 前定义 SV 预处理宏 `SVX_ENABLE_FSDB_WAVEFORM`。
wrapper 由 `sv/svx_pkg.sv` 包含，随 SVX 发布；外部 dumper 库不随包提供。

先用已安装的后端编译可选 wrapper，确认所需系统任务可用。运行时分支不能
隐藏未知系统任务。未定义该宏时，其他 SVX 功能照常使用，
`svx.waveform.capabilities()` 返回空集合。在普通 Python 中 import SVX 不会
启动或加载波形后端。

以普通 SVX/SvTypes 包含路径编译 `examples/waveform_control/tb.sv`，加载
`libsvx`，设置源码导入路径 `PYTHONPATH=python:../svtypes/python:.`，并把
`SVX_WAVEFORM_OUTPUT` 设置为新的可写输出目录。示例会创建目录；API 本身
不会创建缺失的父目录，已存在或本轮仿真已使用过的文件名会被拒绝。

## 使用流程

```python
wave = svx.waveform
wave.begin("first.fsdb", scopes=[("tb.dut", 1)])
wave.pause()
wave.resume()
wave.switch_file("continued.fsdb")
wave.add_scope("tb.dut.child", 0)
wave.finish()
wave.begin("second.fsdb", scopes=[("tb.dut.child", 0), ("tb.other", 0)])
wave.finish()
```

所有操作同步执行，要求 SVX 仿真器拥有的 task 上下文，本身不推进仿真时间。
用 `svx.delay()` 分隔记录区间；SV function 回调中禁止这些 task 调用。
scope 字符串在调用时解析，不需要 `Signal` 声明；`begin` 会先校验全部 scope，
再打开文件。深度1选择当前层，2包含下一层，0包含全部下级。

预期输出 `WAVEFORM_CONTROL_PASS`，生成三份 FSDB：

- `first.fsdb`：父层计数器0..15ns，其中5..10ns暂停。
- `continued.fsdb`：15ns起保留已有选择，并加入子模块信号。
- `second.fsdb`：25..30ns仅选择 child/other，不含上一轮父层计数器。

应检查实际信号名称和变化时间区间，不只检查文件存在。暂停期间或新增 scope
之前的历史不会补录。

## 边界

`switch_file` 保留选择；`finish` 关闭所有 FSDB 输出并重置选择，之后可以重新
`begin`。`finish` 幂等；活动状态内重复暂停或恢复也幂等。
`add_scope` 只增加信号，不移除旧选择；`flush` 刷新缓冲区但不关闭文件。

接口管理一个全局 dumping 会话。不要同时用独立 SV/Tcl 命令控制 dump，因为
底层启停和结束操作可能影响所有文件。缺失或不支持的 scope、状态和文件名
错误抛出 `SVXWaveformError`；执行上下文错误抛出 `SVXContextError`。
调用成功不能保证所有 dumper 内部或磁盘错误都被转换成异常，仍应保留后端
诊断并检查产物。应在 `svx_shutdown` 前调用 `finish`。
