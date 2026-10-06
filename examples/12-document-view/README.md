# 12 — Document View

A single `OrderReceipts` repository implementing
`data_view() -> DocumentView` instead of getting the default table. The
topology UI renders a grid of cards, one per record, each previewing the
start of its document; selecting a card opens the document, with the
record's other fields as a caption, previous/next buttons (or the arrow
keys), and `Esc` to return to the grid.

What a document opens as follows from the value of `OrderReceipt`'s
`document` field:

| Value | Shown as | Card preview |
|---|---|---|
| a `dict` or `list` | a collapsible JSON tree, Postman-style | its first lines as JSON |
| a `str` | text: a JSON tree if it parses as JSON, rendered if it reads as Markdown | its first lines |
| `bytes` of a PDF | its pages | its first page, with the page count |
| `bytes` of UTF-8 text (plain text, JSON, Markdown, CSV, ...) | text, as for a `str` | its first lines |

File bytes are told apart by their content, not by a file name, and are
served by `GET /api/repositories/{id}/records/{key}/media`, which **Open
original** links to. Bytes that are neither a PDF nor UTF-8 text (a `.docx`,
say) can't be displayed: the card and the reader name the type instead, and
**Open original** downloads the file. PDFs are drawn by
[pdf.js](https://mozilla.github.io/pdf.js/), loaded from a CDN the first
time a PDF is shown, so displaying one needs network access.

A record carries no file name or type to say that its text is Markdown, so
the UI goes by the text itself: headings, code fences, links and tables
count for more than list items and bold text, and enough of them make it
Markdown. It is then rendered by [marked](https://marked.js.org/), with
[DOMPurify](https://github.com/cure53/DOMPurify) removing any markup that
could run, both loaded from a CDN with the first Markdown document. **View
source** and **View as Markdown** in the reader switch between the two, for
when the guess is wrong. Text holding a JSON object or array, such as a
`.json` file, opens as the same tree a `dict` does, with **View source**
showing it as written.

This isolates the `DocumentView` variant covered in
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/).

`OrderReceipts` comes pre-seeded in-memory with six receipts (see
`app/repositories.py`'s `_SEED_RECEIPTS`): two as dicts, and one each read
from a text file, a PDF, a Markdown file and a JSON file under
`data/receipts/` — a document view is a lot more useful to look at with
something already in it.

## Structure

```
12-document-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded receipts, prints data_view()
├── data/
│   └── receipts/        # order-103.txt, order-104.pdf, order-105.md, order-106.json — the receipts kept as files
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
  OrderReceipt(id=2, order_id=102, document={'order_id': 102, 'line_items': [{'sku': 'SKU-0102', 'quantity': 2, 'price': 12.5}, {'sku': 'SKU-0318', 'quantity': 1, 'price': 25.0}], 'subtotal': 50.0, 'tax': 4.0, 'total': 54.0})
  OrderReceipt(id=3, order_id=103, document=<258 bytes>)
  OrderReceipt(id=4, order_id=104, document=<1676 bytes>)
  OrderReceipt(id=5, order_id=105, document=<407 bytes>)
  OrderReceipt(id=6, order_id=106, document=<244 bytes>)

data_view() -> DocumentView(field='document')
```

Or start the dev UI and click **View Documents** on `OrderReceipts`:

```bash
odf run
```

`GET /api/repositories` reports `OrderReceipts`' view as
`{"kind": "document", "field": "document"}` — that's what tells the UI to
render document cards instead of a table.
