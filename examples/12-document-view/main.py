"""View: DocumentView, arbitrary nested JSON instead of a stringified cell.

OrderReceipts implements data_view() -> DocumentView instead of the default
table. Given OrderReceipt's `document: dict` field, the topology UI renders
a collapsible JSON tree per record, Postman-style, instead of stringifying
the nested dict into an unreadable table cell.

OrderReceipts comes pre-seeded in-memory (see app/repositories.py's
_SEED_RECEIPTS) rather than seeded here, so there's already something to
look at — main.py only reads the receipts back. Run from this directory:
`python main.py`, or `odf run` and click "View Documents" on
OrderReceipts in the UI.
"""

from app.repositories import OrderReceipts

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

receipts = server.context.get(OrderReceipts)

print("All receipts:")
for receipt in receipts.all():
    print(
        f"  OrderReceipt(id={receipt.id}, order_id={receipt.order_id}, document={receipt.document})"
    )

print(f"\ndata_view() -> {receipts.data_view()}")

server.stop()
