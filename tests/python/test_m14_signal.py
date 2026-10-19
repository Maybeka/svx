from __future__ import annotations

import importlib

import pytest
from svtypes import Bit, Logic, LogicValue

from svx.errors import SVXSignalError
from svx import runtime


@pytest.fixture
def signal_module(monkeypatch):
    module = importlib.import_module("svx.signal")
    calls: list[tuple[str, object]] = []
    payloads = {"tb.data": b"\x5a", "tb.logic": b"\x01\x02\x04"}
    runtime._state = runtime.RuntimeState.READY
    runtime._codec_session = __import__("svtypes").CodecSession()

    monkeypatch.setattr(
        module._native,
        "signal_declare",
        lambda *args: calls.append(("declare", args)),
    )
    monkeypatch.setattr(module._native, "signal_read", lambda path: payloads[path])
    monkeypatch.setattr(
        module._native,
        "signal_write",
        lambda path, data: calls.append(("write", (path, data))),
    )
    monkeypatch.setattr(
        module._native,
        "signal_force",
        lambda path, data: calls.append(("force", (path, data))),
    )
    monkeypatch.setattr(
        module._native, "signal_release", lambda path: calls.append(("release", path))
    )
    yield module, calls
    runtime._state = runtime.RuntimeState.UNINITIALIZED
    runtime._codec_session = None


def test_declare_signal_uses_public_svtypes_metadata(signal_module):
    module, calls = signal_module

    signal = module.declare_signal("tb.data", Bit[8]())

    assert signal.path == "tb.data"
    descriptor = __import__("svtypes").encoding_descriptor(Bit[8]())
    assert calls == [
        (
            "declare",
            (
                "tb.data",
                8,
                False,
                "2state",
                descriptor.unified_type_name,
                descriptor.encoding_fingerprint_hex,
                descriptor.binary_format_version,
            ),
        )
    ]
    assert signal.read() == 0x5A
    signal.write(0x12)
    signal.force(0x34)
    signal.release()
    assert calls[1:] == [
        ("write", ("tb.data", b"\x12")),
        ("force", ("tb.data", b"\x34")),
        ("release", "tb.data"),
    ]


def test_declare_signal_rejects_codec_without_public_state_domain(signal_module):
    module, _ = signal_module

    class IncompleteCodec:
        width = 1
        signed = False

        def pack(self, value):
            return b"\x00"

        def unpack(self, value):
            return 0, 1

    with pytest.raises(TypeError, match="two-state"):
        module.declare_signal("tb.flag", IncompleteCodec())


def test_signal_rejects_noncanonical_svtypes_payload(signal_module):
    module, _ = signal_module

    class BrokenBit(Bit):
        def pack(self, value):
            return b""

    signal = module.declare_signal("tb.data", BrokenBit[8]())
    with pytest.raises(SVXSignalError, match="returned 0 bytes"):
        signal.write(1)


def test_four_state_signal_preserves_value_x_and_z_planes(signal_module):
    module, calls = signal_module
    signal = module.declare_signal("tb.logic", Logic[8]())

    assert signal.read() == LogicValue(8, value_mask=1, x_mask=2, z_mask=4)
    signal.write(LogicValue(8, value_mask=0x80, x_mask=2, z_mask=4))
    assert calls[-1] == ("write", ("tb.logic", b"\x80\x02\x04"))


def test_subscription_is_explicit_cached_and_independent(signal_module, monkeypatch):
    module, calls = signal_module
    cached = {1: b"\x12", 2: b"\x34"}
    ids = iter(cached)
    monkeypatch.setattr(module._native, "signal_subscribe", lambda path: next(ids))
    monkeypatch.setattr(module._native, "signal_subscription_read", cached.__getitem__)
    monkeypatch.setattr(module._native, "signal_unsubscribe", lambda id: calls.append(("close", id)))
    signal = module.declare_signal("tb.data", Bit[8]())
    first = signal.subscribe()
    with signal.subscribe() as second:
        assert first.path == second.path == signal.path
        assert first.read() == 0x12
        assert second.read() == 0x34
        assert signal.read() == 0x5a
        cached[1] = b"\x67"
        assert first.read() == 0x67
    second.close()
    assert calls.count(("close", 2)) == 1
    with pytest.raises(SVXSignalError, match="closed"):
        second.read()
    with pytest.raises(SVXSignalError, match="closed"):
        second.__enter__()
    first.close()


def test_subscription_exception_cleanup_and_four_state(signal_module, monkeypatch):
    module, calls = signal_module
    monkeypatch.setattr(module._native, "signal_subscribe", lambda path: 1)
    monkeypatch.setattr(module._native, "signal_subscription_read", lambda id: b"\x01\x02\x04")
    monkeypatch.setattr(module._native, "signal_unsubscribe", lambda id: calls.append(("close", id)))
    signal = module.declare_signal("tb.logic", Logic[8]())
    with pytest.raises(ValueError, match="user failure"):
        with signal.subscribe() as sub:
            assert sub.read() == LogicValue(8, value_mask=1, x_mask=2, z_mask=4)
            raise ValueError("user failure")
    assert calls[-1] == ("close", 1)


def test_subscription_close_failure_can_be_retried(signal_module, monkeypatch):
    module, _ = signal_module
    monkeypatch.setattr(module._native, "signal_subscribe", lambda path: 1)
    monkeypatch.setattr(module._native, "signal_subscription_read", lambda id: b"\x12")
    def fail(id):
        raise SVXSignalError("tb.data", "close", "remove failed", "unsubscribe_failed")
    monkeypatch.setattr(module._native, "signal_unsubscribe", fail)
    sub = module.declare_signal("tb.data", Bit[8]()).subscribe()
    with pytest.raises(SVXSignalError, match="remove failed"):
        sub.close()
    assert sub.read() == 0x12
    monkeypatch.setattr(module._native, "signal_unsubscribe", lambda id: None)
    sub.close()


def test_subscription_resolves_context_codec_signature_once(signal_module, monkeypatch):
    module, _ = signal_module
    class ContextBit(Bit):
        def unpack(self, payload, context):
            assert isinstance(context, __import__("svtypes").UnpackContext)
            return payload[0], len(payload)
    monkeypatch.setattr(module._native, "signal_subscribe", lambda path: 1)
    monkeypatch.setattr(module._native, "signal_subscription_read", lambda id: b"\x12")
    monkeypatch.setattr(module._native, "signal_unsubscribe", lambda id: None)
    sub = module.declare_signal("tb.data", ContextBit[8]()).subscribe()
    def unexpected_signature(*args):
        raise AssertionError("signature checked on every cached read")
    monkeypatch.setattr(module.inspect, "signature", unexpected_signature)
    assert sub.read() == sub.read() == 0x12
    sub.close()
