# SVX Milestone 2 Typed Channel Example

This example verifies the first SvTypes-style typed channel layer on top of raw
binary payload channels:

- Python packs a `SvObject` transaction with `to_bytes()` and sends it through
  `Channel.put(...)`.
- SV receives a payload tagged as `kind="svtypes"`, copies the binary byte
  stream, and unpacks it into a matching generated-style transaction class.
- SV packs the same generated-style transaction byte stream and sends it
  through the raw payload channel layer.
- Python receives it with `Channel.get(M2Transaction)` and unpacks it with
  `from_bytes()`.
- Python rejects a typed payload whose `type_name` metadata does not match the
  requested transaction class.

The transaction payload is never hex-encoded for transport.
