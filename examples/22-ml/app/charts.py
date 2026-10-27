"""Comparing runs: the ``RunComparison`` chart component.

The template's ``RunComparison`` draws one plain SVG scatter with the
standard library. This one is the fuller version, built with Plotly: final
loss and accuracy by learning rate, every run's loss curve, and a ranked
table, interactive and in the UI's own theme.
"""

import json
from html import escape

import plotly.graph_objects as go
from opendataframework import Analytics, Component
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots

from app.repositories import Metrics, Params, Runs

# Used until the page reads the UI's own colors, and when the chart is opened
# outside the UI. In the UI, run i takes the color the grouped timeseries
# gives group i: the --accent-* below, in this order.
_ACCENTS = ("repository", "component", "service", "task", "pipeline")
_FALLBACK_COLORS = ("#7c6cf2", "#e2a03f", "#2bb673", "#3b9ddd", "#e05a7a")

_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<script>{plotlyjs}</script>
<style>
  :root {{ color-scheme: light dark; --bg: #ffffff; --text: #1f2328; --dim: #6b7280;
          --border: #e5e7eb; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #16161a; --text: #e6e6e6; --dim: #9aa0a6; --border: #2c2f36; }}
  }}
  body {{ margin: 0; padding: 16px 20px; background: var(--bg); color: var(--text);
         font: 13px/1.45 system-ui, sans-serif; }}
  h1 {{ font-size: 16px; font-weight: 600; margin: 0 0 2px; }}
  .sub {{ color: var(--dim); margin: 0 0 8px; }}
  .best-pill {{ display: inline-block; padding: 1px 8px; border-radius: 999px;
               border: 1px solid var(--border); margin-left: 6px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 8px;
          font-variant-numeric: tabular-nums; }}
  th, td {{ text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--dim); font-weight: 500; font-size: 12px; }}
  th:nth-child(-n+2), td:nth-child(-n+2) {{ text-align: left; }}
  tr.best td {{ font-weight: 600; }}
  .swatch {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%;
            margin-right: 8px; vertical-align: -1px; }}
  .empty {{ color: var(--dim); padding: 40px 0; text-align: center; }}
