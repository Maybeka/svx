# 外部类 Handle 与 Virtual Interface

[English](README.md)

本示例展示两种不同的外部 handle 边界：

- `Packet` 是任意 SV class。Python 收到其 SvTypes `RemoteRef`，只保存并原样
  返回，不构造对象也不访问成员。SV 调用者得到同一个基类 handle，动态的
  `TaggedPacket` 实例身份不会丢失。
- `virtual example_bus_if.master` 会生成 Python 类
  `svx_vif.example_bus_if.master.Master`。它的 `write_data`、`write` 与 `read`
  完全由 modport 可见成员生成，不需要维护第二份 Python 访问白名单。

共享的构建输入、runtime 加载和通过/失败判定见[示例运行指南](../RUNNING_EXAMPLES.zh-CN.md)。

## 生成

manifest 只声明一个需要生成的 Python endpoint。外部 handle adapter 与 VIF view
由其中的类型声明自动发现。

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-manifest \
  --python-module examples.foreign_handles.python_api \
  --sv-source examples/foreign_handles/bus_if.sv \
  --out examples/foreign_handles/generated/handles.json

PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest examples/foreign_handles/generated/handles.json \
  --sv-source examples/foreign_handles/bus_if.sv \
  --python-out examples/foreign_handles/generated/python \
  --sv-out examples/foreign_handles/generated/mirrors.sv \
  --artifact-manifest examples/foreign_handles/generated/svx-artifacts.json
```

VIF 发现需要可选的 manifest frontend 依赖；执行生成的机器应安装带
`manifest` extra 的 SVX。

## 运行

通过正常的 SVX DPI 集成流程编译 `tb.sv`、SvTypes 的 SV runtime package、
`svx_pkg.sv` 与 `generated/mirrors.sv`。运行时将
`examples/foreign_handles/generated/python`、`python` 和项目根目录加入
`PYTHONPATH`。

`tb.sv` 验证 class handle 的动态实例身份、Python 经 VIF 进行的信号写入和
function 调用，以及返回 VIF 在 SV 中仍可继续使用。

生命周期、null 和不支持操作的规则见
[handle adapter 契约](../../docs/CROSS_LANGUAGE_HANDLE_ADAPTERS.md)。
