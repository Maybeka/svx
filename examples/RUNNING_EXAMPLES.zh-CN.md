# 运行 SVX 示例

[English](RUNNING_EXAMPLES.md)

这是本目录所有示例共用的操作步骤。各示例 README 还会给出自己的 Python
入口、生成文件和预期行为；运行时应同时遵守该 README 的说明和本指南。

## 1. 准备开发环境

以下命令在仓库根目录执行。开发时使用相邻的 SvTypes checkout 作为数据契约来源：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ../svtypes
python -m pip install -e '.[dev,manifest]'
```

构建 native runtime：

```sh
cmake -S . -B build
cmake --build build -j2
```

安装、构建和仿真内嵌 Python 应使用同一解释器。存在多个 Python 时，在首次
CMake 配置加入 `-DPython3_EXECUTABLE="$(python -c 'import sys; print(sys.executable)')"`；
切换解释器使用新 build 目录，避免旧 ABI 缓存。

分层信号示例还要求 runtime 能使用目标工具的 VPI header，并启用 direct VPI
service：

```sh
cmake -S . -B build \
  -DSVX_SIMULATOR_INCLUDE_DIR=/path/to/simulator/include \
  -DSVX_REQUIRE_DIRECT_VPI=ON
cmake --build build -j2
```

## 2. 生成声明的产物

在编译选定示例的 testbench 前，先执行该示例 README 中的生成命令。类型和
channel helper 生成一个 SV 源文件；继承示例同时生成 SV 源文件和 Python package。
按示例 README 的规定，把这些生成物加入编译和导入输入。

生成也应进入项目 build gate。如果 manifest 来自源码声明发现，应先执行
原来的 `inheritance-manifest` 命令并加 `--check`，使用相同模块、声明及
源码/解析选项。发现检查通过后，再检查继承生成物：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest <example>/inheritance.json \
  --python-out <example>/generated/python \
  --sv-out <example>/generated/inheritance_mirrors.sv \
  --artifact-manifest <example>/generated/svx-artifacts.json \
  --check
```

产物检查只验证其与给定 manifest 是否一致，不会重新发现已编辑的 Python
声明。对旧 manifest 刷新输入摘要不能代替发现检查。手写 manifest 没有
发现命令，需先显式更新契约，再检查产物。两阶段命令和仅修改方法体的流程见
[迭代开发](../docs/SVX_GENERATION_WORKFLOW.md)。

## 3. 编译与加载

从已安装的 SVX package 查询与工具无关的集成输入：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx sv-files
PYTHONPATH=python:../svtypes/python:. python -m svx compile-flags
SVX_LIB_DIR="$PWD/build" PYTHONPATH=python:../svtypes/python:. python -m svx libs
```

编译所选示例的 `tb.sv`、`svx sv-files` 输出的文件，以及该示例 README 所列的
生成 SV 文件。使用目标工具的正常 DPI 机制加载 `svx libs` 输出的 library。
若 `tb.sv` 已用 include 包含这些文件，只编译该顶层并提供 include 路径，不要
再把同一 package/interface 作为独立源文件重复编译。寄存器小项目采用这种方式，
也要求直接 VPI 运行库。按其 README 设置 `SVX_ARTIFACT_MANIFEST`。

仿真进程至少应有以下 import path：

```text
<repository root>:<repository root>/python:<repository root>/../svtypes/python
```

继承示例还要追加其 `generated/python` 目录。不要用 Python `async`、宿主机线程或
宿主机 timer 替换仿真器的调度模型。

## 4. 运行和判定结果

按常规方式运行已编译的 testbench。正常示例成功时会在没有 `ERROR` display 或
fatal report 的情况下，依次到达 `svx_shutdown()` 与 `$finish`。
故意失败的用例不同：其 README 规定的具体 fatal diagnostic 才是预期结果。
例如寄存器项目的 `corrupt_read` 和 `function_wait`。同时拒绝正常通过标记、
超时和崩溃；进程退出码为零或非零都不能单独证明负面用例通过。

testbench 是初始化和关闭的唯一所有者。Python 测试不得自行调用 `svx_shutdown()`。

## 5. 快速源码检查

进行仿真前，仓库的 Python contract test 可验证不依赖活动仿真的 generator、
descriptor、manifest 和示例：

```sh
PYTHONPATH=python:../svtypes/python:. .venv/bin/python -m pytest -q
```
