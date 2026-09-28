"""Experimental explicit handoff of Python-created inheritance objects to SV."""

from __future__ import annotations

from . import _native
from .errors import SVXInheritanceError


def publish_object(name: str, instance: object) -> None:
    """Publish one live cross-language instance under an application-chosen name.

    The name is an explicit capability, not an object lookup mechanism. SV can
    obtain the object only through ``SVX_GET_OBJECT`` and its expected type is
    verified by an SV ``$cast``.
    """

    if not isinstance(name, str) or not name or "\x00" in name:
        raise ValueError("published object name must be a non-empty string without NUL")
    object_id = getattr(instance, "_svx_remote_object_id", None)
    if not isinstance(object_id, int) or object_id <= 0:
        raise SVXInheritanceError(
            "publish_object() requires a live SVX cross-language instance"
        )
    if _native.inheritance_get(object_id) is not instance:
        raise SVXInheritanceError(
            "publish_object() requires an instance currently bound to its SV object"
        )
    _native.inheritance_publish(name, object_id)
