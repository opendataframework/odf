import tomllib

from app.entities import Account
from app.repositories import Accounts
from app.tasks import Revenue

from odf.ui import themes

from .conftest import EXAMPLE_DIR

# Deliberately builds Accounts directly rather than going through Project/
# Context — same reason as the other examples' tests, see
# tests/examples/table_view/test_books.py.


def test_accounts_starts_pre_seeded():
    accounts = Accounts()

    assert [a.name for a in accounts.all()] == [
        "Northwind Labs",
        "Brightline",
        "Kestrel Analytics",
        "Fieldnote",
        "Parallel Studio",
    ]


def test_accounts_save_assigns_incrementing_ids_after_seed():
    accounts = Accounts()

    accounts.save(Account(id=None, name="Lumen", plan="Pro", mrr=490))

    assert [a.id for a in accounts.all()] == [1, 2, 3, 4, 5, 6]


def test_accounts_save_updates_existing_record():
    accounts = Accounts()
    saved = accounts.all()[3]

    saved.plan = "Pro"
    saved.mrr = 290
    accounts.save(saved)

    assert len(accounts.all()) == 5
    assert accounts.all()[3].plan == "Pro"


def test_accounts_delete_removes_record():
    accounts = Accounts()

    accounts.delete(1)

    assert [a.id for a in accounts.all()] == [2, 3, 4, 5]


def test_revenue_totals_mrr_per_plan_highest_first():
    assert Revenue(Accounts()).execute() == {"Enterprise": 8000, "Pro": 780, "Free": 0}


def test_config_selects_the_example_theme_by_path():
    config = tomllib.loads((EXAMPLE_DIR / "config.toml").read_text())

    assert config["ui"]["theme"] == "./themes/ink"


def test_example_theme_has_every_required_file(monkeypatch):
    monkeypatch.chdir(EXAMPLE_DIR)

    path = themes.theme_dir("./themes/ink")

    assert (path / "theme.js").is_file()


def test_example_theme_keeps_the_canvas_at_full_resolution():
    script = (EXAMPLE_DIR / "themes" / "ink" / "theme.js").read_text()

    assert "pixelSize" not in script
