# Changelog

All notable changes to SVX are documented in this file.

## Unreleased

- Requires SvTypes 1.4.2 for public codec, external-storage and field-policy fixes.
  Missing or noncallable normalization/identity APIs fail early instead of
  being misreported as invalid user annotations.
- Checks the explicit `ExpectedType` in experimental `SVX_GET_OBJECT`, rather
  than relying only on the destination variable's potentially broader type.

- Allows `close_instance` to take a cross-language instance directly, retaining
  integer-ID callers and preventing release through a different bound receiver.
  Uses a nonblocking release gateway for function callbacks and rejects waiting
  cleanup hooks.
- Validates SV method parameter/return types semantically during source-backed
  manifest discovery, including expanded ancestors and closed specializations.
  Preserves unpacked declarator dimensions and SV implicit type-group rules.

- Preflights inheritance output paths and ownership before replacing artifacts,
  refusing user-file collisions and parent-symlink directory escapes.
- Reports expected CLI errors concisely with exit status 2; the global `--debug`
  option retains tracebacks, while programmatic exception behavior is unchanged.
- Includes referenced SVG and Excalidraw architecture assets in the source
  distribution and validates published local document links.
- Recognizes SV method parameters declared in the method body, preserving
  their formal order and output directions during source discovery.
- Resolves exposed inherited methods and implicit virtual overrides during SV
  source validation, including package-qualified parameterized bases.
- Uses public SvTypes field-path queries for indexed collection element codecs;
  associative-array key/value codec access still needs public-contract work.
- Checks exposed SV method timing and formal order/directions during source
  discovery, recognizes pure virtual prototypes, and preserves inherited SV
  argument directions/types in VIF methods. VIF void functions are supported.
- Validates closed SV specialization parameter counts and type/value order
  during source discovery, rescans edited source instead of reusing cached
  contents, and does not treat ordinary parser warnings as syntax failures.
- Generates Python views for declared SV-owned fields without redeclaring or
  shadowing their inherited SV storage, including alternating inheritance targets.
- Preserves unchanged output timestamps for the SvTypes CLI generation wrapper
  and manifest migration, not only inheritance artifacts.
- Explicitly classifies experimental object handoff and public raw payload
  entry points separately from private generated/native bridge interfaces.
- Refreshes discovered field codecs after class redefinition and rejects
  collisions with user-defined symbols instead of silently reusing them.
- Retains active child execution state when a process-group handle is collected,
  and drains children before shutdown closes their channels and object registries.
- Removes completed processes' cancellation metadata instead of accumulating it.
- Locates support/native sources beside the imported package for target installs,
  avoiding unnecessary `SVX_SHARE_DIR` setup and mixed-installation discovery.
- Advances the internal runtime/SV ABI to 3 for separate nonblocking gateways,
  including object release; incompatible older libraries and artifacts fail
  initialization.
- Generates typed SV implementation-selection factories for constructible
  Python roots, removing handwritten private-ABI glue from published examples.
- Preserves unchanged generated files and their timestamps to avoid unnecessary
  recompilation during iterative development.
- Separates nonblocking inheritance/field dispatch from task dispatch and enforces
  function-callback restrictions, including constructors.
- Invalidates released projected fields, clears foreign-handle endpoint caches on
  shutdown, and rejects unknown modports during generation.
- Makes process-group kill a cleanup completion barrier and tracks generator-owned
  outputs to remove obsolete artifacts without deleting user files.

## 1.0.0 - 2026-09-29

- Updates the SvTypes integration to the 1.2 public `Bit` and `Logic` codecs.
- Requires SvTypes 1.3 for public SystemVerilog declaration and packer
  rendering used by automatic projected-field manifest discovery.
- Keeps constrained randomization, coverage collection, and UCIS handling in
  SvTypes; SVX transports explicitly prepared typed values without implicitly
  randomizing or sampling them.
- Reorganizes example documentation around current adoption paths and adds
  generated cross-language inheritance and hierarchical signal-access examples.
- Adds manifest-declared SV static-member mirrors with class-level dispatch
  that does not allocate or require a foreign object ID.
- Narrows cross-language inheritance parameters to `input`, `output`, and
  `inout`; `ref` and `const ref` are explicitly outside the SVX ABI.

- Improves generated Python and SystemVerilog inheritance artifacts with
  deterministic provenance headers, structural sections, readable call
  contracts, and boundary comments without changing their runtime ABI.
- Requires the stable SvTypes `1.x` contract and validates its runtime
  capabilities before user code runs.
- Adds deterministic runtime initialization and shutdown states, stale process
  handling, process failure propagation, and initialization rollback.
- Adds declarative inheritance manifest v2, safe v1 migration, `RemoteRef`
  validation, callback-cycle diagnostics, generated artifact hashes, atomic
  generation, and stale-output checking.
- Adds Python decorators, versioned SV declaration metadata, and the
  `inheritance-manifest` command as front ends that normalize to manifest v2.
- Adds generated SvTypes request/response record contracts, completion-time
  copy-out response values, runtime validation of call-record identities, and
  generator ABI 2. Legacy concatenated argument streams are no longer accepted.
- Adds typed channel encoding descriptors, first-use type binding, bounded
  queues, payload limits, and deterministic cleanup.
- Integrates hierarchical access directly into `libsvx`, validates every
  declared path before runtime readiness, and retains SvTypes descriptors for
  each declaration.
- Adds Python/native/SystemVerilog product-version handshake checks and
  reproducible source and wheel contents for Python, SystemVerilog, and native
  consumer builds.
- Adds `native-source` discovery so an installed wheel can build `libsvx`
  without a repository checkout.

## 0.1.0 - 2026-07-12

Initial release of the split SVX repository.

- Provides simulator-hosted Python execution with simulator-owned timing,
  fork/join, error policy, and binary payload channels.
- Uses versioned SvTypes `0.1.x` as the sole typed-value contract.
- Provides generated, manifest-driven cross-language inheritance with typed
  arguments/results, lifecycle handling, and callback-cycle rejection.
- Provides predeclared hierarchical signal read, write, force, and release
  through a direct VPI C service called from an SV DPI context.
- Adds source/runtime installation guidance, CMake install rules, a Python CLI
  entry point, packaged SV support files, and release verification gates.
