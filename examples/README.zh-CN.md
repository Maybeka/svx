# SVX 示例

[English](README.md)

这些示例按验证工程师通常的采用路径组织，而不是按能力最初出现的
milestone 编号组织。建议先阅读 typed-bus 示例，再按所需边界选择专项示例。

| 目标 | 从这里开始 | 展示内容 |
|---|---|---|
| 从 SV testbench 运行一个 Python 测试 | [基础启动](milestone_1_basic/README.zh-CN.md) | `svx_init`、`svx_run_test`、显示和由仿真器管理的延时 |
| 跨边界传输 transaction | [Typed bus testbench](milestone_7_sv_typed_helpers/README.zh-CN.md) | SvTypes 模型、生成的 SV helper、请求/响应与 monitor channel |
| 在既有 SV testbench 中采用 SVX | [既有 SV 环境](milestone_5_existing_env/README.zh-CN.md) | 驱动和监控保留在 SV；场景和检查策略移至 Python |
| 在构建中使用生成类型 | [CLI 工作流](milestone_6_cli_workflow/README.zh-CN.md) | `svx svtypes-gen` 和 CLI 定位命令 |
| 在 Python 中派生 SV class | [跨语言继承](cross_language_inheritance/README.zh-CN.md) | manifest 校验、生成镜像、SV 发起构造与 Python timed override |
| 在 SV 中派生 Python class | [Python 所有的继承](python_owned_inheritance/README.zh-CN.md) | Python 发起构造、SV factory 注册与跨语言 `super()` |
| 检查或临时修改层次路径 | [分层信号访问](hierarchical_signal_access/README.zh-CN.md) | 预声明、启动校验、读/写、force/release 和四态值 |
| 使用原始字节而非 typed model | [Payload channel](milestone_2_payload_channel/README.zh-CN.md) | 二进制 payload、peek 与非阻塞 channel 操作 |
| 理解运行时行为 | [Fork/join](milestone_1_fork/README.zh-CN.md)、[共享状态](milestone_1_shared_state/README.zh-CN.md) 和 [异常策略](milestone_1_error/README.zh-CN.md) | 仿真器驱动的进程控制、Python heap 共享与未捕获异常处理 |

`milestone_*` 目录名因源码和回归兼容性而保留，不代表推荐学习顺序。

## 学习路径

1. 阅读[基础启动](milestone_1_basic/README.zh-CN.md)，理解 runtime entry
   boundary 与由仿真器拥有的时间。
2. 运行 [typed bus testbench](milestone_7_sv_typed_helpers/README.zh-CN.md)，
   学习时钟化 SV 环境的默认 transaction 路径。
3. 在维护中的项目及其 build 中集成此路径时，使用[既有 SV 环境]
   (milestone_5_existing_env/README.zh-CN.md)或 [CLI 工作流]
   (milestone_6_cli_workflow/README.zh-CN.md)。
4. 仅当声明式 virtual-class boundary 是合适扩展机制时，才加入[跨语言继承]
   (cross_language_inheritance/README.zh-CN.md)或 [Python 所有的继承]
   (python_owned_inheritance/README.zh-CN.md)。
5. 仅对小规模、临时的 setup、检查或 fault injection 使用[分层信号访问]
   (hierarchical_signal_access/README.zh-CN.md)。

## 能力矩阵

| SVX 能力 | 主示例 | 关键边界 |
|---|---|---|
| Runtime lifecycle：初始化、加载、启动、运行测试、关闭 | [基础启动](milestone_1_basic/README.zh-CN.md) | SV 拥有仿真 lifecycle 和时间 |
| Delay、display 和 process group | [Fork/join](milestone_1_fork/README.zh-CN.md) | Python 只使用仿真器支持的 primitive |
| 仿真器 process 间共享 Python object | [共享 Python 状态](milestone_1_shared_state/README.zh-CN.md) | 调用栈隔离，object heap 共享 |
| Fatal exception report | [异常策略](milestone_1_error/README.zh-CN.md) | 未捕获 Python exception 遵循配置的 SVX policy |
| Opaque binary transport | [原始 payload channel](milestone_2_payload_channel/README.zh-CN.md) | 仅在 typed SvTypes model 不合适时使用 |
| Checked typed transport 与生成 SV helper | [typed bus testbench](milestone_7_sv_typed_helpers/README.zh-CN.md) | SvTypes descriptor 和 bytes 是唯一 typed wire contract |
| Typed channel role：request、response、monitor | [typed bus testbench](milestone_7_sv_typed_helpers/README.zh-CN.md) | timing、driving 和 sampling 留在 SV |
| 生成 model 和 build-input discovery | [CLI 工作流](milestone_6_cli_workflow/README.zh-CN.md) | 从 `svx` CLI 获取路径和生成产物 |
| 在既有环境中渐进采用 | [既有 SV 环境](milestone_5_existing_env/README.zh-CN.md) | 替换窄数据边界，不替换 SV component structure |
| Python 扩展 SV 所有的 class | [跨语言继承](cross_language_inheritance/README.zh-CN.md) | SV 发起构造，Python 实现声明的 override |
| SV 扩展 Python 所有的 class | [Python 所有的继承](python_owned_inheritance/README.zh-CN.md) | Python 发起构造，SV 注册 factory |
| 目标化分层读/写/force/release | [分层信号访问](hierarchical_signal_access/README.zh-CN.md) | 每条路径都在 runtime ready 前声明并校验 |

SvTypes 的随机化、coverage collection 和 UCIS 处理仍属于 SvTypes。SVX 传输
显式准备好的 typed value，不会在 channel、inheritance 或 signal crossing 时
选择随机值或隐式 sample coverage。

## 推荐的首次运行

先阅读并生成 typed-bus 示例中的模型：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx svtypes-gen \
  --module examples.milestone_7_sv_typed_helpers.tests.types \
  --channel-helpers \
  --out examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv
```

之后通过目标仿真器的常规 DPI 流程编译它的 `tb.sv`、SvTypes runtime SV
package、`svx_pkg.sv` 和生成文件。CLI 可用 `svx sv-files`、
`svx compile-flags` 和 `svx libs` 给出已安装路径。

所有示例都将时间、时钟、信号驱动、monitor 采样和 testbench 并发保留在
SystemVerilog。Python 负责测试意图、typed data 准备和检查策略。
