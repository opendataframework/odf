"""In-memory repository backing the audio-view example."""

import time

from opendataframework import AudioView, Repository, Storage

from app.audio import synth_tone_wav
from app.entities import VoiceMemo

# (frequency in Hz, recorded_at offset in seconds from construction time) —
# so there are a couple of real memos to play without hand-triggering a
# save() first.
_SEED_MEMOS: tuple[tuple[float, float], ...] = (
    (440.0, -120.0),
    (523.25, -60.0),
)


@Storage
@Repository(VoiceMemo)
class VoiceMemos:
    """In-memory ``VoiceMemos`` repository, pre-seeded with ``_SEED_MEMOS``.

    Kept in-memory on purpose — the concept here is ``data_view()``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a memo list is a lot more useful to look
    at with a couple of real memos already in it than an empty one.
    """

    def __init__(self) -> None:
        """Seed the in-memory memo list from ``_SEED_MEMOS``."""
        now = time.time()
        self._memos: list[VoiceMemo] = [
            VoiceMemo(
                id=memo_id, clip=synth_tone_wav(frequency, 1.0, 8000), recorded_at=now + offset
            )
            for memo_id, (frequency, offset) in enumerate(_SEED_MEMOS, start=1)
        ]
        self._next_id = len(self._memos) + 1

    def all(self) -> list[VoiceMemo]:
        """Return every memo."""
        return list(self._memos)

    def save(self, memo: VoiceMemo) -> None:
        """Create or update a memo.

        Args:
            memo: The memo to persist. An unset ``id`` creates a new record
                and has one assigned; a set ``id`` updates the matching
                record in place.
        """
        if memo.id is None:
            memo.id = self._next_id
            self._next_id += 1
            self._memos.append(memo)
            return
        for i, existing in enumerate(self._memos):
            if existing.id == memo.id:
                self._memos[i] = memo
                return

    def delete(self, memo_id: int) -> None:
        """Delete the memo matching ``memo_id``, if one exists.

        Args:
            memo_id: The ``id`` of the memo to remove.
        """
        self._memos = [m for m in self._memos if m.id != memo_id]

    def data_view(self) -> AudioView:
        """Tell the UI to render these records as playable audio, not a table.

        Returns:
            An ``AudioView`` keyed on the ``clip`` field.
        """
        return AudioView(field="clip")
