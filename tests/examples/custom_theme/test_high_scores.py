import tomllib

import pytest
from app.entities import Score
from app.repositories import HighScores
from app.tasks import Tally

from odf.ui import themes

from .conftest import EXAMPLE_DIR

# Deliberately builds HighScores directly rather than going through Project/
# Context — same reason as the other examples' tests, see
# tests/examples/table_view/test_books.py.


def test_high_scores_starts_pre_seeded():
    scores = HighScores()

    assert [s.player for s in scores.all()] == ["AAA", "JMP", "AAA", "ZED", "JMP"]


def test_high_scores_save_assigns_incrementing_ids_after_seed():
    scores = HighScores()

    scores.save(Score(id=None, player="NEW", game="Block Drop", points=100))

    assert [s.id for s in scores.all()] == [1, 2, 3, 4, 5, 6]


def test_high_scores_save_updates_existing_record():
    scores = HighScores()
    saved = scores.all()[0]

    saved.points = 50000
    scores.save(saved)

    assert len(scores.all()) == 5
    assert scores.all()[0].points == 50000


def test_high_scores_delete_removes_record():
    scores = HighScores()

    scores.delete(1)

    assert [s.id for s in scores.all()] == [2, 3, 4, 5]


def test_tally_totals_points_per_player_highest_first():
    assert Tally(HighScores()).execute() == {"AAA": 61100, "JMP": 41600, "ZED": 20400}


def test_config_selects_the_example_theme_by_path():
    config = tomllib.loads((EXAMPLE_DIR / "config.toml").read_text())

    assert config["ui"]["theme"] == "./pixel-theme"


@pytest.mark.parametrize("theme", ["./pixel-theme", "./park-theme", "./neon-theme"])
def test_example_theme_has_every_required_file(monkeypatch, theme):
    monkeypatch.chdir(EXAMPLE_DIR)

    path = themes.theme_dir(theme)

    assert (path / "theme.js").is_file()


@pytest.mark.parametrize(
    ("theme", "pixel_size"),
    [("./pixel-theme", True), ("./park-theme", True), ("./neon-theme", False)],
)
def test_only_the_pixel_art_themes_set_a_pixel_size(theme, pixel_size):
    script = (EXAMPLE_DIR / theme / "theme.js").read_text()

    assert ("pixelSize: 2" in script) is pixel_size
