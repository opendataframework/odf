"""ChartProtocol with an interactive JS charting library instead of a static
image.

SalesByStore implements chart() -> str the same as 14-chart's matplotlib
version, but the self-contained HTML document it returns inlines Plotly's
own JS bundle (via plotly.offline.get_plotlyjs()) instead of a base64 PNG —
still self-contained per ChartProtocol (no external file references), now
with real hover tooltips.

Sales comes pre-seeded in-memory (see app/repositories.py's _SEED_SALES)
rather than seeded here, so there's already something for SalesByStore to
chart — main.py only calls chart() directly. Run from this directory:
`python main.py`, or `odf run` and click "View Chart" on SalesByStore in
the UI to see it rendered.
"""

from app.components import SalesByStore

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

chart = server.context.get(SalesByStore)
html = chart.chart()

print(f"chart() -> {len(html)} bytes of self-contained HTML, starting with:")
print(html[:80] + "...")

server.stop()
