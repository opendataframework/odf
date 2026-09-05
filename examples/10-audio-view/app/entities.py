"""Entities for the audio-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class VoiceMemo:
    """A short voice memo shown via ``VoiceMemos.data_view()``.

    Attributes:
        id: Primary key, ``None`` until ``VoiceMemos.save()`` assigns one.
        clip: The memo, WAV-encoded.
        recorded_at: ``time.time()`` when the memo was recorded.
    """

    id: int | None
    clip: bytes
    recorded_at: float
