from __future__ import annotations

import pytest

import svx
from svx import runtime
from svtypes import CodecSession, Int, SvObject, encoding_descriptor, svobj


@pytest.fixture(autouse=True)
def codec_session():
    runtime._state = runtime.RuntimeState.READY
    runtime._codec_session = CodecSession()
    yield
    runtime._state = runtime.RuntimeState.UNINITIALIZED
    runtime._codec_session = None


@svobj
class ChannelItem(SvObject):
    number = Int()


def test_typed_channel_transports_public_encoding_descriptor(monkeypatch):
    captured = {}

    def put(*args):
        captured["args"] = args

    monkeypatch.setattr("svx._native.channel_put_payload", put)
    item = ChannelItem()
    item.number.value = 23

    svx.channel("descriptor.put").put(item)

    descriptor = encoding_descriptor(ChannelItem)
    args = captured["args"]
    assert args[0:4] == (
        "descriptor.put",
        "svtypes",
        "ChannelItem",
        "application/x-svtypes",
    )
    assert args[4] == descriptor.unified_type_name
    assert args[5] == descriptor.encoding_fingerprint_hex
    assert args[6] == descriptor.binary_format_version
    assert isinstance(args[7], bytes)


def test_typed_channel_checked_decode_rejects_descriptor_mismatch(monkeypatch):
    item = ChannelItem()
    item.number.value = 9
    good = encoding_descriptor(ChannelItem)
    payload = item.to_bytes()

    monkeypatch.setattr(
        "svx._native.channel_get_payload",
        lambda _name: (
            "svtypes",
            "ChannelItem",
            "application/x-svtypes",
            good.unified_type_name,
            bytes(32).hex(),
            good.binary_format_version,
            payload,
        ),
    )
    with pytest.raises(svx.SVXChannelError, match="encoding fingerprint mismatch"):
        svx.channel("descriptor.get").get(ChannelItem)


def test_raw_payload_has_no_fabricated_encoding_descriptor(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "svx._native.channel_put_payload",
        lambda *args: captured.setdefault("args", args),
    )
    svx.channel("raw").put_payload(b"abc")
    assert captured["args"][4:7] == ("", "", 0)


def test_channel_rejects_payload_above_resource_limit(monkeypatch):
    from svx.channel import MAX_PAYLOAD_BYTES

    monkeypatch.setattr("svx._native.channel_put_payload", lambda *_args: None)
    with pytest.raises(svx.SVXChannelError, match="resource limit"):
        svx.channel("oversized").put_payload(b"x" * (MAX_PAYLOAD_BYTES + 1))


def test_typed_role_uses_declared_scalar_codec_for_send_and_receive(monkeypatch):
    captured = {}
    codec = Int()
    descriptor = encoding_descriptor(codec)
    monkeypatch.setattr(
        "svx._native.channel_put_payload",
        lambda *args: captured.setdefault("put", args),
    )
    monkeypatch.setattr(
        "svx._native.channel_get_payload",
        lambda _name: (
            "svtypes",
            "Int",
            "application/x-svtypes",
            descriptor.unified_type_name,
            descriptor.encoding_fingerprint_hex,
            descriptor.binary_format_version,
            codec.pack(42),
        ),
    )

    role = svx.req_channel("scalar", codec)
    role.put(17)
    assert captured["put"][7] == codec.pack(17)
    assert role.raw.get(codec) == 42
