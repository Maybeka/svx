from __future__ import annotations

from collections.abc import Callable
import functools
import traceback

from .export import export


def test(func: Callable[[], object] | None = None, *, name: str | None = None):
    def decorator(f: Callable[[], object]) -> Callable[[], object]:
        @functools.wraps(f)
        def wrapper() -> object:
            try:
                return f()
            except BaseException as exc:
                formatted = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                print(f"SVX TEST FAILED [{f.__module__}.{f.__qualname__}]:\n{formatted}", flush=True)
                raise

        return export(wrapper, name=name)

    if func is None:
        return decorator
    return decorator(func)
