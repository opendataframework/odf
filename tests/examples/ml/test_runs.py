from functools import partial

import pytest
from app.charts import RunComparison
from app.entities import Run
from app.repositories import Artifacts, Metrics, Params, Runs
from app.storages import SQLite
from app.tasks import Sweep
from app.training import simulate_step, train
from opendataframework.component import ChartProtocol
from opendataframework.config import Config
from opendataframework.view import DocumentView, TimeseriesView

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
            "task": {"sweep": {"learning-rates": [0.01, 0.1, 0.5], "epochs": 4}},
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


def test_train_records_a_run_with_params_metrics_and_an_artifact(repos):
    summary = train(0.1, 5, **repos)

    [run] = repos["runs"].all()
    assert run.name == "lr=0.1"
    assert run.status == "finished"
    assert run.finished_at >= run.started_at
    assert repos["params"].for_run(run.id) == {"learning_rate": "0.1", "epochs": "5"}
    steps = repos["metrics"].for_run(run.id)
    assert [m.step for m in steps] == [1, 2, 3, 4, 5]
    [artifact] = repos["artifacts"].all()
    assert artifact.run_id == run.id
    assert artifact.content == summary
    assert summary["final"] == {"loss": steps[-1].loss, "accuracy": steps[-1].accuracy}


def test_simulated_training_is_deterministic_and_best_near_point_one():
    assert simulate_step(0.1, 3) == simulate_step(0.1, 3)

    final = {lr: simulate_step(lr, 6)[0] for lr in (0.01, 0.1, 0.5)}
    assert min(final, key=final.get) == 0.1


def test_sweep_records_one_run_per_learning_rate(config, repos):
    logger = _Logger()
    sweep = Sweep(config, logger, partial(train, **repos))

    summaries = sweep.execute()

    assert [s["run"] for s in summaries] == ["lr=0.01", "lr=0.1", "lr=0.5"]
    assert len(repos["runs"].all()) == 3
    assert len(repos["metrics"].all()) == 3 * 4
    assert logger.lines == ["swept 3 runs, best: lr=0.1"]


def test_deleting_a_run_removes_what_it_recorded(repos):
    train(0.1, 3, **repos)
    kept = train(0.5, 3, **repos)

    repos["runs"].delete(repos["runs"].all()[0].id)

    assert [r.id for r in repos["runs"].all()] == [kept["run_id"]]
    assert {m.run_id for m in repos["metrics"].all()} == {kept["run_id"]}
    assert {p.run_id for p in repos["params"].all()} == {kept["run_id"]}
    assert [a.run_id for a in repos["artifacts"].all()] == [kept["run_id"]]


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


def test_run_comparison_plots_each_run_and_reflects_live_data(repos):
    chart = RunComparison(repos["runs"], repos["params"], repos["metrics"])

    empty = chart.chart()
    train(0.01, 4, **repos)
    train(0.1, 4, **repos)

    assert "No runs yet" in empty
    assert [name for name, _, _ in chart.points()] == ["lr=0.01", "lr=0.1"]
    html = chart.chart()
    assert html.startswith("<html>")
    assert html.count("<circle") == 2
    assert "Best: lr=0.1" in html
