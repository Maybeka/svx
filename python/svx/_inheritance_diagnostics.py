"""Preserve source exceptions while annotating cross-language call boundaries."""

from contextvars import ContextVar
from functools import wraps
import inspect

from .errors import SVXCancellationError


_call_path: ContextVar[tuple[str, ...]] = ContextVar('svx_inheritance_call_path', default=())
_NOTE_PREFIX = 'SVX call path: '


def inheritance_boundary(direction: str, *, identity: str = 'method_id',
                         receiver: str | None = 'object_id'):
    def decorate(function):
        positions = {name: index for index, name in enumerate(inspect.signature(function).parameters)}

        def argument(name, args, kwargs):
            index = positions[name]
            return args[index] if index < len(args) else kwargs.get(name)

        @wraps(function)
        def invoke(*args, **kwargs):
            target = argument(identity, args, kwargs)
            object_id = argument(receiver, args, kwargs) if receiver is not None else 0
            frame = f'{direction} object={object_id} {identity}={target}'
            path = (*_call_path.get(), frame)
            token = _call_path.set(path)
            try:
                return function(*args, **kwargs)
            except SVXCancellationError:
                raise
            except BaseException as error:
                if not any(note.startswith(_NOTE_PREFIX) for note in getattr(error, '__notes__', ())):
                    error.add_note(_NOTE_PREFIX + ' -> '.join(path))
                raise
            finally:
                _call_path.reset(token)

        return invoke

    return decorate
