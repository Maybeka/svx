"""SvTypes 1.x capability contract consumed by SVX."""

from __future__ import annotations


SVTYPES_PACKAGE_MAJOR_VERSION = 1
SVTYPES_SCHEMA_FORMAT_VERSION = 1
SVTYPES_BINARY_FORMAT_VERSION = 1
SVTYPES_OBJECT_ENVELOPE_VERSION = 2
SVTYPES_GENERATOR_RUNTIME_ABI_VERSION = 1
SVTYPES_REQUIRED_CAPABILITIES = (
    "svtypes.checked-encoding-descriptor.v1",
    "svtypes.codec-context.v1",
    "svtypes.record-schema.v1",
    "svtypes.remote-reference.v1",
)
