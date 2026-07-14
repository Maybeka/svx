# Decision 0001: SvTypes as a Versioned External Dependency

Status: accepted.

## Context

SVX uses typed transaction data, generated SystemVerilog classes, generated C++
support, and binary serialization parity. Those responsibilities belong to
SvTypes, not to the simulator-hosted SVX runtime.

SvTypes is also useful without SVX: it can model SystemVerilog-like data,
generate language support, and serialize data for offline tools or future
post-silicon flows.

## Decision

SVX and SvTypes will be split into two repositories and two versioned packages.

```text
svtypes
  owns Python SvTypes DSL, binary format, generated SV/C++ support, and
  SvTypes tests/docs.

svx
  owns simulator-hosted Python execution, DPI/VPI runtime, SVX SystemVerilog
  services, SVX Python APIs, and SVX examples/tests.
```

SVX depends on a versioned SvTypes release. SvTypes must not import or depend
on SVX.

## Dependency Direction

```text
svx
  depends on svtypes
  consumes svtypes runtime support files

svtypes
  has no dependency on svx
```

SVX may provide convenience CLI wrappers around SvTypes generation only when
they call public SvTypes APIs. The canonical SvTypes implementation and
serialization contract live in the SvTypes repository.

## Consequences

- SvTypes can be released, tested, and reused independently.
- SVX has a clear versioned dependency boundary.
- Cross-repo compatibility must be tested explicitly.
- SVX examples should pin or declare compatible SvTypes versions.
- Development and CI use the sibling `../svtypes` repository as the editable
  dependency; released SVX consumes versioned SvTypes packages only.
