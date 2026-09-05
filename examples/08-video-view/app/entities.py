"""Entities for the video-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class SecurityClip:
    """A short security-camera clip shown via ``SecurityClips.data_view()``.

    Attributes:
        id: Primary key, ``None`` until ``SecurityClips.save()`` assigns one.
        label: A short human-readable label for the clip.
        clip: The clip, mp4-encoded.
        recorded_at: ``time.time()`` when the clip was recorded.
    """

    id: int | None
    label: str
    clip: bytes
    recorded_at: float
