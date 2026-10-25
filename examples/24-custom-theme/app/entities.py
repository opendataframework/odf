"""Entities for the custom-theme example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Score:
    """One finished game on the arcade's high score table.

    Attributes:
        id: Primary key, ``None`` until ``HighScores.save()`` assigns one.
        player: The player's three-letter initials.
        game: The cabinet the game was played on.
        points: The final score.
    """

    id: int | None
    player: str
    game: str
    points: int
