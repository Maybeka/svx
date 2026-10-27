# OpenTitan UART 迁移验证

[English](RESULTS.md)

上游固定版本：`724f378edf920eb5bc536a0d136158963c44186b`，上游工作树保持未修改。
验收日期：2026-10-25。
分别记录原 SV 基线、SVX 接入和独立 Python 检查，不相互替代。

| 门禁 | 场景 | 验收 |
| --- | --- | --- |
| 原始 SV 基线 | smoke、tx_rx、FIFO full/overflow/reset、parity error、loopback、interrupt；seed 1 | 8 项全通过 |
| 混合模式 | seed 1/2/3 | 每项 10 TX、10 RX、10 次 Python 读回检查 |
| Python 主导模式 | seed 1/2/3 | 每项 64 TX、64 RX、64 次 Python 读回检查；关闭原 UART 数据 scoreboard |
| Python 检查器负向门禁 | 捕获的 TX 数据损坏、丢失、乱序 | 各自出现 `UART_MODEL_STREAM TX` 并终止，不得有 PASS 标记 |
| 扩展构建中的原 SV 用例 | smoke、tx_rx、FIFO reset、parity error | 不启动 Python，原 SV 路径仍通过 |
| 全字节 Python 扩展 | seed 1/2/3 | 每项 512 TX、512 RX、512 次读回 |
| 构建后新增 Python 模块 | `rotated_bytes_case`，seed 1 | 512 TX、512 RX、512 次读回，不重新生成或编译 |

17 项接入门禁全部符合验收条件，其中包括 3 项故意触发 checker 错误的控制场景。
原始 8 项 SV 基线单独统计，不混入这 17 项。

正常用例必须有 `TEST PASSED CHECKS`、对应 `UART_MIGRATION_PASS` 标记，且 UVM
warning/error/fatal 均为 0。负向用例必须是指定 Python checker 错误并走 SVX fatal
路径；超时、崩溃或无关异常不算通过。这一 UVM 统计不表示编译阶段没有诊断。

冻结检查覆盖仿真二进制、native SVX library、生成的 SV/Python 和 artifact manifest，
同时核对内容及修改时间。原基线二进制单独保留。
最终审计确认 17 份日志对应同一组 6 个冻结构建文件，并确认新增 rotated 用例模块
的加入时间晚于二进制构建。

## 复用原编译配置的追加验证

在独立输出目录中，直接读取原构建系统的实际编译 argv 和工作目录，再由导入层
展开原 filelist。读取 235 个上游源文件（含原工具隐式 UVM 库）、27 个 include
目录和 9 个宏；仅追加本例的 bridge 后，共 236 个源输入、517 个实际源码依赖。
未改动上游源码、清单或原基线构建。

新生成物实际重新编译后，seed 1 的混合模式、Python 主导模式、全字节 Python
用例、保留的 SV smoke 和指定 TX 数据损坏检查全部符合验收，共 5 项。这是前述
17 项迁移验收之外的一次独立构建输入集成验证，不替代或扩大原迁移范围。
其中全字节用例再次检查 512 TX、512 RX 和 512 次读回。

五份日志均对应同一组 6 个冻结构建文件，内容与修改时间一致。随后只改变导入
命令中的宏定义，`--check` 正确报告构建配置过期，且没有改写生成物；使用原配置
的只读检查通过。原始 8 项 SV 基线及未修改的上游工作区也单独重新审计。
本次编译配置导入回归在远端 16 项通过；更新后的本地完整 Python 测试为
1020 项通过，无 skip/xfail。

## 按需库搜索的追加验证

四项实际编译器对照覆盖：原目录顺序、反转目录顺序、反转扩展名顺序，以及
第一个目录的次选扩展名与第二个目录的首选扩展名交叉。SVX 与原工具均按目录
优先、目录内扩展名次序选择相同文件；选中单元的下层依赖也递归载入。库目录
中的无关错误源码未被读取。还单独验证了未指定扩展名时的精确文件名搜索，以及
共享编译单元中宏对选中库源码的可见性。

随后在原 UART 构建中加入这组库搜索上下文与一个独立的库选择检查顶层，重新
导出原来的类、生成桥接并实际编译。seed 1 的混合模式、Python 主导模式、全字节
Python 用例和原 SV smoke 共 4 项通过。每次仿真还确认实际库单元选择正确；全字节
用例仍为 512 TX、512 RX、512 次读回。

四份运行记录共享同一组 6 个冻结构建文件；生成的 SV/Python 类代码与之前的
导出逐字节一致。修改未使用的库文件后，只读检查通过；不改变清单或命令、仅
新增更高优先级的候选文件时，只读检查正确拒绝过期结果，且未改写生成物。

这些检查验证按需源文件解析与类导出，不将库内额外声明自动加入生成目标，也不
表示支持所有工具专有的库配置或配置块绑定语法。
该阶段远端库搜索/配置回归为 23 项通过，本地完整 Python 测试为 1027 项通过，
无 skip/xfail。

## 接入中确认的问题

- 多个 SV 进程的 virtual callback 不能共享一条宿主线程递归栈或 Python 执行状态。
  独立 `callback_interleaving` 回归检查同对象并发调用、非后进先出返回、嵌套
  function 回调和因果上下文的保持。
- 核心修复还验证了 DPI 签名、真正循环拒绝、对象/静态/嵌套 callback 取消，以及
  SV-root/Python-root 两类构造链。最终完整 Python 测试为 994 项通过，无 skip/xfail；
  本地 native 源码构建也通过。
- 关闭原 scoreboard 不只是关闭比较：原 idle helper 还读取该 scoreboard 维护的
  RAL mirror。本接入层改为轮询实际 CSR 响应；扩大到全部字节值的场景曾发现短
  场景未暴露的 FIFO 丢包，没有通过削弱 checker 来掩盖它。

## 验证范围

本项目端到端迁移字节事务场景与独立流、帧、读回检查，不是把原 scoreboard 的
全部 CSR 预测、中断、FIFO overflow、超时、复位恢复和覆盖率算法重写成 Python。
原 SV 基线证明原路径可运行，不能把它计为 Python 模型覆盖；也不声称已验证整个
上游类树的自动发现或全部 UVM 声明的自动导出。

三个主要 seed 覆盖关闭 parity 和 odd parity，混合模式 seed 3 还覆盖 even parity。
全字节用例覆盖所有字节值，包括原生方法使用 signed byte 时的符号边界。
