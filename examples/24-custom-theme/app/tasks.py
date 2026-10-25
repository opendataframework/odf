"""Tasks for the custom-theme example."""

from opendataframework import Task

from app.repositories import HighScores


@Task
class Tally:
    """Totals every player's points across all games.

    Gives the topology a second node, wired to ``HighScores``, so the
    theme's icons and links have something to show.
    """

    def __init__(self, scores: HighScores) -> None:
        """Wire up the score table to total.

        Args:
            scores: The repository to read scores from.
        """
        self.scores = scores

    def execute(self) -> dict[str, int]:
        """Return each player's total points, highest first."""
        totals: dict[str, int] = {}
        for score in self.scores.all():
            totals[score.player] = totals.get(score.player, 0) + score.points
        return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))
