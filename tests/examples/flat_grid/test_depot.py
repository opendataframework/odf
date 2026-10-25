import json
import re
import tomllib
from pathlib import Path

from app.entities import Courier, Parcel
from app.functions import shipping_cost
from app.pipelines import NightlyRun
from app.repositories import Couriers, Parcels
from app.tasks import SortParcels
from opendataframework.logger import LogManager

# Deliberately builds the repositories, task and pipeline directly rather
# than going through Project/Context — same reason as the other examples'
# tests, see tests/examples/table_view/test_books.py. Each test that logs
# chdirs into tmp_path first, so no logs/ is written into the repo.

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_DIR = ROOT / "examples" / "25-flat-grid"
FLAT_JS = ROOT / "src" / "odf" / "ui" / "static" / "grids" / "flat.js"


def _sort_parcels(parcels):
    return SortParcels(parcels, LogManager().logger_for("SortParcels"))


def test_parcels_start_seeded_and_unsorted():
    parcels = Parcels()

    assert [p.destination for p in parcels.all()] == ["Lyon", "Porto", "Gdansk"]
    assert not any(p.sorted for p in parcels.all())


def test_parcels_save_assigns_ids_after_seed():
    parcels = Parcels()

    parcels.save(Parcel(id=None, destination="Ghent", weight_kg=1.0, sorted=False))

    assert [p.id for p in parcels.all()] == [1, 2, 3, 4]


def test_couriers_save_and_delete():
    couriers = Couriers()

    couriers.save(Courier(id=None, name="Aiko"))
    couriers.delete(1)

    assert [c.name for c in couriers.all()] == ["Tomasz", "Aiko"]


def test_sort_parcels_sorts_each_parcel_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parcels = Parcels()
    task = _sort_parcels(parcels)

    assert task.execute() == 3
    assert all(p.sorted for p in parcels.all())
    assert task.execute() == 0


def test_nightly_run_sorts_the_parcels(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    parcels = Parcels()

    NightlyRun(_sort_parcels(parcels)).execute()

    assert capsys.readouterr().out == "Sorted 3 parcel(s).\n"


def test_shipping_cost():
    assert shipping_cost(2.5) == 7.5


def test_config_picks_the_flat_grid():
    config = tomllib.loads((EXAMPLE_DIR / "config.toml").read_text())

    assert config["ui"]["grid"] == "flat"


def test_layout_gives_couriers_a_flat_glyph():
    layout = json.loads((EXAMPLE_DIR / "layout.json").read_text())
    glyphs = re.findall(r"^    ([a-z]+): \{ label:", FLAT_JS.read_text(), re.M)

    assert list(layout) == ["repository.couriers"]
    assert layout["repository.couriers"]["flatIcon"] in glyphs
