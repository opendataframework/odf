"""Live synthetic audio repository backing the streaming-audio-view example."""

import time
from collections.abc import Iterator

from opendataframework import Repository, Storage, StreamingAudioView

from app.audio import synth_melody_wav
from app.entities import DispatchChunk

_NOTE_SECONDS = 0.5  # tempo of the melody itself
_REST_SECONDS = 2.5  # a deliberate breath at the end of each phrase
# A3 up to A4 and back down to A3 (A natural minor), then a rest —
# (None, duration) is silence. Twice as many notes as the original
# A3..E4..B3 arch, for a fuller-feeling phrase before it loops.
_SCALE_HZ = [220.00, 246.94, 261.63, 293.66, 329.63, 349.23, 392.00, 440.00]  # A3..A4
_PHRASE = [(hz, _NOTE_SECONDS) for hz in _SCALE_HZ + _SCALE_HZ[-2::-1]] + [(None, _REST_SECONDS)]
_PHRASE_SECONDS = sum(duration for _, duration in _PHRASE)  # 10.0s
# Chunk length is independent of the melody's own tempo — it's sized for
# how often the dev UI's <audio> element can tolerate reloading its decode
# pipeline (same cost as an HLS segment switch). It's set to exactly one
# phrase so the chunk boundary — where that reload happens — falls inside
# the phrase's trailing rest rather than mid-note: whatever the reload
# costs lands in a beat that was already going to be silent.
_PHRASES_PER_CHUNK = 1
_CHUNK_DURATION_SECONDS = _PHRASE_SECONDS * _PHRASES_PER_CHUNK
_NOTES_PER_CHUNK = len(_PHRASE) * _PHRASES_PER_CHUNK
_SAMPLE_RATE = 8000
# Paced to roughly match each chunk's own audio duration — not shorter. The
# framework's stream subscriber queue holds only the single newest
# unconsumed item (opendataframework.context._publish_latest), which is
# right for a live feed like video where a slow viewer should always see
# the freshest frame. But it means a producer running faster than real
# time — the old 0.2s interval regardless of _CHUNK_DURATION_SECONDS —
# generates many chunks between two browser requests; the one the UI
# actually receives is whichever happened to be newest, an effectively
# arbitrary jump forward in the melody rather than the next chronological
# chunk. That jump — not the <audio> reload itself — is what sounded like
# a new melody starting at every chunk boundary.
_INTERVAL_SECONDS = _CHUNK_DURATION_SECONDS


@Storage
@Repository(DispatchChunk)
class DispatchRadio:
    """A live synthetic audio feed — read-only and stream-only, no
    get/all/save. No external device to open/release, so no
    ``open_stream()``/``close_stream()`` — the generator itself is the
    entire resource.

    Demonstrates ``StreamingAudioView``: each streamed chunk is one
    complete, independently decodable WAV clip — the dev UI's ``/stream``
    endpoint serves one chunk per request rather than multiplexing over a
    single connection like ``StreamingVideoView``'s MJPEG multipart stream,
    since browsers don't support multipart delivery for ``<audio>``.
    """

    def stream(self) -> Iterator[DispatchChunk]:
        """Yield synthesized WAV chunks, one every ``_INTERVAL_SECONDS``.

        Each chunk packs exactly ``_PHRASES_PER_CHUNK`` repeats of
        ``_PHRASE`` (melody notes plus its trailing rest), and both the
        melody position and the tone generator's phase (see
        ``synth_melody_wav``) carry over between chunks — so the tune keeps
        moving at its own tempo across chunk boundaries instead of
        restarting or stalling once per chunk.

        Yields:
            Each generated ``DispatchChunk``, playing ``_PHRASE`` on a loop.
        """
        chunk_id = 0
        note_index = 0
        phase = 0.0
        while True:
            notes = [_PHRASE[(note_index + i) % len(_PHRASE)] for i in range(_NOTES_PER_CHUNK)]
            clip, phase = synth_melody_wav(notes, _SAMPLE_RATE, phase)
            note_index += _NOTES_PER_CHUNK
            chunk_id += 1
            yield DispatchChunk(id=chunk_id, data=clip, timestamp=time.time())
            time.sleep(_INTERVAL_SECONDS)

    def data_view(self) -> StreamingAudioView:
        """Tell the UI to render this feed as streamed audio, not a table.

        Returns:
            A ``StreamingAudioView`` keyed on the ``data`` field.
        """
        return StreamingAudioView(field="data")
