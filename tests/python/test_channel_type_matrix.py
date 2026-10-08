"""Composition coverage through SVX's checked channel transport.

The full simulator matrix is separate. These tests do not claim SV parity.
"""

import pytest
import svtypes
from svx import runtime, SVXChannelError
from svx.channel import _pack_svtypes, _unpack_svtypes
from tests.integration.channel_type_matrix import MatrixValue, make_value, verify_value


@pytest.fixture
def isolated_runtime_session(monkeypatch):
    import svtypes.object

    session = svtypes.CodecSession()
    source_session = svtypes.CodecSession()
    monkeypatch.setattr(svtypes.object, "_default_session", source_session)
    monkeypatch.setattr(runtime, "_state", runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, "_codec_session", session)
    yield session
    session.close()
    source_session.close()


def test_channel_matrix_first_null_graph_roundtrip(isolated_runtime_session):
    source = make_value(0)
    verify_value(_unpack_svtypes(_pack_svtypes(source), MatrixValue), 0)


def test_channel_matrix_repeated_graph_roundtrip(isolated_runtime_session):
    # Imported identities reserve their numbers; codec templates consume none.
    for index in range(3):
        source = make_value(index)
        try:
            received = _unpack_svtypes(_pack_svtypes(source), MatrixValue)
        except SVXChannelError as error:
            assert "object number collision" in str(error), str(error)
            raise
        verify_value(received, index)
