import pytest
from app.entities import Frame
from app.repositories import Webcam
from opendataframework.config import Config
from opendataframework.repository import ReadableProtocol, StreamableProtocol, WritableProtocol
from opendataframework.view import DataViewProtocol, StreamingVideoView

# Fakes the capture device rather than requiring physical hardware — no
# physical webcam is available in CI or most dev environments.


class FakeCapture:
    """Yields a fixed number of blank frames, then reports end-of-stream."""

    def __init__(self, frame_count: int) -> None:
        self._remaining = frame_count

    def read(self):
        import numpy as np

        if self._remaining <= 0:
            return False, None
        self._remaining -= 1
        return True, np.zeros((2, 2, 3), dtype="uint8")

    def release(self) -> None:
        pass


@pytest.fixture
def webcam():
    instance = Webcam(Config({"webcam": {"device": 0}}))
    instance.capture = FakeCapture(frame_count=3)
    return instance


def test_conforms_to_streamable_only(webcam):
    assert isinstance(webcam, StreamableProtocol)
    assert not isinstance(webcam, ReadableProtocol)
    assert not isinstance(webcam, WritableProtocol)


def test_data_view_is_streaming_video(webcam):
    assert isinstance(webcam, DataViewProtocol)
    assert webcam.data_view() == StreamingVideoView(field="data")


def test_stream_yields_frame_entities(webcam):
    frames = list(webcam.stream())
    assert len(frames) == 3
    assert all(isinstance(f, Frame) for f in frames)
    assert [f.id for f in frames] == [1, 2, 3]


def test_stream_frame_data_is_jpeg_bytes(webcam):
    frame = next(webcam.stream())
    assert isinstance(frame.data, bytes)
    assert frame.data[:2] == b"\xff\xd8"  # JPEG SOI marker
