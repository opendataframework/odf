import csv
import json
import pickle  # nosec B403 — unpickles only the model the test itself just trained
from functools import partial
from pathlib import Path

import pytest
from app.charts import RunComparison
from app.entities import Artifact, Run
from app.exports import export_run
from app.repositories import Artifacts, Metrics, Params, Runs
from app.storages import SQLite
from app.tasks import Sweep
from app.training import load_data, train
from opendataframework.component import ChartProtocol
from opendataframework.config import Config
from opendataframework.view import ContentMetadata, DocumentView, TimeseriesView

# Deliberately builds SQLite and the repositories directly rather than going
# through Project/Context — same reason as the other examples' tests (see
# tests/examples/entity_repository/test_books.py): registration is global
# for the whole pytest process.


class _Logger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, message: str) -> None:
        self.lines.append(message)


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        {
            "component": {"sqlite": {"path": str(tmp_path / "test.db")}},
            "task": {"sweep": {"learning-rates": [0.001, 0.1, 1.0], "epochs": 3}},
        }
    )


@pytest.fixture
def repos(config) -> dict:
    sqlite = SQLite(config)
    return {
        "runs": Runs(sqlite),
        "params": Params(sqlite),
        "metrics": Metrics(sqlite),
        "artifacts": Artifacts(sqlite),
    }


def test_train_records_a_run_with_params_metrics_a_summary_and_a_model(repos):
    summary = train(0.1, 3, **repos)

    [run] = repos["runs"].all()
    assert run.name == "lr=0.1"
    assert run.status == "finished"
    assert run.finished_at >= run.started_at
    assert repos["params"].for_run(run.id) == {"learning_rate": "0.1", "epochs": "3"}
    steps = repos["metrics"].for_run(run.id)
    assert [m.step for m in steps] == [1, 2, 3]
    assert summary["final"] == {"loss": steps[-1].loss, "accuracy": steps[-1].accuracy}
    saved, model = repos["artifacts"].for_run(run.id)
    assert (saved.name, saved.content) == ("summary", summary)
    assert model.name == "model.pkl"
    assert isinstance(model.content, bytes)


def test_the_saved_model_takes_raw_digits_and_predicts_them(repos):
    train(0.1, 3, **repos)

    model = pickle.loads(repos["artifacts"].for_run(1)[1].content)  # nosec B301
    _, X_test, _, y_test = load_data()
    assert (model.predict(X_test) == y_test).mean() > 0.9


def test_training_is_deterministic(repos):
    first = train(0.1, 3, **repos)
    second = train(0.1, 3, **repos)

    assert first["final"] == second["final"]


def test_sweep_records_one_run_per_learning_rate_with_a_clear_best(config, repos):
    logger = _Logger()
    sweep = Sweep(config, logger, partial(train, **repos))

    summaries = sweep.execute()

    assert [s["run"] for s in summaries] == ["lr=0.001", "lr=0.1", "lr=1.0"]
    assert len(repos["runs"].all()) == 3
    assert len(repos["metrics"].all()) == 3 * 3
    assert logger.lines == ["swept 3 runs, best: lr=0.1"]


def test_export_run_writes_params_metrics_and_every_artifact(repos, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    summary = train(0.1, 3, **repos)

    folder = Path(export_run(summary["run_id"], **repos))

    assert folder == Path("exports") / "1-lr-0.1"
    assert sorted(p.name for p in folder.iterdir()) == [
        "metrics.csv",
        "model.pkl",
        "params.json",
        "summary.json",
    ]
    assert json.loads((folder / "params.json").read_text()) == {
        "learning_rate": "0.1",
        "epochs": "3",
    }
    with open(folder / "metrics.csv", newline="") as f:
        assert [row["step"] for row in csv.DictReader(f)] == ["1", "2", "3"]
    assert json.loads((folder / "summary.json").read_text()) == summary
    assert (folder / "model.pkl").read_bytes() == repos["artifacts"].for_run(1)[1].content


def test_export_run_rejects_an_unknown_run(repos):
    with pytest.raises(ValueError, match="no run with id 7"):
        export_run(7, **repos)


def test_artifacts_name_files_for_download_and_leave_json_alone(repos):
    artifacts = repos["artifacts"]

    model = Artifact(id=None, run_id=1, name="model.pkl", content=b"\x80\x05")
    summary = Artifact(id=None, run_id=1, name="summary", content={"loss": 0.3})
    artifacts.save(model)
    artifacts.save(summary)

    assert artifacts.content_metadata(model) == ContentMetadata(
        filename="model.pkl", content_type="application/octet-stream"
    )
    assert artifacts.content_metadata(summary) == ContentMetadata()
    assert [a.content for a in artifacts.all()] == [b"\x80\x05", {"loss": 0.3}]


def test_deleting_a_run_removes_what_it_recorded(repos):
    train(0.1, 2, **repos)
    kept = train(1.0, 2, **repos)

    repos["runs"].delete(repos["runs"].all()[0].id)

    assert [r.id for r in repos["runs"].all()] == [kept["run_id"]]
    assert {m.run_id for m in repos["metrics"].all()} == {kept["run_id"]}
    assert {p.run_id for p in repos["params"].all()} == {kept["run_id"]}
    assert {a.run_id for a in repos["artifacts"].all()} == {kept["run_id"]}


def test_runs_save_updates_an_existing_run(repos):
    run = Run(id=None, name="draft", status="running", started_at=1.0)
    repos["runs"].save(run)

    run.status = "finished"
    repos["runs"].save(run)

    assert repos["runs"].get(run.id).status == "finished"
    assert repos["runs"].get(run.id + 1) is None


def test_metrics_chart_one_line_per_run_and_artifacts_open_as_documents(repos):
    assert repos["metrics"].data_view() == TimeseriesView(
        field="step", fields=("loss", "accuracy"), group="run_id"
    )
    assert repos["artifacts"].data_view() == DocumentView(field="content")


def test_run_comparison_conforms_to_chart_protocol(repos):
    assert isinstance(
        RunComparison(repos["runs"], repos["params"], repos["metrics"]), ChartProtocol
    )


def test_run_comparison_shows_an_empty_state_without_runs(repos):
    html = RunComparison(repos["runs"], repos["params"], repos["metrics"]).chart()

    assert "No runs yet. Execute Sweep to record some." in html


def test_run_comparison_draws_every_run_and_ranks_them(repos):
    chart = RunComparison(repos["runs"], repos["params"], repos["metrics"])
    train(0.001, 2, **repos)
    train(0.1, 2, **repos)

    rows = chart.rows()
    html = chart.chart()

    assert [row["name"] for row in rows] == ["lr=0.001", "lr=0.1"]
    assert html.startswith("<!doctype html>")
    assert 'id="runs-chart"' in html
    assert "best: lr=0.1" in html
    # One row per run in the ranked table, the best one first.
    assert html.count("<tr") == 1 + 2
    assert html.index("lr=0.1</td>") < html.index("lr=0.001</td>")
