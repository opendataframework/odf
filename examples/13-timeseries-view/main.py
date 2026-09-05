"""View: TimeseriesView, a line chart instead of a table.

Orders implements data_view() -> TimeseriesView instead of the default
table. The topology UI plots the entity's other numeric fields (amount)
against the named timestamp field (created_at) as a line chart, one point
per record, instead of a grid of columns.

Orders comes pre-seeded in-memory (see app/repositories.py's _SEED_ORDERS)
rather than seeded here, so there's already a line to chart — main.py only
reads the orders back. Run from this directory: `python main.py`, or
`odf run` and click "View Chart" on Orders in the UI.
"""

from app.repositories import Orders

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

orders = server.context.get(Orders)

print("All orders:")
for order in orders.all():
    print(f"  Order(id={order.id}, amount={order.amount}, created_at={order.created_at})")

print(f"\ndata_view() -> {orders.data_view()}")

server.stop()
