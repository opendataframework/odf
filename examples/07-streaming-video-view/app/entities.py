"""Entities for the streaming-video-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Frame:
    """A single JPEG-encoded webcam frame.

    Attributes:
        id: Monotonically increasing frame counter, assigned by ``Webcam.stream()``.
        data: The frame, JPEG-encoded.
        timestamp: ``time.time()`` when the frame was captured.
    """

    id: int
    data: bytes
    timestamp: float
