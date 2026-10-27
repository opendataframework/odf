import math
from html import escape

from opendataframework import Analytics, Component

from app.repositories import Metrics, Params, Runs

_W, _H, _PAD = 640, 320, 48


@Analytics
@Component
class RunComparison:
    """Each run's final loss and accuracy against its learning rate, one
    point per run, so the sweep's best setting stands out. Plain SVG,
    rebuilt from the repositories every time the chart is opened."""

    def __init__(self, runs: Runs, params: Params, metrics: Metrics) -> None:
        self.runs = runs
        self.params = params
        self.metrics = metrics

    def points(self) -> list[tuple[str, float, float, float]]:
        """Return ``(run name, learning rate, final loss, final accuracy)``
        for each run that has a learning rate and at least one metric row."""
        points = []
        for run in self.runs.all():
            learning_rate = self.params.for_run(run.id).get("learning_rate")
            steps = self.metrics.for_run(run.id)
            if learning_rate is not None and steps:
                points.append((run.name, float(learning_rate), steps[-1].loss, steps[-1].accuracy))
        return points

    def chart(self) -> str:
        points = self.points()
        if not points:
            return _page("<p>No runs yet. Execute the sweep task to record some.</p>")

        # Learning rates span orders of magnitude, so they go on a log axis.
        # Loss and accuracy share the y axis, both being around 0 to 1.
        rates = sorted({lr for _, lr, _, _ in points})
        x_min, x_max = math.log10(rates[0]), math.log10(rates[-1])
        values = [v for _, _, loss, accuracy in points for v in (loss, accuracy)]
        y_min, y_max = min(0.0, min(values)), max(1.0, max(values))

        def x(lr: float) -> float:
            span = x_max - x_min
            return _W / 2 if span == 0 else _PAD + (math.log10(lr) - x_min) / span * (_W - 2 * _PAD)

        def y(value: float) -> float:
            return _H - _PAD - (value - y_min) / (y_max - y_min) * (_H - 2 * _PAD)

        ticks = "".join(
            f'<text class="tick" x="{x(lr):.1f}" y="{_H - _PAD + 16}">{lr:g}</text>' for lr in rates
        ) + "".join(
            f'<line class="grid" x1="{_PAD}" y1="{y(v):.1f}" x2="{_W - _PAD}" y2="{y(v):.1f}"/>'
            f'<text class="tick" x="{_PAD - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v:g}</text>'
            for v in (y_min, (y_min + y_max) / 2, y_max)
        )
        best = min(points, key=lambda p: p[2])
        marks = ""
        for point in points:
            name, lr, loss, accuracy = point
            css = " best" if point is best else ""
            marks += (
                f'<circle class="loss{css}" cx="{x(lr):.1f}" cy="{y(loss):.1f}" r="5">'
                f"<title>{escape(name)}: loss {loss}</title></circle>"
                f'<rect class="accuracy" x="{x(lr) - 4:.1f}" y="{y(accuracy) - 4:.1f}" '
                f'width="8" height="8"><title>{escape(name)}: accuracy {accuracy}</title></rect>'
            )
        svg = (
            f'<svg viewBox="0 0 {_W} {_H}">{ticks}'
            f'<line class="axis" x1="{_PAD}" y1="{_H - _PAD}" x2="{_W - _PAD}" y2="{_H - _PAD}"/>'
            f'<line class="axis" x1="{_PAD}" y1="{_PAD}" x2="{_PAD}" y2="{_H - _PAD}"/>'
            f'<text class="label" x="{_W / 2}" y="{_H - 10}">learning rate (log scale)</text>'
            f"{marks}</svg>"
        )
        legend = (
            '<p class="legend"><span class="dot loss"></span>final loss '
            '<span class="dot accuracy"></span>final accuracy '
            '<span class="dot best"></span>best run</p>'
        )
        return _page(
            f"<h1>Final loss and accuracy by learning rate</h1>{legend}{svg}"
            f"<p>Best: {escape(best[0])}, loss {best[2]}, accuracy {best[3]}</p>"
        )


def _page(body: str) -> str:
    return (
        "<html><head><style>"
        ":root{color-scheme:light dark;font-family:system-ui,sans-serif;font-size:13px}"
        "h1{font-size:15px;font-weight:600}"
        "svg{width:100%;max-width:640px;height:auto}"
        ".loss{fill:#B36AE2}.accuracy{fill:#3b9ddd}.loss.best{fill:#2bb673}"
        "text{fill:currentColor;text-anchor:middle;font-size:11px}"
        ".axis{stroke:currentColor;opacity:.4}.grid{stroke:currentColor;opacity:.1}"
        ".tick{opacity:.7}"
        ".legend .dot{display:inline-block;width:9px;height:9px;border-radius:50%;"
        "margin:0 4px 0 10px}"
        ".dot.loss{background:#B36AE2}.dot.accuracy{background:#3b9ddd;border-radius:1px}"
        ".dot.best{background:#2bb673}"
        "</style></head><body>"
        f"{body}</body></html>"
    )
