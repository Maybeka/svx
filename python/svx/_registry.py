from collections.abc import Callable

from .errors import SVXExportError

_registry: dict[str, Callable[[], object]] = {}


def default_name(func: Callable[[], object]) -> str:
    return f"{func.__module__}.{func.__qualname__}"


def register(name: str, func: Callable[[], object]) -> None:
    if name in _registry:
        existing = _registry[name]
        raise SVXExportError(
            f"Export name {name!r} is already registered by "
            f"{existing.__module__}.{existing.__qualname__}"
        )
    _registry[name] = func


def resolve(name: str) -> Callable[[], object]:
    try:
        return _registry[name]
    except KeyError:
        raise SVXExportError(f"No SVX export registered for {name!r}") from None


def list_exports() -> dict[str, Callable[[], object]]:
    return dict(_registry)
