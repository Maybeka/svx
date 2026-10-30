# 寄存器项目的可选 UVM 启动

[English](README.md)

首次准备 UVMX 的路径和默认基类用法见[准备和使用 UVMX](../../../../docs/UVMX_GETTING_STARTED.zh-CN.md)。
下面复用的是已有寄存器项目的数据和继承契约，不表示默认用例需要重新生成这些内容。

Python 用例名在启动时动态注册，不再生成逐用例 SV 类。首次构建后，新增使用
已编译基类的 Python Test，直接通过新的 `+UVM_TESTNAME` 启动；保持原二进制
和 native 库不变，不需要重新生成或编译 SV。

这是临时 UVMX 源码中的一个启动适配，不改变[核心寄存器项目](../../../../examples/register_lab/README.zh-CN.md)
的数据、driver、monitor 或继承实现。核心项目不导入 UVMX，也不需要 UVM。
本目录只在源码开发中使用；临时 UVMX 尚未从 SVX 拆为独立项目。

## 生成与编译

先按核心项目说明完成生成和运行库构建。将 `incubator/uvmx/python` 加入 Python
导入路径，再从仓库根生成可复用的 SV 基类注册包：

```sh
export PYTHONPATH="$PWD/incubator/uvmx/python:$PWD/examples/register_lab/generated/python:$PWD:${PYTHONPATH:-}"
python incubator/uvmx/tools/uvmx_gen.py \
  --module incubator.uvmx.examples.register_lab.python_test \
  --package register_lab_uvmx_pkg \
  --sv-out incubator/uvmx/examples/register_lab/generated/tests.sv \
  --artifact-manifest incubator/uvmx/examples/register_lab/generated/artifacts.json
```

保持核心项目的 `SVX_ARTIFACT_MANIFEST` 与原生库加载配置。编译本目录的 `tb.sv`
替代核心 `tb.sv`，提供 UVM package、UVM macros 及 `incubator/uvmx/sv` 的 include
目录。所有编译输入使用一致的默认 1 ns / 1 ps 时间设置，并启用核心项目所需的信号访问。
不要同时编译两个 top；本入口包含并复用核心 top。

## 对等选择

- `+UVM_TESTNAME=register_lab_python_test`：UVM factory 选择 Python 声明的 Test。
- `+UVM_TESTNAME=register_lab_extended_test`：选择 `PythonExtendedTest(PythonTest)`，
  验证 Python 独有状态、新增 build 回调和 Python `super()` 复用场景。
- `+UVM_TESTNAME=register_lab_sv_test`：同一 factory 选择 `legacy_test.sv` 定义的 SV Test。

两者的 run phase 都运行同一个寄存器 smoke，并保留核心场景的通过检查。
Python 定义的用例应出现 `REGISTER_LAB_UVMX_PASS`；SV 定义的用例应出现
`REGISTER_LAB_UVM_PASS`。两者都应出现 `REGISTER_LAB_CHECKER_PASS`、
`REGISTER_LAB_POLICY_CLOSE_PASS` 和 `REGISTER_LAB_PYTHON_PASS`，没有 UVM/SVX 错误。
扩展用例还应输出 `REGISTER_LAB_UVMX_EXTENDED_BUILD_PASS` 和
`REGISTER_LAB_UVMX_EXTENDED_PASS`。

这里的 SV Test 使用 SVX 启动同一 Python 场景，不是把 UVM scheduler 放到 Python。
UVMX 仅映射 Test 和同步 phase callbacks；UVM 仍拥有 factory、phase、objection 与退出。
`run_test()` 在零时刻启动，独立 SV 复位进程运行；driver/monitor 等待复位。
场景等待三个环境完成通知之后才结束。
启动接入先调用 uvmx_init 完成注册，再直接调用原生 run_test；UVMX 不改变 UVM
的退出策略。原生 UVM 默认结束仿真，不依赖 run_test 之后的 shutdown。
因此不会依赖核心 top 在 UVM 结束后的 join 或报告代码。

深层 UVM 类体系与完整 Python UVM 兼容不属于本例。
