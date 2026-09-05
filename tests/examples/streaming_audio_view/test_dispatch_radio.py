import itertools

import app.repositories as repositories
from app.entities import DispatchChunk
from app.repositories import DispatchRadio
from opendataframework.repository import (
    CloseStreamProtocol,
    OpenStreamProtocol,
    ReadableProtocol,
    StreamableProtocol,
    WritableProtocol,
)
from opendataframework.view import DataViewProtocol, StreamingAudioView


def test_conforms_to_streamable_only():
    radio = DispatchRadio()

    assert isinstance(radio, StreamableProtocol)
    assert not isinstance(radio, ReadableProtocol)
    assert not isinstance(radio, WritableProtocol)


def test_has_no_open_or_close_stream_hooks():
    radio = DispatchRadio()

    assert not isinstance(radio, OpenStreamProtocol)
    assert not isinstance(radio, CloseStreamProtocol)


def test_data_view_is_streaming_audio():
    radio = DispatchRadio()

    assert isinstance(radio, DataViewProtocol)
    assert radio.data_view() == StreamingAudioView(field="data")


def test_stream_yields_dispatch_chunk_entities(monkeypatch):
    # stream() paces its sleep to _CHUNK_DURATION_SECONDS (real time, see
    # repositories.py) so a slow UI consumer never skips chunks via
    # Context's keep-only-the-newest subscriber queue — collapse that
    # sleep here so pulling a few chunks stays a fast, deterministic test.
    monkeypatch.setattr(repositories, "_INTERVAL_SECONDS", 0.0)
    radio = DispatchRadio()

    chunks = list(itertools.islice(radio.stream(), 3))

    assert len(chunks) == 3
    assert all(isinstance(c, DispatchChunk) for c in chunks)
    assert [c.id for c in chunks] == [1, 2, 3]


def test_stream_chunk_data_is_wav_bytes():
    radio = DispatchRadio()

    chunk = next(radio.stream())

    assert isinstance(chunk.data, bytes)
    assert chunk.data[:4] == b"RIFF"
    assert chunk.data[8:12] == b"WAVE"