</style>
</head>
<body>
{body}
<script>
(function () {{
  const accents = {accents};
  const fallback = {fallback};
  // The UI's colors when opened inside it (the chart's frame is on the same
  // origin), otherwise the page's own light/dark ones.
  function theme() {{
    const own = getComputedStyle(document.documentElement);
    const ownVar = n => own.getPropertyValue(n).trim();
    let t = {{ bg: ownVar('--bg'), text: ownVar('--text'), dim: ownVar('--dim'),
              border: ownVar('--border'), palette: fallback }};
    try {{
      const ui = getComputedStyle(window.parent.document.documentElement);
      const uiVar = n => ui.getPropertyValue(n).trim();
      if (window.parent !== window && uiVar('--text')) {{
        t = {{ bg: uiVar('--panel') || t.bg, text: uiVar('--text'),
              dim: uiVar('--text-dim') || t.dim, border: uiVar('--border') || t.border,
              palette: accents.map((k, i) => uiVar('--accent-' + k) || fallback[i]) }};
      }}
    }} catch (e) {{}}
    return t;
  }}
  function apply() {{
    const t = theme();
    const root = document.documentElement.style;
    root.setProperty('--bg', t.bg); root.setProperty('--text', t.text);
    root.setProperty('--dim', t.dim); root.setProperty('--border', t.border);
    const color = i => t.palette[i % t.palette.length];
    document.querySelectorAll('[data-run-index]').forEach(el => {{
      el.style.background = color(Number(el.dataset.runIndex));
    }});
    const gd = document.getElementById('runs-chart');
    if (!gd || !window.Plotly) return;
    const layout = {{ 'font.color': t.text, 'legend.font.color': t.text }};
    for (const key of Object.keys(gd.layout)) {{
      if (/^[xy]axis\\d*$/.test(key)) {{
        layout[key + '.gridcolor'] = t.border;
        layout[key + '.linecolor'] = t.border;
        layout[key + '.zerolinecolor'] = t.border;
      }}
    }}
    (gd.layout.annotations || []).forEach((_, i) => {{
      layout[`annotations[${{i}}].font.color`] = t.text;
    }});
    Plotly.relayout(gd, layout);
    const colors = gd.data.map(trace => color(trace.meta));
    Plotly.restyle(gd, {{ 'marker.color': colors, 'line.color': colors }});
  }}
  apply();
  try {{
    new MutationObserver(apply).observe(window.parent.document.documentElement,
      {{ attributes: true, attributeFilter: ['data-theme', 'class', 'style'] }});
  }} catch (e) {{}}
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', apply);
}})();
</script>
</body>
</html>"""


@Analytics
@Component
class RunComparison:
    """Every run side by side, so the sweep's best setting stands out.

    One page with three panels and a table: each run's final loss and final
    accuracy against its learning rate (log scale), each run's loss curve by
    step, and the runs ranked by final loss with their params, best step and
    duration. A run keeps one color everywhere, the one the ``Metrics``
    timeseries gives it, and clicking it in the legend hides it in every
    panel. Rebuilt from the repositories every time the chart is opened.
    """

    def __init__(self, runs: Runs, params: Params, metrics: Metrics) -> None:
        """Store the repositories the chart is drawn from.

        Args:
            runs: The runs to compare.
            params: Where each run's parameters are read from.
            metrics: Where each run's per-step metrics are read from.
        """
        self.runs = runs
        self.params = params
        self.metrics = metrics

    def rows(self) -> list[dict]:
        """Return one row per run that has a learning rate and metrics, in
        ``run_id`` order: its name, params, steps, and final and best values."""
        rows = []
        for run in self.runs.all():
            params = self.params.for_run(run.id)
            steps = self.metrics.for_run(run.id)
            if "learning_rate" not in params or not steps:
                continue
            best = min(steps, key=lambda m: m.loss)
            rows.append(
                {
                    "name": run.name,
                    "params": params,
                    "learning_rate": float(params["learning_rate"]),
                    "steps": [m.step for m in steps],
                    "losses": [m.loss for m in steps],
                    "loss": steps[-1].loss,
                    "accuracy": steps[-1].accuracy,
                    "best_step": best.step,
                    "duration": (run.finished_at - run.started_at) if run.finished_at else None,
                }
            )
        return rows

    def chart(self) -> str:
        """Render the comparison page.

        Returns:
            A self-contained HTML document with the Plotly chart, its inlined
            JS bundle and the ranked table.
        """
        rows = self.rows()
        if not rows:
            body = (
                "<h1>Run comparison</h1>"
                '<p class="empty">No runs yet. Execute Sweep to record some.</p>'
            )
            return self._page(body)

        best = min(rows, key=lambda r: r["loss"])
        body = (
            "<h1>Run comparison</h1>"
            f'<p class="sub">{len(rows)} run{"s" if len(rows) != 1 else ""}'
            f'<span class="best-pill">best: {escape(best["name"])} · loss {best["loss"]}'
            f" · accuracy {best['accuracy']}</span></p>"
            + self._figure(rows, best).to_html(
                full_html=False,
                include_plotlyjs=False,
                div_id="runs-chart",
                config={"displayModeBar": False, "responsive": True},
            )
            + self._table(rows, best)
        )
        return self._page(body)

    def _figure(self, rows: list[dict], best: dict) -> go.Figure:
        """Build the three panels, one legend entry per run."""
        fig = make_subplots(
            rows=2,
            cols=2,
            specs=[[{}, {}], [{"colspan": 2}, None]],
            subplot_titles=(
                "Final loss by learning rate",
                "Final accuracy by learning rate",
                "Loss by step",
            ),
            vertical_spacing=0.17,
            horizontal_spacing=0.1,
        )
        for i, row in enumerate(rows):
            is_best = row is best
            color = _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)]
            params = ", ".join(f"{k}={v}" for k, v in row["params"].items())
            shared = {"legendgroup": row["name"], "meta": i}
            marker = {
                "color": color,
                "size": 14 if is_best else 10,
                "symbol": "star" if is_best else "circle",
            }
            fig.add_trace(
                go.Scatter(
                    x=[row["learning_rate"]],
                    y=[row["loss"]],
                    mode="markers",
                    name=row["name"],
                    marker=marker,
                    hovertemplate=f"<b>{row['name']}</b><br>{params}<br>"
                    "final loss %{y}<extra></extra>",
                    **shared,
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=[row["learning_rate"]],
                    y=[row["accuracy"]],
                    mode="markers",
                    name=row["name"],
                    showlegend=False,
                    marker=marker,
                    hovertemplate=f"<b>{row['name']}</b><br>{params}<br>"
                    "final accuracy %{y}<extra></extra>",
                    **shared,
                ),
                row=1,
                col=2,
            )
            fig.add_trace(
                go.Scatter(
                    x=row["steps"],
                    y=row["losses"],
                    mode="lines+markers",
                    name=row["name"],
                    showlegend=False,
                    line={"color": color, "width": 3.5 if is_best else 1.6},
                    marker={"color": color, "size": 6 if is_best else 4},
                    hovertemplate=f"<b>{row['name']}</b><br>"
                    "step %{x}: loss %{y}<extra></extra>",
                    **shared,
                ),
                row=2,
                col=1,
            )
        fig.update_xaxes(type="log", title_text="learning rate", row=1, col=1)
        fig.update_xaxes(type="log", title_text="learning rate", row=1, col=2)
        fig.update_xaxes(title_text="step", dtick=1, row=2, col=1)
        fig.update_yaxes(title_text="loss", row=1, col=1)
        fig.update_yaxes(title_text="accuracy", row=1, col=2)
        fig.update_yaxes(title_text="loss", row=2, col=1)
        fig.update_layout(
            height=620,
            margin={"l": 56, "r": 16, "t": 56, "b": 48},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "system-ui, sans-serif", "size": 12},
            legend={"orientation": "h", "y": 1.12, "x": 0, "title": {"text": "runs "}},
            hovermode="closest",
        )
        return fig

    def _table(self, rows: list[dict], best: dict) -> str:
        """Render the runs ranked by final loss, with their params."""
        index = {id(row): i for i, row in enumerate(rows)}
        body = ""
        for rank, row in enumerate(sorted(rows, key=lambda r: r["loss"]), start=1):
            duration = f"{row['duration']:.2f} s" if row["duration"] is not None else "—"
            body += (
                f"<tr{' class=best' if row is best else ''}>"
                f"<td>{rank}</td>"
                f'<td><span class="swatch" data-run-index="{index[id(row)]}"></span>'
                f"{escape(row['name'])}</td>"
                f"<td>{row['learning_rate']:g}</td>"
                f"<td>{escape(row['params'].get('epochs', '—'))}</td>"
                f"<td>{row['loss']}</td><td>{row['accuracy']}</td>"
                f"<td>{row['best_step']}</td><td>{duration}</td></tr>"
            )
        return (
            "<table><thead><tr><th>#</th><th>run</th><th>learning rate</th><th>epochs</th>"
            "<th>final loss</th><th>final accuracy</th><th>best step</th><th>duration</th>"
            f"</tr></thead><tbody>{body}</tbody></table>"
        )

    def _page(self, body: str) -> str:
        """Wrap ``body`` in the page, with Plotly and the theme script inlined."""
        return _PAGE.format(
            plotlyjs=get_plotlyjs(),
            body=body,
            accents=json.dumps(list(_ACCENTS)),
            fallback=json.dumps(list(_FALLBACK_COLORS)),
        )
