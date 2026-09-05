"""Matplotlib chart component for the chart example."""

import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from opendataframework import Analytics, Component

from app.repositories import Sales


@Analytics
@Component
class SalesByStore:
    """Bar chart of total sale amount per store — a minimal ``ChartProtocol``
    example. Rebuilds the figure from ``Sales`` on every ``chart()`` call
    rather than caching it, so the chart reflects live data each time it's
    opened.

    Deliberately a single static image with no light/dark theme handling —
    see ``examples/15-chart-plotly``'s ``SalesByStore`` for a Plotly-backed
    sibling with real hover tooltips instead of a static PNG.
    """

    def __init__(self, sales: Sales) -> None:
        """Store the sales source to chart.

        Args:
            sales: The repository to aggregate on each ``chart()`` call.
        """
        self.sales = sales

    def chart(self) -> str:
        """Render a bar chart of total sale amount per store.

        Returns:
            A self-contained HTML document embedding the chart as a PNG.
        """
        totals: dict[str, float] = {}
        for sale in self.sales.all():
            totals[sale.store] = totals.get(sale.store, 0.0) + sale.amount

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(list(totals.keys()), list(totals.values()))
        ax.set_title("Sales by Store")
        ax.set_ylabel("Total amount")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        encoded = base64.b64encode(buf.getvalue()).decode()

        return f"<html><body><img src='data:image/png;base64,{encoded}'></body></html>"
