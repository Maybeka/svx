# 导出嵌套 SV 类

[English](README.md)

类桥接示例先按通用[运行指南](../RUNNING_EXAMPLES.zh-CN.md)准备运行库；下文纯类型
与常量快照只需要 manifest CLI 和 SvTypes，不需要原生运行库。本例导出原始
package 内的嵌套类，不把用户类搬迁或复制到生成的 package 中。

## 生成

从仓库根目录执行：

```sh
svx export --class 'scoped_classes_pkg::*::Inner' scoped_classes_pkg::Outer_Inner \
  -f examples/sv_scoped/design.f --out examples/sv_scoped/generated
```

只有这四个类是生成目标。构造、方法、字段、跨 package 的 Base 继承链，
以及依赖的包级、类内值类型会自动发现。若需要导出包内自有声明，也包含 Outer、
OtherOuter 本身，则改用 --package scoped_classes_pkg。
相同命令可附加 --sv-elaboration packages，只分析包内 API；仿真仍编译原始
SV 输入，不使用内部分析顶层。

```python
from svtypes import Int
from svx_mirror.scoped_classes_pkg import Outer, OtherOuter, Outer_Inner
first = Outer.Inner(Int(3))
second = OtherOuter.Inner(Int(3))
```

两个 Inner 的原生和 Python 类型身份互不混淆，公开全名分别为
svx_mirror.scoped_classes_pkg.Outer.Inner、
svx_mirror.scoped_classes_pkg.OtherOuter.Inner。
`__name__` 仍为 Inner，`__module__` 为 svx_mirror.scoped_classes_pkg，
`__qualname__` 保留词法作用域。Outer_Inner 与 Outer.Inner 也不会因下划线展平
而冲突，包括它们的私有 SV helper 名称。使用
`from svx_mirror.scoped_classes_pkg import Outer` 后访问 Outer.Inner；
Outer 是类/类型名字空间，不是可单独 import 的 Python 子 module。
另一个 outer.Inner 与 Outer.Inner 仅大小写不同，内部文件和 include guard
在大小写不敏感的文件系统上也不会混淆它们。

只选择 Inner 时，Outer 只是名字空间容器，不会自动成为可构造的原生镜像，
例化 Inner 也不需要先例化 Outer。若同时选择 Outer，其真实镜像类会持有 Inner
这个类属性。内部定义文件仅重新导出同一个类对象，不添加第二层 wrapper，
也不定义第二份原生类型。artifact manifest 记录公开全名。

## 编译和运行

依次编译 [classes.sv](classes.sv)、[tb.sv](tb.sv)，include 路径包含仓库根目录。
顶层已包含运行库和生成桥接，不要重复编译对应 package。仿真进程 Python
路径需要包含 examples/sv_scoped/generated/python 和仓库根目录，并加载已准备
的原生运行库。

[entry.py](entry.py) 直接构造 Inner，读写继承的 count 字段，调用带 output 的
2ns task、静态函数，往返 Packet 并局部修改原生 packed 字段，同时保留 X/Z。
PythonInner 使用普通 Python 继承覆盖 status。SV 顶层取回原始
scoped_base_pkg::Base 句柄，检查虚调用返回121。
预期在2ns出现 SCOPED_PYTHON_PASS、SCOPED_SV_PASS。
原生成命令附加 --check，可不改写文件地验证发现和生成结果。

Outer.LocalMode、Outer.LocalPacket 保留原生类内类型身份。entry.py 通过
echo_local 往返 packed struct，并修改其原生 mode 字段，保留 flags 中的 X/Z。
未选择 Outer 时它们属于名字空间；选择 Outer 时它们属于同一个 Mirror 类。
仅导出这组值类型而不生成任何可构造类，可执行：

```sh
svx export --type scoped_classes_pkg::Outer::LocalPacket \
  -f examples/sv_scoped/design.f --out examples/sv_scoped/generated-values
```

从 svx_mirror.scoped_classes_pkg 导入 Outer 后使用 Outer.LocalPacket；依赖的
Outer.LocalMode 枚举自动生成。这个纯类型导入只需 SvTypes，无需运行仿真。
## 集成副本模式

