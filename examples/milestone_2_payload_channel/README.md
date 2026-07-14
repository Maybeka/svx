# SVX Milestone 2 Payload Channel Example

This example verifies the raw payload channel layer:

- Python puts bytes into a named channel; SV gets the same payload.
- SV puts bytes into a named channel; Python blocks in `get_payload()` until
  the SV producer runs.
- Python `try_get_payload()` returns `None` when the channel is empty.
- Python `try_put_payload()` succeeds on the current unbounded channel.
- Python and SV `peek` operations observe without consuming.
- A 1 MB Python payload reaches SV intact as binary bytes.

Payloads are stored in native binary buffers and passed through SV as opaque
`chandle` payloads. SV can inspect or copy bytes through payload accessor
functions.
