from collections.abc import Callable
from typing import overload

from . import _registry


@overload
def export(func: Callable[[], object]) -> Callable[[], object]: ...


@overload
def export(func: None = None, *, name: str | None = None) -> Callable[[Callable[[], object]], Callable[[], object]]: ...


def export(func: Callable[[], object] | None = None, *, name: str | None = None):
    def decorator(f: Callable[[], object]) -> Callable[[], object]:
        _registry.register(
            _registry.default_name(f) if name is None else name,
            f,
        )
        return f

    if func is None:
        return decorator
    return decorator(func)


def list_exports() -> dict[str, Callable[[], object]]:
    return _registry.list_exports()
