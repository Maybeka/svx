# 运行 SVX 示例

[English](RUNNING_EXAMPLES.md)

这是本目录所有示例共用的操作步骤。各示例 README 还会给出自己的 Python
入口、生成文件和预期行为；运行时应同时遵守该 README 的说明和本指南。

## 1. 准备开发环境

以下命令在仓库根目录执行。开发时使用相邻的 SvTypes checkout 作为数据契约来源：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pytest
PYTHONPATH=../svtypes/python python -m pip install -e .
```

构建 native runtime：

```sh
cmake -S . -B build
cmake --build build -j2
```

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

生成也应进入项目 build gate。继承产物可用下列形式检查是否过期：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest <example>/inheritance.json \
  --python-out <example>/generated/python \
  --sv-out <example>/generated/inheritance_mirrors.sv \
  --artifact-manifest <example>/generated/svx-artifacts.json \
  --check
```

## 3. 编译与加载

从已安装的 SVX package 查询与工具无关的集成输入：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx sv-files
PYTHONPATH=python:../svtypes/python:. python -m svx compile-flags
SVX_LIB_DIR="$PWD/build" PYTHONPATH=python:../svtypes/python:. python -m svx libs
```

编译所选示例的 `tb.sv`、`svx sv-files` 输出的文件，以及该示例 README 所列的
生成 SV 文件。使用目标工具的正常 DPI 机制加载 `svx libs` 输出的 library。

仿真进程至少应有以下 import path：

```text
<repository root>:<repository root>/python:<repository root>/../svtypes/python
```

继承示例还要追加其 `generated/python` 目录。不要用 Python `async`、宿主机线程或
宿主机 timer 替换仿真器的调度模型。

## 4. 运行和判定结果

按常规方式运行已编译的 testbench。正常示例成功时会在没有 `ERROR` display 或
fatal report 的情况下，依次到达 `svx_shutdown()` 与 `$finish`。
`milestone_1_error` 和明确命名为 expected-failure 的 testbench 不同：其 README
规定的 fatal diagnostic 才是预期结果。

testbench 是初始化和关闭的唯一所有者。Python 测试不得自行调用 `svx_shutdown()`。

## 5. 快速源码检查

进行仿真前，仓库的 Python contract test 可验证不依赖活动仿真的 generator、
descriptor、manifest 和示例：

```sh
PYTHONPATH=python:../svtypes/python:. .venv/bin/python -m pytest -q
```
