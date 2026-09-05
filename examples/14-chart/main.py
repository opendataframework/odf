"""ChartProtocol: a Component-level, not Repository-level, dev-UI capability.

SalesByStore implements chart() -> str, a self-contained HTML document (an
inline base64 PNG here) that the dev UI serves verbatim and renders inside a
same-origin <iframe> via a "View Chart" button. Independent of DataView
(examples 06 and 07-13) — that family lives on Repository, this lives on
Component, and the component gets normal constructor-injected access to
repositories, no separate data-fetching layer needed.

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
