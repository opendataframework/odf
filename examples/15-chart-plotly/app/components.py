"""Plotly chart component for the chart-plotly example."""

import plotly.graph_objects as go
from opendataframework import Analytics, Component
from plotly.offline import get_plotlyjs

from app.repositories import Sales

_HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<script>{plotlyjs}</script>
</head>
<body>
{chart_div}
</body>
</html>"""


@Analytics
@Component
class SalesByStore:
    """Bar chart of total sale amount per store — a Plotly-backed sibling of
    14-chart's matplotlib ``SalesByStore``, same ``ChartProtocol`` contract,
    different charting library.

    ``chart()`` must return a self-contained HTML document (no external
    file references) — for an interactive JS chart that means inlining the
    charting library's own JS bundle, not just an image. ``plotly.offline
    .get_plotlyjs()`` returns that bundle as a string, embedded once via
    ``_HTML_TEMPLATE``; ``fig.to_html(include_plotlyjs=False)`` then emits
    only the chart's own `<div>`/`<script>`, assuming that bundle is already
    on the page. In return for the extra inlining step, the chart gets real
    hover tooltips instead of a static image.

    Rebuilds the figure from ``Sales`` on every ``chart()`` call rather than
    caching it, so the chart reflects live data each time it's opened —
    same as the matplotlib version.
    """

    def __init__(self, sales: Sales) -> None:
        """Store the sales source to chart.

        Args:
            sales: The repository to aggregate on each ``chart()`` call.
        """
        self.sales = sales

    def chart(self) -> str:
        """Render an interactive bar chart of total sale amount per store.

        Returns:
            A self-contained HTML document embedding the Plotly chart and
            its inlined JS bundle.
        """
        totals: dict[str, float] = {}
        for sale in self.sales.all():
            totals[sale.store] = totals.get(sale.store, 0.0) + sale.amount

        labels = list(totals.keys())
        values = list(totals.values())

        fig = go.Figure(
            go.Bar(
                x=labels,
                y=values,
                text=[f"${v:,.2f}" for v in values],
                textposition="outside",
                hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(
            title="Sales by Store", yaxis_title="Total amount", margin=dict(l=40, r=20, t=48, b=40)
        )

        chart_div = fig.to_html(
            full_html=False, include_plotlyjs=False, config={"displayModeBar": False}
        )
        return _HTML_TEMPLATE.format(plotlyjs=get_plotlyjs(), chart_div=chart_div)