```sh
svx export --package scoped_classes_pkg --integrated \
  -f examples/sv_scoped/design.f --out .tmp/sv-scoped-integrated
```

将 tb.sv 中的生成文件 include 改为 `.tmp/sv-scoped-integrated/sv/source.sv`。
此时只编译 tb.sv，不再单独编译 classes.sv，因为副本中已包含原始 package。
Python 路径和 artifact 配置分别使用 .tmp/sv-scoped-integrated/python、该目录下
的 artifacts.json。仍执行同一个 entry.py，检查相同虚方法回调和 pass marker。
包级变体还构造 Outer.Alias：它是原生 Outer.Inner 的类别名。分离桥接和集成
副本两种模式均已实际编译运行。

当前尚未覆盖 module/interface/program 的实例绑定，以及带自动值记录的多次
交替跨语言继承集成布局。
当前边界见[导出规则](../../docs/SVX_GENERATION_WORKFLOW.md#direct-sv-export)。

[原始 filelist](design.f)。

## 无 Package 的值声明

[unit_values.sv](unit_values.sv) 包含单元级枚举、packed struct、类型别名、动态
数组别名、常量及 Holder 中的公开嵌套类型：

```sh
svx export --type '$unit::*' --constant '$unit::*' \
  --sv-source examples/sv_scoped/unit_values.sv --out .tmp/unit-values
PYTHONPATH=.tmp/unit-values/python python examples/sv_scoped/unit_values.py
```

[unit_values.py](unit_values.py) 不加载 SVX 原生库，即可验证公开 SvTypes 声明、
别名身份、packed X/Z 常量和嵌套类型；预期出现 UNIT_VALUES_PYTHON_PASS。
可选 [SV 顶层](tb_unit_values.sv) 在自己的单元中包含原声明，验证相同原生值；
预期出现 UNIT_VALUES_NATIVE_PASS。两侧均已在远端运行。请求 Holder.Payload
不会额外生成可构造的 Holder 类镜像。

导入路径为 svx_mirror_unit.unit_0；独立单元使用不同索引。inspect --json 的
compilation_unit_index 给出归属，重名时可用 '$unit[1]::Mode' 消歧。
分组、归属和仍未完成的运行时记录布局，以
[单元值导出规则](../../docs/SVX_GENERATION_WORKFLOW.md#compilation-unit-values)为准。

## 实例作用域的类型快照

[instance_values.sv](instance_values.sv) 在 module、interface、program 和 generate
中声明类型与常量。按唯一的[生成流程](../../docs/SVX_GENERATION_WORKFLOW.md#instance-owned-values)
复用[原始 filelist](instance_values.f) 导出。把生成目录
.tmp/instance-values/python 与仓库根目录加入 Python 路径，然后运行：

```sh
python -m examples.sv_scoped.instance_values
```

[Python 示例](instance_values.py) 检查标准 SvTypes enum/struct 编解码、typedef
别名、嵌套 Holder.Tag、相同参数的独立实例和非默认位宽，不加载原生运行库，
输出 INSTANCE_VALUES_PYTHON_PASS。编译运行原始 SV 源码，预期在1ns输出
INSTANCE_VALUES_NATIVE_PASS；五条 INSTANCE_VALUE 和两条 INSTANCE_INDEX
结果已在远端与 Python 快照逐项比较。不需要编译任何生成的 SV 桥接文件。
参数化 enum 的枚举值使用显式 W 位转换；program 自身保留2ns进程，避免早于
顶层1ns检查结束仿真。这里不包含实例局部命名类型在类字段和方法中的运行时
绑定；该路径由下面的独立示例验证。

## 实例局部类型的运行时传输

[SV 源码](instance_runtime_values.sv)、[filelist](instance_runtime_values.f)和
[Python 入口](instance_runtime_values.py)使用三个原始模块实例，位宽分别为
8、8、13。按[权威流程](../../docs/SVX_GENERATION_WORKFLOW.md#instance-owned-values)
只选择 Driver 类，CLI 自动收集每个实例的 Mode、Payload、Word、Packets 和
Modes，无需用户重复列出类型。按 artifacts.json 的编译顺序编译替换源码和启动
单元，并加入生成的 Python 路径；SV 顶层负责初始化桥接并启动 Python 入口。

Python 创建原生对象、局部修改结构体字段，传递枚举、结构体、定长数组与队列，
并执行三个各耗时1ns的 output/inout task。Python 子类覆盖虚方法后，将实例交给
SV 基类句柄调用，包含 super() 回调原始 SV 实现的路径。应同时出现
INSTANCE_RUNTIME_VALUES_PYTHON_PASS 和 INSTANCE_RUNTIME_VALUES_NATIVE_PASS。
本示例已在远端执行通过；等价的 interface、program 场景也已通过。
generate 局部命名类型的运行时组合及跨实例依赖不属于此示例已验证的范围。

## 无 Package 的类

[unit_classes.sv](unit_classes.sv) 直接在编译单元中声明 Driver，继承同单元的
UnitBase，再继承真实 package 中的 Base。[原始顶层](tb_unit_classes.sv) 将它
include 到同一单元。
直接复用[工程 filelist](unit_classes.f)：

```sh
svx export --class Driver -f examples/sv_scoped/unit_classes.f \
  --sv-elaboration packages --out .tmp/unit-classes
```

无需 declarations JSON、stub 或额外 wrapper package。命令自动生成
.tmp/unit-classes/sv/source.sv 和 sv/exports.sv。先编译准备好的 SvTypes、SVX
运行时 package，再按 artifact 中的顺序编译这两个生成输入，替换原始顶层。
不要另外编译 unit_classes.sv，因为副本中已包含其原生声明。Python 路径加入
.tmp/unit-classes/python 和仓库根目录，并使用本次 artifacts.json 与原生运行时。
顶层例化一个 svx_exports，在 svx_init 后、加载 Python 前调用 exports.initialize。
独立编译单元需要显式建立这条注册连接，不依赖未引用全局变量的初始化副作用。

[unit_classes.py](unit_classes.py) 从 svx_mirror_unit.unit_0 导入 Driver，创建
原生实例、访问和修改继承/本层字段，调用带 output/inout 的2ns task，以及
Driver、本单元基类和 package 基类分别声明的静态函数，
并使用普通 Python 继承覆盖虚方法。顶层以原始 SV Driver 句柄取得 Python
创建的子类，验证虚调用返回108。预期在2ns出现 UNIT_CLASSES_PYTHON_PASS 和
UNIT_CLASSES_NATIVE_PASS。这套实际 CLI 生成、检查、原生运行已在远端通过；
两个独立编译单元中的同名 Driver 也已通过源代码自动发现与仿真，包括非默认
13位泛型祖先字段的访问。
只有 Driver 是导出目标；基类信息和静态分派作为依赖纳入，不额外生成基类的
构造目标。

索引选择器、编译单元分组、启动及仍未完成的 owner-local 布局，以
[单元类导出规则](../../docs/SVX_GENERATION_WORKFLOW.md#compilation-unit-classes)为准。

## 嵌套编译单元类

[原生声明](unit_nested.sv)、[顶层](tb_unit_nested.sv)和
[Python 入口](unit_nested.py)使用同一套 owner-local 架构：

```sh
svx export --class '$unit::*::Inner' Outer_Inner Outer::Alias \
  --type UnitModes -f examples/sv_scoped/unit_nested.f \
  --sv-elaboration packages --out .tmp/unit-nested
```

先编译准备好的 SvTypes/SVX 运行时 package，再编译输出提示中的源码副本和
.tmp/unit-nested/sv/exports.sv；不要重复编译原始顶层或声明。Python 路径加入
.tmp/unit-nested/python 和仓库根目录，使用本次 artifacts.json 与原生运行时运行
tb_unit_nested。顶层已经包含统一启动实例与 initialize 调用。

只生成选择的五个类视图。Outer、OtherOuter 是 Python 命名空间，不是构造目标；
Outer.Inner、OtherOuter.Inner、outer.Inner、Outer_Inner 保持独立，Outer.Alias
保留被选择的原生类别名。Outer 的原始构造函数被设计为一旦调用就失败，因而
可直接确认 Inner 的创建没有分配外层对象。

根级 UnitMode、UnitPacket 依赖自动发现，仍是真实 SvTypes 枚举/packed struct；
显式 --type 请求公开 UnitModes 容器别名，导出类不会顺带公开所有非名义 typedef。
入口将三者传入原生方法，验证 X/Z 局部字段更新、2ns output/inout task、静态
方法及 Python 虚方法覆盖。SV 顶层取得原始 Outer::Inner 句柄，验证回调108。
Inner 中另一个 UnitMode typedef 也验证了显式 $unit 类型不会被局部同名声明遮蔽。
类内 Inner.State、Inner.Packet 同样会自动发现。派生类另行声明同名 State，
枚举成员名字也相同但值不同；继承的方法和字段仍使用 Outer.Inner 原始类型，
并通过真实枚举调用及 packed 字段的 X/Z 局部更新验证两者不会混淆。
预期在2ns出现 UNIT_NESTED_PYTHON_PASS 和 UNIT_NESTED_NATIVE_PASS。

这套 CLI、--check、原生运行已在远端通过。独立单元索引、仍待支持的特化名义
类型及实例作用域布局，以
[单元类权威流程](../../docs/SVX_GENERATION_WORKFLOW.md#compilation-unit-classes)为准。

## 实例内的类

按真实模块实例选择，不要把源模块定义名当成实例路径：

```sh
svx export --class 'tb_instance_classes.*.Driver' \
  -f examples/sv_scoped/instance_classes.f --out .tmp/instance-classes
```

不需要声明 JSON、原型 package 或 Python stub。CLI 直接读取原工程输入，
计算各实例的实际类型，保留原始类名：

```python
from svx_mirror_instance.tb_instance_classes.a.classes import Driver as DriverA
from svx_mirror_instance.tb_instance_classes.b.classes import Driver as DriverB
from svx_mirror_instance.tb_instance_classes.c.classes import Driver as DriverC
```

a、b 参数相同但绑定各自实时 owner 上下文；c 的字段为13位，a、b 为8位。
原始 Base、Driver 仍在 SV 中，绑定适配器以类型参数接收真实类型，不移动或
重新声明用户类。只有选择的三个 Driver 是生成目标，Base 只是继承上下文。

先编译 SvTypes/SVX 运行时 package，再按照 artifacts.json 中的
systemverilog_compile_order 编译生成输入。用 source replacement 替换原始顶层
输入，不要把两份一起编译。示例顶层已有统一 svx_exports 实例，在 svx_init 后、
加载 Python 前调用 initialize。

instance_classes.py 验证构造、继承字段/虚方法、参数位宽、owner 实时状态读写、
自身及继承的静态方法和2ns output/inout task；随后把 PythonDriver 作为原始 SV Driver 句柄
发布，由 SV 验证 Python 覆盖方法。预期在2ns出现 INSTANCE_CLASSES_PYTHON_PASS、
INSTANCE_CLASSES_NATIVE_PASS。这条源码直接 CLI、检查、编译、仿真路径已远端通过。

## Generate 作用域内的类

源码：[设计](generate_classes.sv)、[顶层](tb_generate_classes.sv)、
[Python](generate_classes.py)、[filelist](generate_classes.f)。

直接复用原始 filelist，选择实际 lane 中的类：

```sh
svx export --class 'tb_generate_classes.*.lane[*].active.Driver' \
  -f examples/sv_scoped/generate_classes.f --out .tmp/generate-classes
```

三个模块实例各包含两条 lane，共生成六个 Driver 视图，保留独立的 owner 上下文
及8/9/13/14位原生字段。内部 active 块故意把 LANE 遮蔽成99，但 INDEX、字段位宽
和导出选择仍对应正确的外层 lane。Base 只是继承上下文，不是额外的生成目标；
用户不需要原型、声明 JSON，也不需要移动源类。

例如 b.lane[1].active 的导入是：

```python
from svx_mirror_instance.tb_generate_classes.b.svx_scope_4_lane_p1.active.classes import Driver
```

先编译运行时 package，再按照 artifact 的 systemverilog_compile_order 编译。
替换原始顶层输入，不要同时编译两份。顶层仍在 svx_init 后调用统一的
svx_exports.initialize。完整适配器留在原 generate owner 内，不把原生类类型传到
外部 bind 模块中；父参数守卫在子 generate 项之前捕获，保留词法遮蔽和真实索引。

generate_classes.py 验证构造、实时字段/模块状态、自身及继承静态方法和1ns
output/inout task，随后发布六个对象。SV 顶层在每个 lane 内把对象转换为原始
Driver 句柄，检查虚分派确实调用 PythonDriver。预期在1ns出现
GENERATE_CLASSES_PYTHON_PASS 和 GENERATE_CLASSES_NATIVE_PASS。普通源码 CLI、
--check、原生仿真已远端通过，涵盖模块、接口和匿名 generate 块变体。
尚未完成的源码布局见[权威流程](../../docs/SVX_GENERATION_WORKFLOW.md#generate-owned-classes)。

### Generate 内的复合值

源码：[SV 工程](generate_runtime_values.sv)、[Python 场景](generate_runtime_values.py)、
[原始 filelist](generate_runtime_values.f)。

```sh
svx export --class 'tb_generate_runtime_values.*.lane[0].Driver' \
  -f examples/sv_scoped/generate_runtime_values.f --out .tmp/generate-runtime-values
```

仅选择 Driver 即可自动收集它的类内 enum、packed struct 及必要容器别名，不需要
声明 JSON 或额外列出类型。Python 从各自 owner 模块取得 Driver.Mode 和
Driver.Payload；原有8/13位 SV 类、变量和作用域保持原位。按上文编译 artifact
给出的替换源码与启动单元，不同时编译原文件。

场景检查 enum/struct 字段、enum 队列、struct 定长/动态数组、字符串关联数组和
嵌套关联数组队列的整值与局部修改。原始 SV getter 验证写入和未修改的兄弟元素，
包括 X/Z 的保留。每个 owner 执行一个耗时1ns的 output/inout task。
PythonDriver 覆盖 enum、struct、数组虚方法，再通过既有
publish_object/SVX_GET_OBJECT 显式交接，由 SV 使用原 Driver 句柄回调同一实例，
其中包含 Python super() 调用。

原始 filelist 导出、只读检查、编译和运行均已在远端通过。2ns 时应出现
GENERATE_RUNTIME_VALUES_PYTHON_PASS 和 GENERATE_RUNTIME_VALUES_NATIVE_PASS。
这些布局的通过不代表任意 owner 参数化或跨 owner 类型依赖都已完成，完整边界见
[权威流程](../../docs/SVX_GENERATION_WORKFLOW.md#generate-owned-classes)。

## Program 作用域内的类

源码：[program](program_classes.sv)、[顶层](tb_program_classes.sv)、
[Python](program_classes.py)、[filelist](program_classes.f)。

```sh
svx export --class 'tb_program_classes.*.Driver' \
  -f examples/sv_scoped/program_classes.f --out .tmp/program-classes
```

三个 program 的 Driver 导入路径为
svx_mirror_instance.tb_program_classes.<a/b/c>.classes.Driver。原始类仍在 program
内部，适配器按实际 owner 注册，然后复用已有 SV 注册表完成字段、构造和方法分派。
顶层不会越过 program 的访问规则去读变量或按层级调用局部函数。

先编译运行时 package，再按照 artifact 的源码替换和编译顺序编译。顶层仍在
svx_init 后调用统一 svx_exports.initialize，再加载 Python。选中 program 时
initialize 为 task，通过 SV 事件等待 program 声明注册，不推进仿真时间；顶层
明确检查启动后时间仍为零。仅 module/interface 时仍生成 function 初始化入口。

Python 通过导出方法配置状态，再构造对象，验证相同参数实例的独立 owner、
8/13位字段、继承静态方法及1ns output/inout task。verify_published 在 SV 中使用
原始 Driver 句柄调用 Python 覆盖方法。预期在1ns出现 PROGRAM_CLASSES_PYTHON_PASS
和 PROGRAM_CLASSES_NATIVE_PASS。普通 CLI、--check、原生仿真已远端通过。
初始化、生命周期和剩余布局边界见[权威流程](../../docs/SVX_GENERATION_WORKFLOW.md#program-owned-classes)。
