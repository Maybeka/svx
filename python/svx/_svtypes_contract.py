"""SvTypes 1.x capability contract consumed by SVX."""

from __future__ import annotations

from .errors import SVXError


SVTYPES_MIN_VERSION = '1.4.2'
SVTYPES_TYPE_SPEC_APIS = (
    'is_materializable_type',
    'materialize_type_spec',
    'type_spec_identity',
    'type_spec_from_identity',
)


def require_type_spec_api(module) -> None:
    missing = [name for name in SVTYPES_TYPE_SPEC_APIS
               if not callable(getattr(module, name, None))]
    if missing:
        raise SVXError(
            f'SVX requires SvTypes >= {SVTYPES_MIN_VERSION} with public TypeSpec APIs; '
            'missing: ' + ', '.join(missing))


def require_codec_template_api(module) -> None:
    object_type = getattr(module, 'SvObject', None)
    if not callable(getattr(object_type, 'codec_template', None)):
        raise SVXError(
            'SVX requires the public SvTypes SvObject.codec_template() API; '
            'the installed dependency lacks it. Use a SvTypes build providing '
            'this API; matching version and wire capabilities are insufficient.')


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
