"""Bounded discovery errors; invalid discovery never publishes artifacts."""

from contextvars import ContextVar
from functools import wraps

from .errors import SVXInheritanceError

_current = ContextVar('svx_export_diagnostics', default=None)


class _Diagnostics:
    def __init__(self, limit):
        self.limit = limit
        self.messages = []

    def record(self, error):
        message = str(error)
        if message not in self.messages:
            self.messages.append(message)
        if len(self.messages) >= self.limit:
            self.raise_errors()

    def raise_errors(self):
        if not self.messages:
            return
        if len(self.messages) == 1 and len(self.messages) < self.limit:
            raise _DiscoveryErrors(self.messages[0])
        suffix = (f'; error limit {self.limit} reached; discovery stopped early, '
                  'further errors may remain' if len(self.messages) >= self.limit else '')
        raise _DiscoveryErrors(
            f'SV export failed with {len(self.messages)} errors{suffix}:\n'
            + '\n'.join(f'  {index}. {message}' for index, message in enumerate(self.messages, 1)))


class _DiscoveryErrors(SVXInheritanceError):
    pass


def attempt(function, *args, **kwargs):
    collector = _current.get()
    if collector is None:
        return function(*args, **kwargs)
    try:
        return function(*args, **kwargs)
    except _DiscoveryErrors:
        raise
    except SVXInheritanceError as error:
        collector.record(error)
        return None


def raise_errors():
    collector = _current.get()
    if collector is not None:
        collector.raise_errors()


def has_errors():
    collector = _current.get()
    return collector is not None and bool(collector.messages)


def report(message):
    error = SVXInheritanceError(message)
    collector = _current.get()
    if collector is None:
        raise error
    collector.record(error)


def with_export_diagnostics(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        limit = kwargs.get('max_errors', 10)
        if type(limit) is not int or limit < 1:
            raise SVXInheritanceError('max_errors must be a positive integer')
        collector = _Diagnostics(limit)
        token = _current.set(collector)
        try:
            try:
                result = function(*args, **kwargs)
            except _DiscoveryErrors:
                raise
            except SVXInheritanceError as error:
                collector.record(error)
                collector.raise_errors()
            collector.raise_errors()
            return result
        finally:
            _current.reset(token)
    return wrapped
