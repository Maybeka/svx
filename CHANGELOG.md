# Changelog

All notable changes to SVX are documented in this file.

## Unreleased

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

## 1.0.0 - 2026-08-14

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
