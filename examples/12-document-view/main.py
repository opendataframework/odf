"""View: DocumentView, a readable document per record.

OrderReceipts implements data_view() -> DocumentView instead of the default
table. The topology UI renders a grid of cards, one per record, each
previewing the start of its document; selecting a card opens the document.
What it opens as follows from OrderReceipt's `document` field: a dict is a
collapsible JSON tree, text is text (rendered, if it reads as Markdown), and
the bytes of a file are a PDF or a text file.

OrderReceipts comes pre-seeded in-memory (see app/repositories.py's
_SEED_RECEIPTS, two of them read from data/receipts) rather than seeded here,
so there's already something to look at — main.py only reads the receipts
back. Run from this directory: `python main.py`, or `odf run` and click
"View Documents" on OrderReceipts in the UI.
"""

from app.repositories import OrderReceipts

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

receipts = server.context.get(OrderReceipts)

print("All receipts:")
for receipt in receipts.all():
    document = receipt.document
    if isinstance(document, bytes):
        document = f"<{len(document)} bytes>"
    print(f"  OrderReceipt(id={receipt.id}, order_id={receipt.order_id}, document={document})")

print(f"\ndata_view() -> {receipts.data_view()}")

server.stop()
