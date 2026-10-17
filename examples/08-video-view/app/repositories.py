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

# (fourcc, file suffix), tried in order until a writer opens. H.264 plays in
# every browser but the opencv-python wheels for Linux ship without an
# encoder for it, VP8 plays everywhere but Safari, and MPEG-4 Part 2 is
# FFmpeg's built-in fallback, which the UI labels if the browser can't play it.
_CLIP_CODECS: tuple[tuple[str, str], ...] = (
    ("avc1", ".mp4"),
    ("VP80", ".webm"),
    ("mp4v", ".mp4"),
)


def synth_clip(seed: int) -> bytes:
    """Generate a short synthetic clip — a dot sweeping left to right,
    position/color derived from ``seed`` so each clip looks distinct.

    ``cv2.VideoWriter`` has no in-memory sink, so the clip is written to a
    temp file and read back as bytes. It is encoded with the first codec in
    ``_CLIP_CODECS`` this OpenCV build can write; the UI detects which one
    from the bytes.

    Raises:
        RuntimeError: If OpenCV can write none of ``_CLIP_CODECS``.
    """
    width, height = _CLIP_SIZE
    for fourcc, suffix in _CLIP_CODECS:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*fourcc), _CLIP_FPS, (width, height))
        try:
            if not writer.isOpened():
                continue
            color = (int(seed * 47) % 256, int(seed * 91) % 256, int(seed * 137) % 256)
            for frame_index in range(_CLIP_FRAME_COUNT):
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                x = int((frame_index / _CLIP_FRAME_COUNT) * width)
                cv2.circle(frame, (x, height // 2), 12, color, -1)
                writer.write(frame)
            writer.release()
            with open(path, "rb") as f:
                return f.read()
        finally:
            writer.release()
            os.remove(path)
    raise RuntimeError(f"OpenCV can't write any of {[c for c, _ in _CLIP_CODECS]}")


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
            SecurityClip(id=clip_id, label=label, clip=synth_clip(seed), recorded_at=now + offset)
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
