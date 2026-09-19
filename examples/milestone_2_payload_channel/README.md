# Raw Payload Channels

[中文](README.zh-CN.md)

Use raw payload channels only when no shared SvTypes schema is appropriate. It
demonstrates the binary payload layer:

- Python puts bytes into a named channel; SV gets the same payload.
- SV puts bytes into a named channel; Python blocks in `get_payload()` until
  the SV producer runs.
- Python `try_get_payload()` returns `None` when the channel is empty.
- Python `try_put_payload()` succeeds on the current unbounded channel.
- Python and SV `peek` operations observe without consuming.
- A 1 MB Python payload reaches SV intact as binary bytes.

Payloads are stored in native binary buffers and passed through SV as opaque
`chandle` payloads. SV can inspect or copy bytes through payload accessor
functions. Prefer the [typed bus example](../milestone_7_sv_typed_helpers) for
transactional verification data.
