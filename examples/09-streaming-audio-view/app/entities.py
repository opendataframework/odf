"""Entities for the streaming-audio-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class DispatchChunk:
    """A single synthesized WAV audio chunk from the dispatch radio feed.

    Attributes:
        id: Monotonically increasing chunk counter, assigned by ``DispatchRadio.stream()``.
        data: The chunk, WAV-encoded.
        timestamp: ``time.time()`` when the chunk was generated.
    """

    id: int
    data: bytes
    timestamp: float
