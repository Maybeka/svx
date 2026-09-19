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

    signal = module.declare_signal("tb.data", Bit(8))

    assert signal.path == "tb.data"
    descriptor = __import__("svtypes").encoding_descriptor(Bit(8))
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

    signal = module.declare_signal("tb.data", BrokenBit(8))
    with pytest.raises(SVXSignalError, match="returned 0 bytes"):
        signal.write(1)


def test_four_state_signal_preserves_value_x_and_z_planes(signal_module):
    module, calls = signal_module
    signal = module.declare_signal("tb.logic", Logic(8))

    assert signal.read() == LogicValue(8, value_mask=1, x_mask=2, z_mask=4)
    signal.write(LogicValue(8, value_mask=0x80, x_mask=2, z_mask=4))
    assert calls[-1] == ("write", ("tb.logic", b"\x80\x02\x04"))
