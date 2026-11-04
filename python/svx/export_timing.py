"""Opt-in, command-local wall-clock measurements for export."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import perf_counter


_report = ContextVar('svx_export_timing', default=None)


@contextmanager
def phase(name):
    report = _report.get()
    if report is None:
        yield
        return
    path = (*report['stack'], name)
    row = report['rows'].setdefault(path, [0.0, 0])
    report['stack'].append(name)
    start = perf_counter()
    try:
        yield
    finally:
        row[0] += perf_counter() - start
        row[1] += 1
        report['stack'].pop()


def measured(name):
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            if _report.get() is None:
                return function(*args, **kwargs)
            with phase(name):
                return function(*args, **kwargs)
        return call
    return decorate


@contextmanager
def export_report(enabled, out):
    if not enabled:
        yield
        return
    report = {'stack': [], 'rows': {}}
    token = _report.set(report)
    start = perf_counter()
    status = 'failed'
    try:
        yield
        status = 'completed'
    finally:
        elapsed = perf_counter() - start
        _report.reset(token)
        print(f'SVX export timings ({status}; wall time, inclusive phases):', file=out)
        for path, (seconds, count) in report['rows'].items():
            label = '  ' * len(path) + path[-1]
            print(f'{label}: {seconds:.6f} s ({count} calls)', file=out)
        print(f'  Total: {elapsed:.6f} s', file=out)
