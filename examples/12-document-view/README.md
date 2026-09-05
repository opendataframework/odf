# 12 — Document View

A single `OrderReceipts` repository implementing
`data_view() -> DocumentView` instead of getting the default table. Given
`OrderReceipt`'s `document: dict` field, the topology UI renders a
collapsible JSON tree per record, Postman-style, instead of stringifying the
nested dict into an unreadable table cell.

This isolates the `DocumentView` variant covered in
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/) —
the odd one out among the media
views: it exists for genuinely nested data, not bytes.

`OrderReceipts` comes pre-seeded in-memory with one receipt (see
`app/repositories.py`'s `_SEED_RECEIPTS`) — there's no reason to reach for
a file when the data is this small, and a document view is a lot more
useful to look at with something already in it.

## Structure

```
12-document-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded receipt, prints data_view()
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py       # OrderReceipt(id, order_id, document, issued_at) — @Entity
    └── repositories.py   # OrderReceipts — @Storage @Repository(OrderReceipt), in-memory, pre-seeded
```

## Dependencies

None beyond `opendataframework` itself and the Python standard library.

## Run it

```bash
cd examples/12-document-view
python main.py
```

Expected output (the timestamp isn't printed, so this is stable):

```
All receipts:
  OrderReceipt(id=1, order_id=101, document={'order_id': 101, 'line_items': [{'sku': 'SKU-0101', 'quantity': 1, 'price': 92.59}], 'subtotal': 92.59, 'tax': 7.41, 'total': 100.0})

data_view() -> DocumentView(field='document')
```

Or start the dev UI and click **View Documents** on `OrderReceipts`:

```bash
odf run
```

`GET /api/repositories` reports `OrderReceipts`' view as
`{"kind": "document", "field": "document"}` — that's what tells the UI to
render a collapsible JSON tree instead of a table.
