"""In-memory repository backing the custom-theme example."""

from opendataframework import Repository, Storage

from app.entities import Score

# (player, game, points): a few games to look at without hand-typing
# records through the UI first.
_SEED_SCORES: tuple[tuple[str, str, int], ...] = (
    ("AAA", "Star Raiders", 48200),
    ("JMP", "Star Raiders", 31750),
    ("AAA", "Block Drop", 12900),
    ("ZED", "Block Drop", 20400),
    ("JMP", "Maze Muncher", 9850),
)


@Storage
@Repository(Score)
class HighScores:
    """In-memory ``Score`` repository, pre-seeded with ``_SEED_SCORES``.

    Implements no ``data_view()``. The concept this example isolates is the
    project's own UI theme (see ``../themes/pixel/`` and this project's
    ``config.toml``), so it renders as the same plain default table as
    ../01-table-view, in the theme's look.
    """

    def __init__(self) -> None:
        """Seed the in-memory score list from ``_SEED_SCORES``."""
        self._scores: list[Score] = [
            Score(id=score_id, player=player, game=game, points=points)
            for score_id, (player, game, points) in enumerate(_SEED_SCORES, start=1)
        ]
        self._next_id = len(self._scores) + 1

    def all(self) -> list[Score]:
        """Return every score."""
        return list(self._scores)

    def save(self, score: Score) -> None:
        """Create or update a score.

        Args:
            score: The score to persist. An unset ``id`` creates a new record
                and has one assigned; a set ``id`` updates the matching
                record in place.
        """
        if score.id is None:
            score.id = self._next_id
            self._next_id += 1
            self._scores.append(score)
            return
        for i, existing in enumerate(self._scores):
            if existing.id == score.id:
                self._scores[i] = score
                return

    def delete(self, score_id: int) -> None:
        """Delete the score matching ``score_id``, if one exists.

        Args:
            score_id: The ``id`` of the score to remove.
        """
        self._scores = [s for s in self._scores if s.id != score_id]
