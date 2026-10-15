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

File bytes are served by `GET /api/repositories/{id}/records/{key}/media`,
which **Open original** links to and **Download** saves. Bytes that are
neither a PDF nor UTF-8 text (a `.docx`, say) can't be displayed: the card and
the reader name the type instead, and **Open original** downloads the file.

`OrderReceipts` also implements `content_metadata(receipt)`, declaring each
file receipt's name (`order-104.pdf`) and type (`application/pdf`). The file
names aren't `OrderReceipt` fields: the repository keeps them beside the
receipts it read from `data/receipts/`. A declared name labels the card and
the reader and names the downloaded file. A declared type is taken over
working the type out from the bytes, but only picks between the same three
outcomes: a PDF, text, or a download. A receipt held in the record, or saved
from the UI, declares nothing and is worked out from its content as before. PDFs are drawn by
[pdf.js](https://mozilla.github.io/pdf.js/), loaded from a CDN the first
time a PDF is shown, so displaying one needs network access.

Whether text is Markdown isn't taken from a file name or a declared type, so
the UI goes by the text itself: headings, code fences, links and tables
count for more than list items and bold text, and enough of them make it
Markdown. It is then rendered by [marked](https://marked.js.org/), with
[DOMPurify](https://github.com/cure53/DOMPurify) removing any markup that
could run, both loaded from a CDN with the first Markdown document. The
**View source** button in the rail at the top left of the reader switches
between the two, for when the guess is wrong. Text holding a JSON object or array, such as a
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
    └── repositories.py   # OrderReceipts — @Storage @Repository(OrderReceipt), in-memory, pre-seeded, with content_metadata()
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

## Annotating

An open receipt can be labelled, for simple cases where a separate annotation
tool or a one-off script would be more than the job needs. What it takes
follows from what it opens as:

- **Text** (`order-103.txt`): pick **Label text** (`T`) in the rail at the top
  left of the reader, select some of the text, type a label and press
  `Enter`. With **Select** (`V`), the tool a document first opens on, selected
  text is left alone, to be copied. The tool picked is remembered in the
  browser. Labels already used in the repository are listed under the input,
  to click or to pick with `↓`/`↑` and `Enter`; typing narrows the list, and
  the last label is prefilled. White space at either end of the selection is
  left out, and a selection that runs into a span already there is refused,
  so spans never overlap.
- **Markdown and JSON text** (`order-105.md`, `order-106.json`): the same.
  **Label text** switches to the source, since a span is a place in the text
  as written, which the rendered view doesn't show.
- **A PDF** (`order-104.pdf`): pick **Draw a box** (`B`) and drag on a page
  to draw one, then label it the same way. A box inside a larger one stays on top, so it can still be
  selected.
- **A `dict` or `list`** (receipts 1 and 2) can't be labelled: it has no text
  of its own for a span to point into.

Select a span or a box and press `Delete` (or its `×`) to remove it, or select
its label to change it. There is no move or resize: delete it and make it
again. A label nothing in the repository uses any more is dropped from the
list. `Esc` backs out of the label input, then the selection, then the
receipt.

Every change is saved to `annotations.json` in the directory `odf run` was
started from (`[project] annotations-file` in `config.toml` names another
path), the same file image boxes go to. `annotations = false` under `[ui]` in
`config.toml` turns annotating off for a project that doesn't need it. The
file looks like this:

```json
{
  "version": 1,
  "repositories": {
    "order-receipts": {
      "labels": ["total", "logo"],
      "records": {
        "3": {
          "annotations": [
            {"type": "span", "label": "total", "start": 220, "end": 227, "text": "50.00 €"}
          ]
        },
        "4": {
          "annotations": [
            {"type": "box", "label": "logo", "page": 1,
             "x": 40, "y": 32.5, "width": 120, "height": 48,
             "page_width": 612, "page_height": 792}
          ]
        }
      }
    }
  }
}
```

- `repositories` is keyed by repository id, and `records` by record key (as a
  string). A record with no annotations has no entry.
- `labels` lists the labels that repository's annotations use, in the order
  each was first used. A label nothing uses any more is dropped, so a label's
  index is a stable class id only while every label before it stays in use.
- A span's `start` and `end` (exclusive) count characters the way Python
  indexes a `str`, into the document's text: the `str` itself, or the file's
  bytes decoded as UTF-8 (after a byte order mark, if it has one). `text` is
  what the span covered when it was drawn, to tell a document that has changed
  since. A record's spans are listed in the order they appear in the text.
- A box's `x`, `y`, `width` and `height` are PDF points (1/72 inch) from the
  top-left corner of the page as displayed, with `page` counted from 1.
  `page_width` and `page_height` are that page's own size, so a box can be
  normalised without opening the PDF.

The file is plain JSON, so a pipeline reads it without importing `odf`:

```python
import json
from pathlib import Path

block = json.load(open("annotations.json"))["repositories"]["order-receipts"]
text = Path("data/receipts/order-103.txt").read_text(encoding="utf-8")
for span in block["records"]["3"]["annotations"]:
    assert text[span["start"] : span["end"]] == span["text"]
    entity = (span["start"], span["end"], span["label"])  # spaCy-style
```
