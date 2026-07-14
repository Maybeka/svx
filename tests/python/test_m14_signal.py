from __future__ import annotations

import importlib

import pytest
from svtypes import Bits

from svx.errors import SVXSignalError


@pytest.fixture
def signal_module(monkeypatch):
    module = importlib.import_module("svx.signal")
    calls: list[tuple[str, object]] = []
    payloads = {"tb.data": b"\x5a"}

    monkeypatch.setattr(
        module._native,
        "signal_declare",
        lambda path, width, signed: calls.append(("declare", (path, width, signed))),
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
    return module, calls


def test_declare_signal_uses_public_svtypes_metadata(signal_module):
    module, calls = signal_module

    signal = module.declare_signal("tb.data", Bits(8))

    assert signal.path == "tb.data"
    assert calls == [("declare", ("tb.data", 8, False))]
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

    class BrokenBits(Bits):
        def pack(self, value):
            return b""

    signal = module.declare_signal("tb.data", BrokenBits(8))
    with pytest.raises(SVXSignalError, match="returned 0 bytes"):
        signal.write(1)
