# 直接导出已有 SV 声明

[English](README.md)

先按照通用[运行指南](../RUNNING_EXAMPLES.zh-CN.md)准备环境。本例需要 manifest
可选依赖，但不需要手写 manifest、SV declarations JSON、Python Mirror stub，
也不需要为 Python 子类添加声明装饰器。

## 生成

工程配置较多时，可复用本例提供的[自定义 JSON 配置](export-config.json)和
[Python 解析器](config_parser.py)：

```sh
svx export --config examples/sv_export/export-config.json \
  --config-parser examples/sv_export/config_parser.py
```

输出位于 .tmp/configured-export；追加 --check 可只检查而不写入。
脚本路径之后的所有参数都会原样传入解析器的 argv。本例将它们原样返回给
SVX；项目自己的解析器也可以消费自定义参数，不再转发。额外的 --config
文件和直接交给 SVX 的选项应放在 --config-parser 之前。
解析器以 JSON 文件所在目录解析 build_directory/output，再复用原始 filelist。
JSON 的结构只是本例约定，不是 SVX 固定格式；接口和参数优先级见
[配置适配器](../../docs/SVX_GENERATION_WORKFLOW.md#project-configuration-adapters)。

在仓库根目录执行：

```sh
svx inspect -f examples/sv_export/design.f --kind class type
svx export --class export_driver_pkg::Driver \
  -f examples/sv_export/design.f --out examples/sv_export/generated
```

inspect 先列出候选声明，不生成文件；可加 --name 'export_driver_pkg::*'
筛选，或加 --json 查看源码位置及当前导出限制。作用域可选择不代表所有类型和
签名都已支持，具体以[工作流](../../docs/SVX_GENERATION_WORKFLOW.md#direct-sv-export)
中的检查规则为准。

命令复用原始 filelist，自动发现构造参数、字段、方法签名，以及通过 import
继承的 export_base_pkg::Base。只有 Driver 是请求导出的目标，使用方式为：

```python
from svx_mirror.export_driver_pkg import Driver
```

Mode、Packet 会从方法签名和字段中自动发现，生成在同一个 Python module 中，
分别采用公开的 SvTypes Enum、SvStruct 范式。另一包也定义了 Mode，仍保留独立
身份 svx_mirror.export_base_pkg.Mode。若只导出值类型，不需要任何类目标：

```sh
svx export --type export_driver_pkg::Mode export_driver_pkg::Packet \
  -f examples/sv_export/design.f --out .tmp/exported-types
```

这些 Python module 只依赖 SvTypes，不需要 SVX 原生运行库。

编译期参数也可以单独导出，无需类目标：

```sh
svx export --constant 'export_driver_pkg::*' \
  -f examples/sv_export/design.f --out .tmp/exported-constants
```

把 .tmp/exported-constants/python 加入 Python 路径后：

```python
from svx_mirror.export_driver_pkg import COUNT, FLAGS, DEFAULT_PACKET
assert COUNT == 18
assert str(FLAGS) == '10xz'
assert DEFAULT_PACKET.tag.value == 0x81
```

这些是经 SvTypes 编码的求值快照，不是运行期 SV 变量访问。本例包含依赖 import
参数的表达式、字符串、实数、packed struct 和数组参数。package 导出会包含自有
常量，可用 --exclude-constant 排除不需要的快照。生成值已与独立编译的 SV
对同一声明的求值逐项对照。

普通类内的常量保留类命名空间，例如：

```sh
svx export --constant 'export_driver_pkg::Driver::*' \
  -f examples/sv_export/design.f --out .tmp/exported-driver-constants
```

```python
from svx_mirror.export_driver_pkg import Driver, Mode
assert Driver.DEFAULT_SEED == 18
assert Driver.DEFAULT_MODE == Mode.IDLE
```

此时 Driver 只是值命名空间；同时选择类时，快照会挂到实际可调用的镜像类上。
按 package 选择会同时包含两者。嵌套类常量保持嵌套关系；参数化类可使用源码中
完整的默认参数或具体 typedef 别名，见下例。

若要导出包内所有自有类、支持的值类型、编译期常量及函数/task，将 --class 改为
--package export_driver_pkg。
import 仅提供依赖解析上下文，不会自动导出整个 export_base_pkg；只有显式添加
--recursive-packages 才会扩展导出范围。模式匹配、成员筛选和当前边界见
[目标选择](../../docs/SVX_GENERATION_WORKFLOW.md#direct-sv-export)。

大型工程中只导出包内 API 时，可在相同命令中附加 --sv-elaboration packages。
它保留显式源码预处理，跳过设计实例分析和 DUT 实例化触发的 RTL 库请求，
不会停止解析 filelist 中明确列出的 RTL，也不改变仿真编译输入。
完整规则见上述导出流程文档。
同一条导出命令还可加 --incremental，未变化时经校验后复用；追加 --check 时
生成文件和本地缓存都不改写。输入或查找选择变化后自动执行完整流程，也可用
--incremental --refresh-cache 强制完整检查。这不会缓存运行期 Python 用例，
也不代表已经实现只解析某个变化文件。

## 具体类类型别名

[generic_values.sv](generic_values.sv) 定义一个 Config 模板、9 位 Narrow、70 位
Wide、等价别名 Same 和派生类 Child。其 enum/packed struct 保持实际特化后的
位宽；等价别名引用同一个 Python 值类型。

```sh
svx export --constant 'generic_class_constants_pkg::Narrow::*' \
  'generic_class_constants_pkg::Wide::*' \
  -f examples/sv_export/generic.f --out .tmp/exported-generic-values
```

```python
from svx_mirror.generic_class_constants_pkg import Narrow, Wide
assert Narrow.WIDTH == 9 and Wide.WIDTH == 70
assert str(Wide.DEFAULT_PACKET.data.value) == 'x' * 70
```

这里仅生成快照及必要值类型，不生成类工厂。
`--constant 'generic_class_constants_pkg::Config::*'` 使用实际 SV 默认参数；
`--constant 'generic_class_constants_pkg::Child::WIDTH'` 按 SV 继承关系解析常量。
`--type 'generic_class_constants_pkg::Wide::Packet'` 可只导出具体的值类型。
枚举值采用 `WIDTH'(...)`，使字面量位宽与参数化基类型一致。

完整可运行示例：

```sh
svx export --package generic_class_constants_pkg \
  -f examples/sv_export/generic.f --out .tmp/exported-generic
```

沿用下节编译和运行准备，将输入替换为 generic.f、新生成的 mirrors.sv 和
[tb_generic.sv](tb_generic.sv)，顶层为 generic_class_constants_tb；Python 路径
加入新的生成目录。[generic_entry.py](generic_entry.py) 检查两种位宽、SV 原始状态、
task 的四态输出、继承类型，以及 Python 虚方法覆盖和 super()。
也可只选择包级函数/task：

```sh
svx export --callable 'generic_class_constants_pkg::*' \
  -f examples/sv_export/generic.f --out .tmp/exported-generic-calls
```

编译时使用这个生成目录中的桥接，运行相同顶层时加 +SVX_GENERIC_ONLY_CALLABLES。
[generic_calls.py](generic_calls.py) 此时只使用包函数和必要的值命名空间，
不生成或构造类镜像。

## 编译和运行

顶层按 svx_init()、svx_exports_pkg::initialize()、加载/启动 Python 的顺序执行。
生成的 initialize 显式注册工厂和分派器，且可重复调用；原始和生成文件分步分析时，
不要只依赖 package 静态变量初始化来完成注册。

也可以用集成副本方式导出包内 API：

```sh
svx export --package export_driver_pkg --integrated \
  -f examples/sv_export/design.f --out .tmp/sv-export-integrated
```

将 tb_package_calls.sv 中的生成文件 include 改为
`.tmp/sv-export-integrated/sv/source.sv`，只编译这个顶层，不再单独编译 drivers.sv。
使用 CLI 打印的 Python 路径和 artifact manifest，仍执行 package_calls.py，
检查相同3ns结果和 pass marker。原生类、枚举、interface 仅定义一次，调用记录
和桥接在其后生成。两种布局均已实际编译运行。完整规则见
[集成源码输出](../../docs/SVX_GENERATION_WORKFLOW.md#integrated-source-output)。

默认分离布局的步骤如下：

编译顺序是 drivers.sv、tb.sv，include 路径包含仓库根目录。顶层已经包含 SVX
与生成的 mirror，不要重复编译这些 package。仿真进程的 Python 路径需要包含
examples/sv_export/generated/python 和仓库根目录；按照通用指南加载已准备好的
原生运行库。

entry.py 创建真实 SV Driver，读写继承的 count 字段，调用耗时2ns且带有
output/inout 参数的 task，并调用静态方法。
同时验证枚举和 packed struct 的往返，保留结构体中的 X/Z，并分别整体写入和
局部修改真实 SV struct 字段。普通 Python 子类重写 status，
通过 super() 调用 SV 实现，然后发布给 SV。SV 取回 Base 句柄后调用虚方法，
经 Python 覆盖返回108。

预期出现 SV_EXPORT_PYTHON_PASS 和 SV_EXPORT_SV_PASS，仿真在2ns结束。
在原生成命令后加 --check，可同时验证发现与生成结果而不改写文件。
生成目录不纳入 Git。

## 包级函数和 Task

不选择任何类，也可以直接生成函数导入：

```sh
svx export --callable 'export_driver_pkg::*' \
  -f examples/sv_export/design.f --out examples/sv_export/generated
```

保持上述 runtime/include/Python 配置，编译 drivers.sv 后改用 tb_package_calls.sv，
不使用 tb.sv。package_calls.py 直接导入普通函数：

```python
import svx
from svtypes import Int
from svx_mirror.export_driver_pkg import add, step
previous, total = svx.Output(), svx.Inout(10)
assert add(Int(2), Int(3), previous) == 23
step(Int(4), previous, total)
assert previous.value == 1 and total.value == 15
```

所有形参保留原位置，不暴露 response 打包记录。示例还调用无参数 void 函数，
往返包含 X/Z 的 Packet，以 opaque handle 创建和传回未导出的 Other 类对象，
检查真实对象身份，以及返回、读取并传回受限 VIF view。SV 顶层检查包内原始
状态和实际流逝的3ns。预期出现 PACKAGE_CALLS_PYTHON_PASS、PACKAGE_CALLS_SV_PASS。
函数调用复用正常 SVX 调用通道，需要运行中的 SV 端点；上面的纯类型和常量快照
导入则不需要。

## 独立编译单元

可选的 units.f 工程在两个独立编译单元中保留同名的 $unit::UnitLocal 类，宏宽度
分别为5/13。只导出 unit_child_pkg 的 API，其中 Child 继承 unit_base_pkg::Base：

```sh
svx export --package unit_child_pkg --integrated --incremental \
  -f examples/sv_export/units.f --out .tmp/sv-export-units
```

先编译运行库 package，然后按 artifacts.json 的 source_replacements 将 units.f
中的各个原文件逐一换成生成副本。遵循 systemverilog_compile_order，保持各编译
单元独立分析，不要把它们放入一个 include wrapper。选择 tb_independent_units
顶层；它已在加载 unit_entry.py 前调用 svx_exports_pkg::initialize。仿真 Python
路径包含生成的 python 目录和仓库根目录，运行库加载方式与通用指南相同。

SV 探针确认两个同名原生类分别返回11/22、宏没有泄漏。Python 创建 Child 子类，
读写继承字段和本地字段，执行带 output/inout 的2ns task，然后显式发布对象。
SV 获取真实 Child 句柄后调用虚方法，正确进入 Python 覆盖。预期在2ns出现
INDEPENDENT_UNITS_PYTHON_PASS、INDEPENDENT_UNITS_SV_PASS。这里保留但不导出
$unit 类。原始文件配合独立分析的桥接、顶层 include 桥接变体，以及集成替换
构建，均已通过原生工具的独立分析与运行验证。

## 源文件

- [原始 SV 声明](drivers.sv)与[原始 filelist](design.f)。
- [类扩展入口](entry.py)及其 [SV 顶层](tb.sv)。
- [包函数入口](package_calls.py)及其 [SV 顶层](tb_package_calls.sv)。
- [独立单元 filelist](units.f)、[基类单元](base_unit.sv)、[派生单元](child_unit.sv)、
  [Python 入口](unit_entry.py)与 [SV 顶层](tb_units.sv)。
