# SVX 架构图阅读指南

本文只解释图中的角色和箭头，不另行定义接口或复制运行步骤。实际接入从
[Cookbook](SVX_COOKBOOK.zh-CN.md) 选择路线，符号与限制查
[API 参考](SVX_API_REFERENCE.md)。

## 先看哪张图

| 图 | 阅读重点 | 对应权威说明 |
|---|---|---|
| [SVX 全景](architecture/svx_architecture.excalidraw) | Python、native、SV 与数据契约的职责 | [架构](SVX_SPEC.md) |
| [Python 派生 SV](architecture/inheritance_python_extends_sv.excalidraw) | SV 基类、Python 子类和同一对象的绑定 | [继承机制](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md) |
| [SV 派生 Python](architecture/inheritance_sv_extends_python.excalidraw) | Python 部分如何成为真实 SV 继承链的一部分 | [继承机制](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md) |

## 四层不是四份业务实现

SV 拥有时序与硬件耦合行为；Python 拥有场景和检查；SVX 提供受控调用、进程与
传输；SvTypes 定义值、类型、编码和字段存储接口。跨层箭头表示调用或数据依赖，
不表示把时钟、driver 或 monitor 迁到 Python。

类型化通道把事务交给原有 SV 服务，独立观察再交给 Python 检查器。具体工程可看
[Register Lab](../examples/register_lab/README.zh-CN.md) 与
[真实 UART 迁移](../examples/opentitan_uart/README.zh-CN.md)。

## 继承图中的两类关系

同一语言内的继承箭头表示普通 Python 继承或 SV extends；语言之间的箭头表示
对象绑定和生成的调用边界，不是原生跨语言 extends。图中的 Mirror/Proxy 是角色
标签，准确的公开全名由[继承命名规则](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md#public-generated-type-names)定义。

一条跨语言链只有一个最派生 Python receiver 和一个 SV 动态对象。字段驻留按
实际创建的 target 决定，不因为项目里存在某个 SV 子类就把全部 Python 字段搬到 SV。
查看[字段驻留](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md#field-residency)和
[构造路由](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md#constructor-routing)，不要从图上
推断每个框都会另建一个实例。

要让 SV 使用 Python 创建的对象，走[显式发布示例](../examples/cross_language_inheritance/README.zh-CN.md)；
不是随意查询任意 Python 对象。只有 handle 传递需求时，查
[不透明对象与受限 VIF](CROSS_LANGUAGE_HANDLE_ADAPTERS.md)，不必把每个类型都映射成类。

## 选择合适的入口

| 需求 | 入口 |
|---|---|
| 运行第一个 Python 场景 | [基础启动](../examples/milestone_1_basic/README.zh-CN.md) |
| 逐步迁移现有验证环境 | [UART 教程](../examples/opentitan_uart/README.zh-CN.md) |
| UVM factory 对等启动 Python/SV 用例 | [UVMX 准备指南](UVMX_GETTING_STARTED.zh-CN.md) |
| 声明源码变化后如何生成、检查和重编译 | [生成工作流](SVX_GENERATION_WORKFLOW.md) |
| 偶发的层次信号读写与 force/release | [信号示例](../examples/hierarchical_signal_access/README.zh-CN.md) |

图是阅读辅助，不取代源码契约。实现变化时更新图中的关系；接口、构建步骤与
验证范围仍分别由其权威文档负责，避免在图注中维护第二份完整规则。
