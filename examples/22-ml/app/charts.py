"""Comparing runs: the ``RunComparison`` chart component."""

import math
from html import escape

from opendataframework import Analytics, Component

from app.repositories import Metrics, Params, Runs

_W, _H, _PAD = 640, 320, 48


@Analytics
@Component
class RunComparison:
    """Each finished run's final loss against its learning rate, one point
    per run, so the sweep's best setting stands out. Plain SVG, rebuilt from
    the repositories every time the chart is opened."""

    def __init__(self, runs: Runs, params: Params, metrics: Metrics) -> None:
        """Store the repositories the chart is drawn from.

        Args:
            runs: The runs to plot.
            params: Where each run's learning rate is read from.
            metrics: Where each run's final loss is read from.
        """
        self.runs = runs
        self.params = params
        self.metrics = metrics

    def points(self) -> list[tuple[str, float, float]]:
        """Return ``(run name, learning rate, final loss)`` for each run that
        has a learning rate and at least one metric row."""
        points = []
        for run in self.runs.all():
            learning_rate = self.params.for_run(run.id).get("learning_rate")
            steps = self.metrics.for_run(run.id)
            if learning_rate is not None and steps:
                points.append((run.name, float(learning_rate), steps[-1].loss))
        return points

    def chart(self) -> str:
        """Render final loss against learning rate, the best run highlighted.

        Returns:
            A self-contained HTML document with an inline SVG chart.
        """
        points = self.points()
        if not points:
            return _page("<p>No runs yet. Execute the sweep task to record some.</p>")

        # Learning rates span orders of magnitude, so they go on a log axis.
        xs = [math.log10(lr) for _, lr, _ in points]
        ys = [loss for _, _, loss in points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        def x(value: float) -> float:
            span = x_max - x_min
            return _W / 2 if span == 0 else _PAD + (value - x_min) / span * (_W - 2 * _PAD)

        def y(value: float) -> float:
            span = y_max - y_min
            return _H / 2 if span == 0 else _H - _PAD - (value - y_min) / span * (_H - 2 * _PAD)

        best = min(points, key=lambda p: p[2])
        marks = ""
        for point in points:
            name, lr, loss = point
            cx, cy = x(math.log10(lr)), y(loss)
            css = ' class="best"' if point is best else ""
            marks += (
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5"{css}/>'
                f'<text x="{cx:.1f}" y="{cy - 10:.1f}">{escape(name)} · {loss}</text>'
            )
        svg = (
            f'<svg viewBox="0 0 {_W} {_H}">'
            f'<line class="axis" x1="{_PAD}" y1="{_H - _PAD}" x2="{_W - _PAD}" y2="{_H - _PAD}"/>'
            f'<line class="axis" x1="{_PAD}" y1="{_PAD}" x2="{_PAD}" y2="{_H - _PAD}"/>'
            f'<text class="label" x="{_W / 2}" y="{_H - 12}">learning rate (log scale)</text>'
            f'<text class="label" x="14" y="{_H / 2}" transform="rotate(-90 14 {_H / 2})">'
            "final loss</text>"
            f"{marks}</svg>"
        )
        return _page(f"<h1>Final loss by learning rate</h1>{svg}<p>Best: {escape(best[0])}</p>")


def _page(body: str) -> str:
    """Wrap ``body`` in an HTML page styled for both light and dark themes."""
    return (
        "<html><head><style>"
        ":root{color-scheme:light dark;font-family:system-ui,sans-serif;font-size:13px}"
        "h1{font-size:15px;font-weight:600}"
        "svg{width:100%;max-width:640px;height:auto}"
        "circle{fill:#B36AE2}circle.best{fill:#2bb673}"
        "text{fill:currentColor;text-anchor:middle;font-size:11px}"
        ".axis{stroke:currentColor;opacity:.4}"
        "</style></head><body>"
        f"{body}</body></html>"
    )
