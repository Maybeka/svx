# 原始 Payload Channel

[English](README.md)

仅当不存在合适的共享 SvTypes schema 时使用 raw payload channel。此示例展示
二进制 payload 层：

- Python 向具名 channel 放入 bytes，SV 收到相同 payload。
- SV 向具名 channel 放入 bytes，Python 在 `get_payload()` 中阻塞直到 SV producer 运行。
- channel 为空时，Python `try_get_payload()` 返回 `None`。
- 当前无界 channel 中 Python `try_put_payload()` 成功。
- Python 和 SV 的 `peek` 只观察而不消费。
- 1 MB Python payload 能以完整二进制 bytes 到达 SV。

Payload 保存在 native 二进制 buffer 中，并作为 opaque `chandle` 传入 SV。SV
可通过 payload accessor function 检查或复制 bytes。对 transaction 验证数据，
优先使用 [typed bus 示例](../milestone_7_sv_typed_helpers/README.zh-CN.md)。
