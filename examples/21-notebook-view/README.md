# 21 — Notebook View

A `Notebooks` repository over the `.ipynb` files in `notebooks/`, implementing
`data_view() -> DocumentView`. The topology UI renders a card per notebook,
previewing its first cells; selecting a card opens the notebook in the reader
as its cells and their saved outputs:

- Markdown cells are rendered.
- Code cells are shown as written, with their execution count.
- Images, such as the chart in `sales-summary.ipynb`, are shown inline.
- HTML outputs, such as a pandas DataFrame, are shown with anything that
  could run removed.

**View source** in the rail at the top left of the reader shows the
notebook's JSON.

With the `notebook` package installed in the project's environment, the pencil
under it, **Edit in Jupyter**, swaps the rendered notebook for Jupyter
Notebook's own editor, embedded in the reader. You get the same editor as a
local notebook server: run cells, add and move them, restart the kernel.
Pressing the pencil again closes the editor and shows the notebook
as last saved.

Jupyter starts the first time a notebook is edited, which takes a few
seconds, and stops with `odf run`. Its kernels start in this directory, so a
cell can open `data/sales.csv` or `import app` the same way the project does.
`scratch.ipynb` does the second:

```python
from app.repositories import Notebooks

[notebook.name for notebook in Notebooks().all()]
```

Jupyter saves each notebook through `Notebooks.save()`, which writes it back
to its file in `notebooks/`. A repository keeping notebooks somewhere else, a
database or an object store, gets the same editing with no change to the UI.
Notebooks autosave every 5 seconds unless your Jupyter settings say otherwise,
and `Ctrl+S` / `Cmd+S` saves straight away. Save before closing the editor,
since closing it drops anything not yet saved. A notebook can't be created,
renamed or deleted from Jupyter, only edited; records are added and removed
in the UI.

`Notebooks.content_metadata()` names each file and declares it
`application/x-ipynb+json`, which labels the card with the file name and
makes the preview show cells instead of JSON. A notebook with nothing
declared still opens as a notebook, worked out from its content.

`[ui] notebooks = false` in `config.toml` turns editing off, leaving notebooks
rendered but read-only. Editing is on by default whenever `notebook` is
installed.

## Structure

```
21-notebook-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — lists the notebooks, prints data_view()
├── data/
│   └── sales.csv        # what sales-summary.ipynb reads
├── notebooks/
│   ├── sales-summary.ipynb  # Markdown, code, a printed table and a chart, with outputs saved
│   └── scratch.ipynb        # a short notebook to edit
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py      # Notebook(name, content) — @Entity
    └── repositories.py  # Notebooks — @Storage @Repository(Notebook), one record per .ipynb file
```

## Dependencies

Viewing needs nothing beyond `opendataframework` itself. Editing needs Jupyter
Notebook installed alongside `odf`, and running `sales-summary.ipynb`'s chart
needs `matplotlib`:

```bash
pip install "odf[ui,notebook]" matplotlib
```

## Run it

```bash
cd examples/21-notebook-view
python main.py
```

Expected output:

```
All notebooks:
  Notebook(name='sales-summary', content=<16097 bytes>)
  Notebook(name='scratch', content=<677 bytes>)

data_view() -> DocumentView(field='content')
```

Or start the dev UI and click **View Documents** on `Notebooks`:

```bash
odf run
```
