"""In-memory repository backing the video-view example."""

import os
import tempfile
import time

import cv2
import numpy as np
from opendataframework import Repository, Storage, VideoView

from app.entities import SecurityClip

_CLIP_SIZE = (160, 120)  # (width, height)
_CLIP_FPS = 12
_CLIP_FRAME_COUNT = 24


def synth_clip_mp4(seed: int) -> bytes:
    """Generate a short synthetic mp4 clip — a dot sweeping left to right,
    position/color derived from ``seed`` so each clip looks distinct.

    ``cv2.VideoWriter`` has no in-memory sink, so the clip is written to a
    temp file and read back as bytes.
    """
    width, height = _CLIP_SIZE
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"avc1"), _CLIP_FPS, (width, height))
    try:
        color = (int(seed * 47) % 256, int(seed * 91) % 256, int(seed * 137) % 256)
        for frame_index in range(_CLIP_FRAME_COUNT):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            x = int((frame_index / _CLIP_FRAME_COUNT) * width)
            cv2.circle(frame, (x, height // 2), 12, color, -1)
            writer.write(frame)
    finally:
        writer.release()
    with open(path, "rb") as f:
        clip_bytes = f.read()
    os.remove(path)
    return clip_bytes


# (label, seed, recorded_at offset in seconds from construction time) — so
# there are a couple of real clips to watch without hand-triggering a
# save() first.
_SEED_CLIPS: tuple[tuple[str, int, float], ...] = (
    ("front-door", 1, -120.0),
    ("loading-dock", 2, -60.0),
)


@Storage
@Repository(SecurityClip)
class SecurityClips:
    """In-memory ``SecurityClips`` repository, pre-seeded with ``_SEED_CLIPS``.

    Kept in-memory on purpose — the concept here is ``data_view()``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a clip list is a lot more useful to look
    at with a couple of real clips already in it than an empty one.
    """

    def __init__(self) -> None:
        """Seed the in-memory clip list from ``_SEED_CLIPS``."""
        now = time.time()
        self._clips: list[SecurityClip] = [
            SecurityClip(
                id=clip_id, label=label, clip=synth_clip_mp4(seed), recorded_at=now + offset
            )
            for clip_id, (label, seed, offset) in enumerate(_SEED_CLIPS, start=1)
        ]
        self._next_id = len(self._clips) + 1

    def all(self) -> list[SecurityClip]:
        """Return every clip."""
        return list(self._clips)

    def save(self, clip: SecurityClip) -> None:
        """Create or update a clip.

        Args:
            clip: The clip to persist. An unset ``id`` creates a new record
                and has one assigned; a set ``id`` updates the matching
                record in place.
        """
        if clip.id is None:
            clip.id = self._next_id
            self._next_id += 1
            self._clips.append(clip)
            return
        for i, existing in enumerate(self._clips):
            if existing.id == clip.id:
                self._clips[i] = clip
                return

    def delete(self, clip_id: int) -> None:
        """Delete the clip matching ``clip_id``, if one exists.

        Args:
            clip_id: The ``id`` of the clip to remove.
        """
        self._clips = [c for c in self._clips if c.id != clip_id]

    def data_view(self) -> VideoView:
        """Tell the UI to render these records as playable video, not a table.

        Returns:
            A ``VideoView`` keyed on the ``clip`` field.
        """
        return VideoView(field="clip")
