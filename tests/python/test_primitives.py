from __future__ import annotations

import pytest

from svx import primitives


def test_delay_validates_domain_unit_and_overflow(monkeypatch):
    calls = []
    monkeypatch.setattr(primitives._native, "delay", lambda *args: calls.append(args))

    primitives.delay(1.5, "ns")
    assert calls == [(1.5, 3)]

    for value in (-1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            primitives.delay(value)
    with pytest.raises(ValueError, match="unsupported"):
        primitives.delay(1, "minute")
    with pytest.raises(OverflowError, match="64-bit"):
        primitives.delay(10**10, "s")


def test_fork_rejects_empty_and_noncallable_sequences():
    with pytest.raises(ValueError, match="at least one"):
        primitives.fork_join([])
    with pytest.raises(TypeError, match="expected callables"):
        primitives.fork_join([lambda: None, 3])
